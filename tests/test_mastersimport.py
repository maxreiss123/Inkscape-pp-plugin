import os
import tempfile
import zipfile

import pytest
from pplib import mastersimport

A = mastersimport._A
P = mastersimport._P

PPTX_PRES = (
    '<p:presentation xmlns:p="%s">'
    '<p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>'
    "</p:presentation>" % P
)

PPTX_THEME = (
    '<a:theme xmlns:a="%s"><a:themeElements>'
    "<a:clrScheme>"
    '<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>'
    '<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
    '<a:accent1><a:srgbClr val="4472C4"/></a:accent1>'
    "</a:clrScheme>"
    "<a:fontScheme>"
    '<a:majorFont><a:latin typeface="Calibri Light"/></a:majorFont>'
    '<a:minorFont><a:latin typeface="Calibri"/></a:minorFont>'
    "</a:fontScheme>"
    "</a:themeElements></a:theme>" % A
)


# A realistic slide master: a coloured background (which lt1 does not reflect)
# plus explicit title/body text styles -- the bits a typical corporate template
# actually carries.
PPTX_MASTER = (
    '<p:sldMaster xmlns:p="%s" xmlns:a="%s">'
    "<p:cSld>"
    '<p:bg><p:bgPr><a:solidFill><a:srgbClr val="1F2933"/></a:solidFill></p:bgPr></p:bg>'
    "<p:spTree/></p:cSld>"
    "<p:txStyles>"
    '<p:titleStyle><a:lvl1pPr><a:defRPr sz="4400">'
    '<a:solidFill><a:srgbClr val="C0392B"/></a:solidFill>'
    "</a:defRPr></a:lvl1pPr></p:titleStyle>"
    '<p:bodyStyle><a:lvl1pPr><a:defRPr sz="2000"/></a:lvl1pPr></p:bodyStyle>'
    "</p:txStyles></p:sldMaster>" % (P, A)
)

PPTX_MASTER_SCHEME_BG = (
    '<p:sldMaster xmlns:p="%s" xmlns:a="%s">'
    "<p:cSld>"
    '<p:bg><p:bgRef idx="1001"><a:schemeClr val="accent1"/></p:bgRef></p:bg>'
    "<p:spTree/></p:cSld></p:sldMaster>" % (P, A)
)


def _make_pptx(suffix=".pptx", master=None):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("ppt/presentation.xml", PPTX_PRES)
        zf.writestr("ppt/theme/theme1.xml", PPTX_THEME)
        if master:
            zf.writestr("ppt/slideMasters/slideMaster1.xml", master)
    return path


ODP_STYLES = (
    '<office:document-styles '
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:style="%s" xmlns:draw="%s" xmlns:fo="%s">'
    "<office:styles>"
    '<style:default-style style:family="paragraph">'
    '<style:text-properties style:font-name="Liberation Sans"/>'
    "</style:default-style>"
    '<style:style style:family="drawing-page" style:name="Mdp1">'
    '<style:drawing-page-properties draw:fill="solid" draw:fill-color="#102030"/>'
    "</style:style>"
    "</office:styles>"
    "<office:automatic-styles>"
    '<style:page-layout style:name="PL1">'
    '<style:page-layout-properties fo:page-width="25.4cm" fo:page-height="19.05cm"/>'
    "</style:page-layout>"
    "</office:automatic-styles>"
    "</office:document-styles>"
    % (mastersimport._STYLE, mastersimport._DRAW, mastersimport._FO)
)


def _make_odp():
    fd, path = tempfile.mkstemp(suffix=".odp")
    os.close(fd)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("styles.xml", ODP_STYLES)
    return path


def test_import_pptx_theme():
    path = _make_pptx()
    try:
        overrides, aspect, size = mastersimport.import_master(path)
    finally:
        os.remove(path)
    assert aspect == "16:9"
    assert overrides["bg_color"] == "#FFFFFF"
    assert overrides["accent_color"] == "#4472C4"
    assert overrides["font_family"] == "Calibri"


def test_import_odp_theme():
    path = _make_odp()
    try:
        overrides, aspect, size = mastersimport.import_master(path)
    finally:
        os.remove(path)
    assert aspect == "4:3"  # 25.4 x 19.05 cm
    assert overrides["bg_color"] == "#102030"
    assert overrides["font_family"] == "Liberation Sans"


def test_unsupported_type_raises():
    with pytest.raises(ValueError):
        mastersimport.import_master("/tmp/whatever.key")


def test_apply_import_updates_master(presentation):
    path = _make_pptx()
    try:
        summary = mastersimport.apply_import(presentation, path, resize=True)
    finally:
        os.remove(path)
    defn = presentation.master_by_id(None).definition
    assert defn["accent_color"] == "#4472C4"
    assert defn["font_family"] == "Calibri"
    assert "Imported" in summary or "theme" in summary


def test_import_potx_with_slide_master():
    """The .potx template format works, and the slide master drives the look."""
    path = _make_pptx(suffix=".potx", master=PPTX_MASTER)
    try:
        overrides, aspect, size = mastersimport.import_master(path)
    finally:
        os.remove(path)
    # Master background beats the theme's lt1 white.
    assert overrides["bg_color"] == "#1F2933"
    # 44pt title -> 88px in our units; explicit title colour; 20pt body -> 40px.
    assert overrides["title_font_size"] == 88
    assert overrides["title_color"] == "#C0392B"
    assert overrides["body_font_size"] == 40
    assert aspect == "16:9"


_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\x00\x02"
    b"\x00\x00\x05\x00\x01\xe2&\x05\x9b\x00\x00\x00\x00IEND\xaeB`\x82"
)

PPTX_MASTER_IMAGE = (
    '<p:sldMaster xmlns:p="%s" xmlns:a="%s" xmlns:r="%s"><p:cSld>'
    '<p:bg><p:bgPr><a:blipFill><a:blip r:embed="rId1"/>'
    "<a:stretch><a:fillRect/></a:stretch></a:blipFill></p:bgPr></p:bg>"
    "<p:spTree/></p:cSld></p:sldMaster>"
    % (P, A, mastersimport._R)
)


def _make_pptx_image_bg():
    fd, path = tempfile.mkstemp(suffix=".pptx")
    os.close(fd)
    rels = (
        '<Relationships xmlns="%s">'
        '<Relationship Id="rId1" Type="%s/image" Target="../media/image1.png"/>'
        "</Relationships>" % (mastersimport._CT, mastersimport._R)
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("ppt/presentation.xml", PPTX_PRES)
        zf.writestr("ppt/theme/theme1.xml", PPTX_THEME)
        zf.writestr("ppt/slideMasters/slideMaster1.xml", PPTX_MASTER_IMAGE)
        zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", rels)
        zf.writestr("ppt/media/image1.png", _PNG_1X1)
    return path


def test_background_image_extracted_and_applied(presentation):
    path = _make_pptx_image_bg()
    try:
        overrides, _, _ = mastersimport.import_master(path)
        assert overrides["bg_image"].startswith("data:image/png;base64,")
        mastersimport.apply_import(presentation, path)
    finally:
        os.remove(path)
    # Every slide now carries a managed background <image>.
    from pplib import constants as C
    from pplib import svgutil as S
    for slide in presentation.slides():
        imgs = [e for e in slide.layer
                if e.tag.endswith("}image")
                and S.get_pp(e, C.A_PH_ROLE) == C.PhRole.BACKGROUND]
        assert len(imgs) == 1
        assert imgs[0].get("{http://www.w3.org/1999/xlink}href").startswith(
            "data:image/png;base64,")


PPTX_MASTER_SHAPES = (
    '<p:sldMaster xmlns:p="%s" xmlns:a="%s"><p:cSld><p:spTree>'
    '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
    "<p:grpSpPr/>"
    '<p:sp><p:nvSpPr><p:cNvPr id="2" name="band"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
    '<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="12192000" cy="1219200"/></a:xfrm>'
    '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
    '<a:solidFill><a:srgbClr val="0E2A47"/></a:solidFill></p:spPr></p:sp>'
    '<p:sp><p:nvSpPr><p:cNvPr id="3" name="dot"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
    '<p:spPr><a:xfrm><a:off x="10000000" y="5000000"/><a:ext cx="800000" cy="800000"/></a:xfrm>'
    '<a:prstGeom prst="ellipse"><a:avLst/></a:prstGeom>'
    '<a:solidFill><a:schemeClr val="accent1"/></a:solidFill></p:spPr></p:sp>'
    "</p:spTree></p:cSld></p:sldMaster>" % (P, A)
)


def test_master_vector_shapes_imported_and_applied(presentation):
    path = _make_pptx(master=PPTX_MASTER_SHAPES)
    try:
        overrides, _, _ = mastersimport.import_master(path)
        assert "bg_shapes" in overrides
        # Band rect (navy) + dot ellipse (accent1 resolved) translated to SVG.
        assert "rect" in overrides["bg_shapes"]
        assert "ellipse" in overrides["bg_shapes"]
        assert "#0E2A47" in overrides["bg_shapes"]
        assert "#4472C4" in overrides["bg_shapes"]  # schemeClr accent1
        mastersimport.apply_import(presentation, path)
    finally:
        os.remove(path)
    from pplib import constants as C
    from pplib import svgutil as S
    for slide in presentation.slides():
        groups = [e for e in slide.layer
                  if e.tag.endswith("}g")
                  and S.get_pp(e, C.A_PH_ROLE) == C.PhRole.BACKGROUND]
        assert groups, "master graphics group missing"
        assert groups[0].findall(".//{http://www.w3.org/2000/svg}rect")
        assert groups[0].findall(".//{http://www.w3.org/2000/svg}ellipse")


def test_master_bgref_scheme_colour_resolves():
    path = _make_pptx(master=PPTX_MASTER_SCHEME_BG)
    try:
        overrides, _, _ = mastersimport.import_master(path)
    finally:
        os.remove(path)
    assert overrides["bg_color"] == "#4472C4"  # schemeClr accent1 resolved


def test_unsupported_message_lists_formats():
    with pytest.raises(ValueError) as err:
        mastersimport.import_master("/tmp/whatever.key")
    assert ".potx" in str(err.value)


def _clr(xml):
    import lxml.etree as ET
    return ET.fromstring(xml % A)


def test_colour_lummod_transform():
    sf = _clr('<a:solidFill xmlns:a="%s"><a:srgbClr val="808080">'
              '<a:lumMod val="50000"/></a:srgbClr></a:solidFill>')
    assert mastersimport._resolve_color(sf, {}) == "#404040"  # 128 * 0.5 = 64


def test_colour_tint_transform():
    sf = _clr('<a:solidFill xmlns:a="%s"><a:srgbClr val="000000">'
              '<a:tint val="50000"/></a:srgbClr></a:solidFill>')
    # 0 * 0.5 + 255 * 0.5 = 128 -> #808080
    assert mastersimport._resolve_color(sf, {}) == "#808080"


def test_colour_alpha_opacity():
    sf = _clr('<a:solidFill xmlns:a="%s"><a:srgbClr val="FF0000">'
              '<a:alpha val="40000"/></a:srgbClr></a:solidFill>')
    assert mastersimport._color_alpha(sf) == 0.4


def test_shape_alpha_becomes_fill_opacity():
    import lxml.etree as ET
    from pplib import ooxml_shapes as OX
    sp = ET.fromstring(
        '<p:sp xmlns:p="%s" xmlns:a="%s">'
        '<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="1000" cy="1000"/></a:xfrm>'
        '<a:prstGeom prst="rect"/><a:solidFill><a:srgbClr val="2E86C1">'
        '<a:alpha val="40000"/></a:srgbClr></a:solidFill></p:spPr></p:sp>'
        % (P, A))
    el = OX._shape(sp, (0, 0, 1.0), lambda e: mastersimport._resolve_color(e, {}))
    style = el.get("style")
    assert "fill:#2E86C1" in style
    assert "fill-opacity:0.4" in style


def test_fillref_idx0_is_no_fill():
    """A text box's <a:fillRef idx="0"> must not paint an opaque rectangle."""
    import lxml.etree as ET
    from pplib import ooxml_shapes as OX
    scheme = {"accent1": "#4472C4"}
    sp = ET.fromstring(
        '<p:sp xmlns:p="%s" xmlns:a="%s">'
        '<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="1000" cy="1000"/></a:xfrm>'
        '<a:prstGeom prst="rect"/></p:spPr>'
        '<p:style><a:lnRef idx="0"><a:schemeClr val="accent1"/></a:lnRef>'
        '<a:fillRef idx="0"><a:schemeClr val="accent1"/></a:fillRef></p:style>'
        "</p:sp>" % (P, A))
    el = OX._shape(sp, (0, 0, 1.0), lambda e: mastersimport._resolve_color(e, scheme))
    assert el is None  # no fill + no stroke -> nothing painted

    sp2 = ET.fromstring(
        '<p:sp xmlns:p="%s" xmlns:a="%s">'
        '<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="1000" cy="1000"/></a:xfrm>'
        '<a:prstGeom prst="rect"/></p:spPr>'
        '<p:style><a:fillRef idx="1"><a:schemeClr val="accent1"/></a:fillRef>'
        "</p:style></p:sp>" % (P, A))
    el2 = OX._shape(sp2, (0, 0, 1.0), lambda e: mastersimport._resolve_color(e, scheme))
    assert el2 is not None and "fill:#4472C4" in el2.get("style")


def test_apply_import_summary_is_detailed(presentation):
    path = _make_pptx(master=PPTX_MASTER)
    try:
        summary = mastersimport.apply_import(presentation, path)
    finally:
        os.remove(path)
    assert "background: #1F2933" in summary
    assert "Applied to 3 slides." in summary


def test_apply_import_restyles_existing_text(presentation):
    from pplib import placeholders as Ph
    from pplib import svgutil as S

    slide = presentation.slides()[0]  # title layout
    Ph.set_placeholder_text(slide.placeholder("title"), ["Hello"])

    path = _make_pptx(master=PPTX_MASTER)
    try:
        mastersimport.apply_import(presentation, path)
    finally:
        os.remove(path)

    text = Ph.placeholder_text_el(presentation.slides()[0].placeholder("title"))
    assert text.style["font-family"] == "Calibri"
    assert text.style["font-size"] == "88px"
    assert text.style["fill"] == "#C0392B"
    assert "Hello" in S.text_content(text)  # content untouched


def test_import_on_blank_doc_creates_styled_deck():
    """Importing on a non-setup document auto-creates a deck and applies it."""
    import importlib.util
    import io

    import inkex
    from pplib.model import Presentation

    handler_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "src", "pp", "pp_import_master.py")
    spec = importlib.util.spec_from_file_location("pp_import_master", handler_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    potx = _make_pptx(master=PPTX_MASTER)  # navy bg master
    blank = (b'<svg xmlns="http://www.w3.org/2000/svg" '
             b'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
             b'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd" '
             b'width="200" height="150" viewBox="0 0 200 150">'
             b'<sodipodi:namedview id="nv"/></svg>')
    fd, svgpath = tempfile.mkstemp(suffix=".svg")
    os.write(fd, blank)
    os.close(fd)
    try:
        ext = mod.ImportMaster()
        ext.parse_arguments(["--file=" + potx, svgpath])
        ext.document = inkex.load_svg(io.BytesIO(blank))
        ext.original_document = ext.document
        ext.svg = ext.document.getroot()
        ext.svg.selection.set()
        ext.effect()
        pres = Presentation(ext.svg)
        assert pres.is_initialized()
        assert pres.slide_count() >= 1
        defn = pres.master_by_id(None).definition
        assert defn["bg_color"] == "#1F2933"
    finally:
        os.remove(potx)
        os.remove(svgpath)
