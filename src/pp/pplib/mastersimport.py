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
    if lower.endswith(".pptx"):
        return _import_pptx(path)
    if lower.endswith(".odp"):
        return _import_odp(path)
    raise ValueError("Unsupported file type (use .pptx or .odp): %s" % path)


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


def _import_pptx(path):
    overrides = {}
    aspect = size = None

    pres_xml = _read_zip_member(path, "ppt/presentation.xml")
    if pres_xml:
        root = ET.fromstring(pres_xml)
        sldsz = root.find("{%s}sldSz" % _P)
        if sldsz is not None:
            try:
                cx = float(sldsz.get("cx")) / EMU_PER_PX
                cy = float(sldsz.get("cy")) / EMU_PER_PX
                aspect, size = _aspect_for(cx, cy)
            except (TypeError, ValueError):
                pass

    theme_xml = _first_member(
        path, lambda n: n.startswith("ppt/theme/") and n.endswith(".xml"))
    if theme_xml:
        root = ET.fromstring(theme_xml)
        scheme = root.find(".//{%s}clrScheme" % _A)
        if scheme is not None:
            bg = _clr_value(scheme.find("{%s}lt1" % _A))
            accent = _clr_value(scheme.find("{%s}accent1" % _A))
            if bg:
                overrides["bg_color"] = bg
            if accent:
                overrides["accent_color"] = accent
        font_scheme = root.find(".//{%s}fontScheme" % _A)
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


def apply_import(pres, path, resize=True):
    """Import a master from ``path`` into ``pres`` and apply it to all slides.

    Returns a short human-readable summary of what was imported.
    """
    from . import document, pages, template

    overrides, aspect, size = import_master(path)
    master = template.ensure_master(pres)
    defn = master.definition
    defn.update(overrides)
    defn["label"] = "Imported"
    master.definition = defn

    summary = ["Imported theme: " + ", ".join(sorted(overrides)) if overrides
               else "No theme attributes found"]

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
        summary.append("size %s (%gx%g)" % (aspect, w, h))

    template.apply_to_all(pres, defn)
    return "; ".join(summary)
