"""Import a slide master's theme essentials from PowerPoint (.pptx) or
LibreOffice/OpenDocument (.odp) files.

Both formats are ZIP archives of XML. We extract the *essentials* -- slide size /
aspect, background colour, an accent colour and the body font -- and map them onto
our master definition. Placeholder geometry and images are intentionally out of
scope (DrawingML/ODF geometry is fragile); see the module docstring in the
project README.
"""

import zipfile

import lxml.etree as ET

from . import constants as C

# OOXML namespaces
_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
# ODF namespaces
_STYLE = "urn:oasis:names:tc:opendocument:xmlns:style:1.0"
_DRAW = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
_FO = "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"

EMU_PER_PX = 914400.0 / 96.0  # 9525 EMU per pixel at 96 dpi


def import_master(path):
    """Return (definition_overrides, aspect, size) parsed from ``path``.

    ``definition_overrides`` is a dict of master-definition keys to override.
    ``aspect`` is "16:9" / "4:3" / "custom" / None. ``size`` is (w, h) px or None.
    Raises ValueError for unsupported file types.
    """
    lower = path.lower()
    if lower.endswith((".pptx", ".potx", ".pptm", ".ppsx")):
        return _import_pptx(path)
    if lower.endswith((".odp", ".otp")):
        return _import_odp(path)
    raise ValueError(
        "Unsupported file type: %s\n"
        "Supported: PowerPoint .pptx / .potx and LibreOffice .odp / .otp." % path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _hex(value):
    if not value:
        return None
    value = value.strip().lstrip("#")
    if len(value) >= 6:
        return "#" + value[:6].upper()
    return None


def _aspect_for(w, h):
    if not w or not h:
        return None, None
    ratio = w / h
    if abs(ratio - 16 / 9) < 0.02:
        return "16:9", None
    if abs(ratio - 4 / 3) < 0.02:
        return "4:3", None
    return "custom", (w, h)


def _read_zip_member(path, name):
    with zipfile.ZipFile(path) as zf:
        try:
            return zf.read(name)
        except KeyError:
            return None


def _first_member(path, predicate):
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if predicate(name):
                return zf.read(name)
    return None


# ---------------------------------------------------------------------------
# PowerPoint (.pptx)
# ---------------------------------------------------------------------------
def _clr_value(parent):
    """Resolve a colour child (<a:srgbClr>/<a:sysClr>) to a hex string."""
    if parent is None:
        return None
    srgb = parent.find("{%s}srgbClr" % _A)
    if srgb is not None:
        return _hex(srgb.get("val"))
    sysclr = parent.find("{%s}sysClr" % _A)
    if sysclr is not None:
        return _hex(sysclr.get("lastClr") or sysclr.get("val"))
    return None


# Slide-master colour-map aliases (default clrMap: bg1->lt1, tx1->dk1, ...).
_SCHEME_ALIAS = {"bg1": "lt1", "tx1": "dk1", "bg2": "lt2", "tx2": "dk2"}

# PowerPoint points -> our page user units. Our pages are 1.5x the slide's
# 96dpi pixel size (16:9: 13.333in -> 1920, 4:3: 10in -> 1440), so
# px = pt * (96/72) * 1.5 = pt * 2.
_PT_TO_PX = 2.0


def _parse_scheme(theme_root):
    """Return {dk1, lt1, dk2, lt2, accent1..6, ...} -> '#RRGGBB'."""
    scheme = {}
    cs = theme_root.find(".//{%s}clrScheme" % _A)
    if cs is None:
        return scheme
    for child in cs:
        if not isinstance(child.tag, str):
            continue
        name = ET.QName(child.tag).localname
        val = _clr_value(child)
        if val:
            scheme[name] = val
    return scheme


def _resolve_color(el, scheme):
    """Resolve the first colour inside ``el`` (srgbClr / schemeClr / sysClr)."""
    if el is None:
        return None
    srgb = el.find(".//{%s}srgbClr" % _A)
    if srgb is not None:
        return _hex(srgb.get("val"))
    sc = el.find(".//{%s}schemeClr" % _A)
    if sc is not None:
        name = sc.get("val")
        return scheme.get(_SCHEME_ALIAS.get(name, name))
    sysc = el.find(".//{%s}sysClr" % _A)
    if sysc is not None:
        return _hex(sysc.get("lastClr") or sysc.get("val"))
    return None


def _style_overrides(style_el, scheme, size_key, color_key, out):
    """Read font size / colour from a txStyles entry (title/body style)."""
    if style_el is None:
        return
    rpr = style_el.find(".//{%s}defRPr" % _A)
    if rpr is None:
        return
    sz = rpr.get("sz")  # hundredths of a point
    if sz:
        try:
            out[size_key] = max(8, round(int(sz) / 100 * _PT_TO_PX))
        except ValueError:
            pass
    color = _resolve_color(rpr, scheme)
    if color:
        out[color_key] = color


_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_CT = "http://schemas.openxmlformats.org/package/2006/relationships"


def _zip_xml(zf, name):
    try:
        return ET.fromstring(zf.read(name))
    except KeyError:
        return None


def _rel_target(zf, part_name, embed_id):
    """Resolve an r:embed/r:id relationship to a normalised zip path."""
    import posixpath
    d, base = posixpath.split(part_name)
    rels_name = posixpath.join(d, "_rels", base + ".rels")
    try:
        rels = ET.fromstring(zf.read(rels_name))
    except KeyError:
        return None
    for rel in rels:
        if rel.get("Id") == embed_id:
            target = rel.get("Target")
            if target.startswith("/"):
                return target.lstrip("/")
            return posixpath.normpath(posixpath.join(d, target))
    return None


def _fmt_bg_color(theme_root, idx, scheme):
    """Resolve a bgRef idx into the theme's bgFillStyleLst solid colour."""
    if theme_root is None or idx < 1000:
        return None
    lst = theme_root.find(".//{%s}bgFillStyleLst" % _A)
    if lst is None:
        return None
    fills = [c for c in lst if isinstance(c.tag, str)]
    n = idx - 1001
    if 0 <= n < len(fills):
        return _resolve_color(fills[n], scheme)
    return None


def _extract_bg(zf, part_name, scheme, theme_root):
    """Return ('color', '#hex') or ('image', bytes, ext) from a part's <p:bg>."""
    import posixpath

    root = _zip_xml(zf, part_name)
    if root is None:
        return None
    bg = root.find(".//{%s}bg" % _P)
    if bg is None:
        return None

    # Background picture (the common case for branded templates).
    blip = bg.find(".//{%s}blip" % _A)
    if blip is not None:
        embed = blip.get("{%s}embed" % _R) or blip.get("embed")
        target = _rel_target(zf, part_name, embed) if embed else None
        if target:
            try:
                data = zf.read(target)
                ext = posixpath.splitext(target)[1].lstrip(".").lower() or "png"
                return ("image", data, ext)
            except KeyError:
                pass

    # Direct solid / scheme colour, then a bgRef into the theme fill styles.
    color = _resolve_color(bg, scheme)
    if not color:
        bgref = bg.find(".//{%s}bgRef" % _P)
        if bgref is not None:
            try:
                color = _fmt_bg_color(theme_root, int(bgref.get("idx", "0")), scheme)
            except ValueError:
                color = None
    if color and color.upper() != "#FFFFFF":
        return ("color", color)
    if color:
        return ("color", color)
    return None


def _import_pptx(path):
    import base64

    overrides = {}
    aspect = size = None

    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()

        cx_emu = cy_emu = None
        pres_root = _zip_xml(zf, "ppt/presentation.xml")
        if pres_root is not None:
            sldsz = pres_root.find("{%s}sldSz" % _P)
            if sldsz is not None:
                try:
                    cx_emu = float(sldsz.get("cx"))
                    cy_emu = float(sldsz.get("cy"))
                    aspect, size = _aspect_for(cx_emu / EMU_PER_PX, cy_emu / EMU_PER_PX)
                except (TypeError, ValueError):
                    pass

        scheme = {}
        theme_root = None
        theme_name = next((n for n in names
                           if n.startswith("ppt/theme/") and n.endswith(".xml")), None)
        if theme_name:
            theme_root = _zip_xml(zf, theme_name)
            scheme = _parse_scheme(theme_root)
            if scheme.get("accent1"):
                overrides["accent_color"] = scheme["accent1"]
            if scheme.get("dk1"):
                overrides["text_color"] = scheme["dk1"]
            font_scheme = theme_root.find(".//{%s}fontScheme" % _A)
            if font_scheme is not None:
                minor = font_scheme.find("{%s}minorFont/{%s}latin" % (_A, _A))
                major = font_scheme.find("{%s}majorFont/{%s}latin" % (_A, _A))
                face = None
                if minor is not None and minor.get("typeface"):
                    face = minor.get("typeface")
                elif major is not None and major.get("typeface"):
                    face = major.get("typeface")
                if face:
                    overrides["font_family"] = face

        # Background: try the slide master, then each slide layout. A real
        # template's look is usually a background image or a bgRef colour --
        # the previous code only caught a plain solidFill, hence "still blank".
        master_name = next((n for n in names
                            if n.startswith("ppt/slideMasters/") and n.endswith(".xml")),
                           None)
        parts = [master_name] if master_name else []
        parts += sorted(n for n in names
                        if n.startswith("ppt/slideLayouts/") and n.endswith(".xml"))

        bg = None
        for part in parts:
            if not part:
                continue
            bg = _extract_bg(zf, part, scheme, theme_root)
            if bg:
                break
        if bg and bg[0] == "color":
            overrides["bg_color"] = bg[1]
        elif bg and bg[0] == "image":
            _, data, ext = bg
            mime = "jpeg" if ext in ("jpg", "jpeg") else ext
            overrides["bg_image"] = "data:image/%s;base64,%s" % (
                mime, base64.b64encode(data).decode("ascii"))
        elif scheme.get("lt1"):
            overrides["bg_color"] = scheme["lt1"]

        # Title / body text styles, and the master's decorative vector shapes.
        if master_name:
            mroot = _zip_xml(zf, master_name)
            if mroot is not None:
                _style_overrides(mroot.find(".//{%s}titleStyle" % _P), scheme,
                                 "title_font_size", "title_color", overrides)
                _style_overrides(mroot.find(".//{%s}bodyStyle" % _P), scheme,
                                 "body_font_size", "text_color", overrides)
            if cx_emu:
                from . import document, ooxml_shapes
                page_w, _ = document.resolve_size(
                    aspect if aspect in ("16:9", "4:3") else "16:9",
                    *(size or (None, None)))
                scale = page_w / cx_emu

                def _resolve(el):
                    return _resolve_color(el, scheme)

                shapes = ooxml_shapes.shapes_svg(
                    zf, master_name, scale, _resolve, _rel_target)
                if shapes is not None:
                    import lxml.etree as _ET
                    overrides["bg_shapes"] = _ET.tostring(shapes).decode("utf-8")

    if "title_color" not in overrides and scheme.get("dk2"):
        overrides["title_color"] = scheme["dk2"]

    return overrides, aspect, size


# ---------------------------------------------------------------------------
# LibreOffice / OpenDocument (.odp)
# ---------------------------------------------------------------------------
def _import_odp(path):
    overrides = {}
    aspect = size = None

    styles_xml = _read_zip_member(path, "styles.xml")
    if styles_xml:
        root = ET.fromstring(styles_xml)

        # Page size from the first page-layout.
        plp = root.find(".//{%s}page-layout-properties" % _STYLE)
        if plp is not None:
            w = _length_px(plp.get("{%s}page-width" % _FO))
            h = _length_px(plp.get("{%s}page-height" % _FO))
            aspect, size = _aspect_for(w, h)

        # Background fill from a drawing-page style.
        for style in root.iter("{%s}drawing-page-properties" % _STYLE):
            fill = style.get("{%s}fill-color" % _DRAW)
            if fill:
                overrides["bg_color"] = _hex(fill)
                break

        # First declared font as a heuristic body font.
        tp = root.find(".//{%s}text-properties" % _STYLE)
        if tp is not None:
            font = tp.get("{%s}font-name" % _STYLE) or tp.get("{%s}font-family" % _FO)
            if font:
                overrides["font_family"] = font.strip("'\"")

    return overrides, aspect, size


def _length_px(value):
    """Convert an ODF length like '25.4cm' / '960px' / '10in' to pixels."""
    if not value:
        return None
    units = {"cm": 96 / 2.54, "mm": 96 / 25.4, "in": 96.0, "px": 1.0, "pt": 96 / 72.0}
    for suffix, factor in units.items():
        if value.endswith(suffix):
            try:
                return float(value[: -len(suffix)]) * factor
            except ValueError:
                return None
    try:
        return float(value)
    except ValueError:
        return None


_PRETTY = {
    "bg_color": "background", "accent_color": "accent",
    "font_family": "font", "title_font_size": "title size",
    "body_font_size": "body size", "title_color": "title colour",
    "text_color": "text colour",
}


def apply_import(pres, path, resize=True, restyle=True):
    """Import a master from ``path`` into ``pres`` and apply it to all slides.

    With ``restyle`` (default) the theme's fonts, sizes and colours are also
    applied to the existing slide text -- like changing the theme in PowerPoint
    -- so the import is immediately visible. Returns a human-readable summary.
    """
    import os

    from . import document, pages, template

    overrides, aspect, size = import_master(path)
    name = os.path.basename(path)
    if not overrides and not aspect:
        return ("No theme information found in %s.\n"
                "The file does not seem to contain a theme or slide master." % name)

    master = template.ensure_master(pres)
    defn = master.definition
    defn.update(overrides)
    defn["label"] = os.path.splitext(name)[0]
    master.definition = defn

    lines = ["Imported theme from %s:" % name]
    for key in sorted(overrides):
        if key == "bg_image":
            lines.append("   background: image from template")
            continue
        if key == "bg_shapes":
            n = overrides[key].count("<ns0:") or overrides[key].count("<rect") \
                + overrides[key].count("<ellipse") + overrides[key].count("<image")
            lines.append("   master graphics: %d shapes" % max(1, n))
            continue
        value = overrides[key]
        if key.endswith("_font_size"):
            value = "%s px" % value
        lines.append("   %s: %s" % (_PRETTY.get(key, key), value))

    if resize and aspect:
        if aspect == "custom" and size:
            w, h = size
        else:
            w, h = document.resolve_size(aspect)
        pres.svg.set("width", str(w))
        pres.svg.set("height", str(h))
        pres.svg.set("viewBox", "0 0 %s %s" % (w, h))
        pres.set_config(C.A_ASPECT, aspect)
        pages.relayout_pages(pres)
        lines.append("   slide size: %s (%g x %g)" % (aspect, w, h))

    template.apply_to_all(pres, defn, restyle=restyle)
    n = pres.slide_count()
    lines.append("Applied to %d slide%s." % (n, "" if n == 1 else "s"))
    return "\n".join(lines)
