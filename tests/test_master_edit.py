import base64
import importlib.util
import io
import os
import struct
import tempfile
import zlib

import inkex
from pplib import constants as C
from pplib import document
from pplib import svgutil as S
from pplib.model import Presentation

_MASTER_EDIT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src", "pp", "pp_master_edit.py")


def _png(rgb=(230, 89, 12)):
    raw = bytearray()
    for _ in range(4):
        raw.append(0)
        raw += bytes(rgb) * 4
    def ch(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n"
            + ch(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0))
            + ch(b"IDAT", zlib.compress(bytes(raw)))
            + ch(b"IEND", b""))


def _rgba(hex_rgb):
    return str((hex_rgb << 8) | 0xFF)


def _run(args):
    root = inkex.load_svg(
        b'<svg xmlns="http://www.w3.org/2000/svg" '
        b'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
        b'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd" '
        b'width="100" height="100" viewBox="0 0 100 100">'
        b'<sodipodi:namedview id="nv"/></svg>').getroot()
    pres = Presentation(root)
    document.init_presentation(pres, aspect="16:9", first_layout=C.LayoutKey.TITLE)
    data = __import__("lxml.etree", fromlist=["tostring"]).tostring(root.getroottree())

    spec = importlib.util.spec_from_file_location("pp_master_edit", _MASTER_EDIT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fd, path = tempfile.mkstemp(suffix=".svg")
    os.write(fd, data)
    os.close(fd)
    try:
        ext = mod.EditMaster()
        ext.parse_arguments(list(args) + [path])
        ext.document = inkex.load_svg(io.BytesIO(data))
        ext.original_document = ext.document
        ext.svg = ext.document.getroot()
        ext.svg.selection.set()
        ext.effect()
        return Presentation(ext.svg)
    finally:
        os.remove(path)


def test_master_edit_background_and_fonts():
    pres = _run(["--bg_mode=color", "--bg_color=" + _rgba(0x0E2A47),
                 "--font_family=Georgia", "--title_font_size=44",
                 "--title_color=" + _rgba(0xF2C14E)])
    defn = pres.master_by_id(None).definition
    assert defn["bg_color"] == "#0E2A47"
    assert defn["font_family"] == "Georgia"
    assert defn["title_font_size"] == 44
    assert defn["title_color"] == "#F2C14E"
    # The background rect on the slide picked up the colour.
    slide = pres.slides()[0]
    bg = [e for e in slide.layer
          if e.tag.endswith("}rect")
          and S.get_pp(e, C.A_PH_ROLE) == C.PhRole.BACKGROUND]
    assert bg and "#0E2A47" in bg[0].get("style", "")


def test_master_edit_logo_embedded_and_positioned():
    fd, logo = tempfile.mkstemp(suffix=".png")
    os.write(fd, _png())
    os.close(fd)
    try:
        pres = _run(["--logo_path=" + logo, "--logo_pos=bottom-right",
                     "--logo_size=0.1"])
    finally:
        os.remove(logo)
    defn = pres.master_by_id(None).definition
    assert defn["logo_href"].startswith("data:image/png;base64,")
    # Validate the embedded data really is the PNG.
    b64 = defn["logo_href"].split(",", 1)[1]
    assert base64.b64decode(b64)[:8] == b"\x89PNG\r\n\x1a\n"
    assert defn["logo_rect"][0] > 0.8 and defn["logo_rect"][1] > 0.8  # bottom-right
    imgs = [e for e in pres.slides()[0].layer
            if e.tag.endswith("}image")
            and S.get_pp(e, C.A_PH_ROLE) == C.PhRole.LOGO]
    assert imgs and imgs[0].get("{http://www.w3.org/1999/xlink}href").startswith(
        "data:image/png")


def test_master_edit_image_background():
    fd, img = tempfile.mkstemp(suffix=".png")
    os.write(fd, _png((10, 20, 30)))
    os.close(fd)
    try:
        pres = _run(["--bg_mode=image", "--bg_image=" + img])
    finally:
        os.remove(img)
    defn = pres.master_by_id(None).definition
    assert defn["bg_image"].startswith("data:image/png;base64,")
