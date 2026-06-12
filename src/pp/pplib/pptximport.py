"""Import a whole PowerPoint presentation (slides *and* content) into the deck.

Where :mod:`mastersimport` reads only a template's *theme* (size, master
background, fonts, colours), this module reads the actual **slides**: their
order, the title / subtitle / bullet text in placeholders, free-floating text
boxes, pictures and decorative shapes, the speaker notes -- and, crucially, the
**effective background of each slide** resolved through the
slide -> slideLayout -> slideMaster chain (where branded templates actually keep
their background pictures and colour bands). Per-run font sizes and colours are
honoured too, so a slide's text looks the way it did in PowerPoint.

It reuses the OOXML plumbing proven by the master import (``mastersimport`` for
colour-scheme parsing / relationship resolution / background extraction, and
:mod:`ooxml_shapes` to translate DrawingML shapes and pictures to SVG).
Placeholder *text* is mapped onto our layouts so it stays editable.
"""

import base64
import os
import posixpath
import zipfile

import lxml.etree as ET

from . import constants as C
from . import mastersimport, ooxml_shapes
from . import svgutil as S

_A = mastersimport._A
_P = mastersimport._P
_R = mastersimport._R
_SVG = "http://www.w3.org/2000/svg"
_XLINK = "http://www.w3.org/1999/xlink"

# PowerPoint points -> our page user units (our pages are 144dpi-equivalent, so
# 1pt = 2px); shared with mastersimport.
_PT_TO_PX = mastersimport._PT_TO_PX

_PPTX_EXTS = (".pptx", ".pptm", ".ppsx", ".potx")


def _q(ns, tag):
    return "{%s}%s" % (ns, tag)


def _ph_of(sp):
    """Return the ``<p:ph>`` placeholder element of a shape, or None."""
    return sp.find(_q(_P, "nvSpPr") + "/" + _q(_P, "nvPr") + "/" + _q(_P, "ph"))


def _txbody_lines(txbody):
    """Return the non-empty paragraph lines of a ``<p:txBody>`` (one per a:p)."""
    if txbody is None:
        return []
    lines = []
    for para in txbody.findall(_q(_A, "p")):
        runs = [t.text for t in para.iter(_q(_A, "t")) if t.text]
        lines.append("".join(runs))
    while lines and lines[-1].strip() == "":
        lines.pop()
    return [ln for ln in lines if ln.strip() != ""]


def _run_format(txbody, scheme):
    """Return (font_size_px, colour) from a txBody's first run, or (None, None)."""
    if txbody is None:
        return None, None
    rpr = txbody.find(".//" + _q(_A, "rPr"))
    if rpr is None:
        return None, None
    size_px = None
    if rpr.get("sz"):
        try:
            size_px = round(int(rpr.get("sz")) / 100.0 * _PT_TO_PX)
        except ValueError:
            size_px = None
    color = mastersimport._resolve_color(rpr, scheme)
    return size_px, color


def _num(el, attr):
    try:
        return float(el.get(attr, 0))
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Relationships: slide order, and slide -> layout -> master
# ---------------------------------------------------------------------------
def _rel_by_type(zf, part_name, type_suffix):
    d, base = posixpath.split(part_name)
    rels_name = posixpath.join(d, "_rels", base + ".rels")
    try:
        rels = ET.fromstring(zf.read(rels_name))
    except KeyError:
        return None
    for rel in rels:
        if rel.get("Type", "").endswith(type_suffix):
            target = rel.get("Target", "")
            if target.startswith("/"):
                return target.lstrip("/")
            return posixpath.normpath(posixpath.join(d, target))
    return None


def _slide_parts(zf):
    """Resolve presentation.xml's sldIdLst to ordered slide part paths."""
    root = mastersimport._zip_xml(zf, "ppt/presentation.xml")
    if root is None:
        return []
    lst = root.find(_q(_P, "sldIdLst"))
    if lst is None:
        return []
    parts = []
    for sld in lst.findall(_q(_P, "sldId")):
        rid = sld.get(_q(_R, "id")) or sld.get("r:id")
        if not rid:
            continue
        target = mastersimport._rel_target(zf, "ppt/presentation.xml", rid)
        if target:
            parts.append(target)
    return parts


def _chain(zf, slide_part):
    """Return (layout_part, master_part) for a slide, either may be None."""
    layout = _rel_by_type(zf, slide_part, "/slideLayout")
    master = _rel_by_type(zf, layout, "/slideMaster") if layout else None
    return layout, master


# ---------------------------------------------------------------------------
# Per-slide placeholder text + formatting
# ---------------------------------------------------------------------------
def _placeholders(zf, part, scheme):
    """Return [{kind, lines, size_px, color}] for a slide's placeholders."""
    root = mastersimport._zip_xml(zf, part)
    if root is None:
        return None
    tree = root.find(".//" + _q(_P, "spTree"))
    if tree is None:
        return []
    out = []
    for sp in tree.findall(_q(_P, "sp")):
        ph = _ph_of(sp)
        if ph is None:
            continue
        txbody = sp.find(_q(_P, "txBody"))
        size_px, color = _run_format(txbody, scheme)
        out.append({
            "kind": ph.get("type", "body"),
            "lines": _txbody_lines(txbody),
            "size_px": size_px,
            "color": color,
        })
    return out


def _classify(phs):
    title = subtitle = None
    bodies = []
    for ph in phs:
        kind = ph["kind"]
        if kind in ("ctrTitle", "title"):
            title = ph
        elif kind == "subTitle":
            subtitle = ph
        elif kind in ("ftr", "sldNum", "dt"):
            continue
        elif ph["lines"]:
            bodies.append(ph)
    return title, subtitle, bodies


def _choose_layout(title, subtitle, bodies):
    if subtitle and not bodies:
        return C.LayoutKey.TITLE
    if len(bodies) >= 2:
        return C.LayoutKey.TWO_CONTENT
    if bodies or title:
        return C.LayoutKey.TITLE_CONTENT
    return C.LayoutKey.BLANK


def _format_text(text_el, family, size_px, color):
    from . import template
    if family:
        text_el.style["font-family"] = family
    if size_px:
        template._set_text_size(text_el, size_px)
    if color:
        text_el.style["fill"] = color


def _populate(slide, title, subtitle, bodies, defn):
    """Fill placeholders with text, honouring per-run size / colour."""
    from . import placeholders as Ph

    family = defn.get("font_family")
    title_sz = defn.get("title_font_size")
    body_sz = defn.get("body_font_size")
    title_clr = defn.get("title_color")
    text_clr = defn.get("text_color")

    def put(ph_id, ph, size_default, color_default):
        if ph is None or not ph["lines"]:
            return
        group = slide.placeholder(ph_id)
        if group is None:
            return
        Ph.set_placeholder_text(group, ph["lines"], bullets=ph_id != "title"
                                and ph_id != "subtitle")
        text = Ph.placeholder_text_el(group)
        _format_text(text, family, ph["size_px"] or size_default,
                     ph["color"] or color_default)

    put("title", title, title_sz, title_clr)
    sub_default = round(title_sz * 0.5) if title_sz else None
    put("subtitle", subtitle, sub_default, text_clr)
    if slide.layout == C.LayoutKey.TWO_CONTENT:
        for ph_id, ph in zip(("content-left", "content-right"), bodies):
            put(ph_id, ph, body_sz, text_clr)
    elif bodies:
        # Merge multiple body blocks into the single body placeholder.
        merged = {"lines": [], "size_px": bodies[0]["size_px"],
                  "color": bodies[0]["color"]}
        for b in bodies:
            merged["lines"].extend(b["lines"])
        put("body", merged, body_sz, text_clr)


# ---------------------------------------------------------------------------
# Effective per-slide background (slide -> layout -> master)
# ---------------------------------------------------------------------------
def _full_rect(w, h, color):
    rect = ET.Element(_q(_SVG, "rect"))
    rect.set("x", "0")
    rect.set("y", "0")
    rect.set("width", str(w))
    rect.set("height", str(h))
    rect.set("style", "fill:%s;stroke:none" % color)
    return rect


def _full_image(w, h, data, ext):
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    href = "data:image/%s;base64,%s" % (mime, base64.b64encode(data).decode("ascii"))
    img = ET.Element(_q(_SVG, "image"))
    img.set("x", "0")
    img.set("y", "0")
    img.set("width", str(w))
    img.set("height", str(h))
    img.set("preserveAspectRatio", "xMidYMid slice")
    img.set(_q(_XLINK, "href"), href)
    img.set("href", href)
    return img


def _pbg_element(zf, part, scheme, theme_root, w, h):
    """Return a full-slide <image>/<rect> for a part's <p:bg>, or None."""
    if not part:
        return None
    bg = mastersimport._extract_bg(zf, part, scheme, theme_root)
    if not bg:
        return None
    if bg[0] == "image":
        return _full_image(w, h, bg[1], bg[2])
    if bg[0] == "color" and bg[1] and bg[1].upper() != "#FFFFFF":
        return _full_rect(w, h, bg[1])
    return None


def _background_group(zf, slide_part, layout_part, master_part,
                      scale, scheme, theme_root, w, h):
    """Composite the slide's effective background into a managed-free <g>.

    Order (back to front): master/layout/slide <p:bg> fill or picture, then the
    master's and layout's decorative shapes / pictures from their spTree.
    """
    def resolve(el):
        return mastersimport._resolve_color(el, scheme)

    group = ET.Element(_q(_SVG, "g"))

    for part in (master_part, layout_part, slide_part):
        el = _pbg_element(zf, part, scheme, theme_root, w, h)
        if el is not None:
            group.append(el)

    for part in (master_part, layout_part):
        if not part:
            continue
        shapes = ooxml_shapes.shapes_svg(
            zf, part, scale, resolve, mastersimport._rel_target)
        if shapes is not None:
            for child in shapes:
                group.append(child)

    if len(group) == 0:
        return None
    S.set_pp(group, C.A_PH_ROLE, C.PhRole.BACKGROUND)
    S.set_pp(group, "imported", "true")
    return group


# ---------------------------------------------------------------------------
# Free text boxes (non-placeholder) -> native SVG text
# ---------------------------------------------------------------------------
def _text_boxes(zf, part, scale, scheme, default_color, family):
    """Translate non-placeholder text boxes to inkex text elements."""
    root = mastersimport._zip_xml(zf, part)
    if root is None:
        return []
    tree = root.find(".//" + _q(_P, "spTree"))
    if tree is None:
        return []
    out = []
    for sp in tree.findall(_q(_P, "sp")):
        if _ph_of(sp) is not None:
            continue  # placeholders already mapped to layout text
        txbody = sp.find(_q(_P, "txBody"))
        lines = _txbody_lines(txbody)
        if not lines:
            continue
        xfrm = sp.find(_q(_P, "spPr") + "/" + _q(_A, "xfrm"))
        if xfrm is None:
            continue
        off = xfrm.find(_q(_A, "off"))
        if off is None:
            continue
        x = _num(off, "x") * scale
        y = _num(off, "y") * scale
        size_px, color = _run_format(txbody, scheme)
        font_px = max(8.0, size_px or 36)
        text = S.make_text(x, y + font_px, lines, font_px,
                           fill=color or default_color, family=family)
        out.append(text)
    return out


# ---------------------------------------------------------------------------
# Speaker notes
# ---------------------------------------------------------------------------
def _notes_text(zf, part):
    notes_part = _rel_by_type(zf, part, "/notesSlide")
    if not notes_part:
        return ""
    root = mastersimport._zip_xml(zf, notes_part)
    if root is None:
        return ""
    for sp in root.iter(_q(_P, "sp")):
        ph = _ph_of(sp)
        if ph is not None and ph.get("type") == "body":
            lines = _txbody_lines(sp.find(_q(_P, "txBody")))
            if lines:
                return "\n".join(lines)
    return ""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def import_presentation(pres, path, replace=True, import_notes=True):
    """Import every slide of ``path`` into ``pres``; return (count, summary)."""
    from . import document, notes, pages, template

    if not path.lower().endswith(_PPTX_EXTS):
        raise ValueError(
            "Import PPTX Presentation reads PowerPoint .pptx / .pptm / .ppsx "
            "(or .potx) files.\nFor LibreOffice .odp use Import Master.")

    overrides, aspect, size = mastersimport.import_master(path)
    name = os.path.basename(path)

    with zipfile.ZipFile(path) as zf:
        parts = _slide_parts(zf)

        scheme = {}
        theme_root = None
        theme_name = next((n for n in zf.namelist()
                           if n.startswith("ppt/theme/") and n.endswith(".xml")),
                          None)
        if theme_name:
            theme_root = mastersimport._zip_xml(zf, theme_name)
            scheme = mastersimport._parse_scheme(theme_root)

        cx_emu = None
        proot = mastersimport._zip_xml(zf, "ppt/presentation.xml")
        if proot is not None:
            sldsz = proot.find(_q(_P, "sldSz"))
            if sldsz is not None:
                try:
                    cx_emu = float(sldsz.get("cx"))
                except (TypeError, ValueError):
                    cx_emu = None

        # 1. A presentation document carrying the imported theme. The master
        #    keeps the theme essentials (base colour, fonts, sizes) but NOT the
        #    global bg picture/shapes -- those are resolved per slide below.
        if not pres.is_initialized():
            document.init_presentation(
                pres,
                aspect=aspect if aspect in ("16:9", "4:3") else "16:9",
                first_layout=C.LayoutKey.BLANK)
        master = template.ensure_master(pres)
        defn = master.definition
        defn.update({k: v for k, v in overrides.items()
                     if k not in ("bg_image", "bg_shapes")})
        defn["label"] = os.path.splitext(name)[0]
        master.definition = defn

        # 2. Match the slide size / aspect.
        if aspect:
            if aspect == "custom" and size:
                w, h = size
            else:
                w, h = document.resolve_size(aspect)
            pres.svg.set("width", str(w))
            pres.svg.set("height", str(h))
            pres.svg.set("viewBox", "0 0 %s %s" % (w, h))
            pres.set_config(C.A_ASPECT, aspect)
            pages.relayout_pages(pres)

        # 3. Replace existing slides if asked (default).
        if replace:
            for slide in list(pres.slides()):
                pages.delete_slide(pres, slide)

        w, h = pres.width, pres.height
        scale = (w / cx_emu) if cx_emu else 1.0
        family = defn.get("font_family", "sans-serif")
        text_color = defn.get("text_color", "#000000")

        def resolve(el):
            return mastersimport._resolve_color(el, scheme)

        count = pics = boxes = noted = bgs = 0
        for part in parts:
            phs = _placeholders(zf, part, scheme)
            if phs is None:
                continue
            title, subtitle, bodies = _classify(phs)
            slide = pages.add_slide(pres, _choose_layout(title, subtitle, bodies))
            _populate(slide, title, subtitle, bodies, defn)

            # Effective background (slide -> layout -> master): the usual home of
            # a branded template's background picture / colour bands.
            layout_part, master_part = _chain(zf, part)
            bg = _background_group(zf, part, layout_part, master_part,
                                   scale, scheme, theme_root, w, h)
            if bg is not None:
                slide.layer.insert(1, bg)  # above the base colour, below content
                bgs += 1

            # Slide-level pictures / shapes (charts, photos, callouts).
            shapes = ooxml_shapes.shapes_svg(
                zf, part, scale, resolve, mastersimport._rel_target)
            if shapes is not None:
                S.set_pp(shapes, C.A_PH_ROLE, "imported")
                slide.layer.append(shapes)
                pics += len(shapes)

            for tb in _text_boxes(zf, part, scale, scheme, text_color, family):
                slide.layer.append(tb)
                boxes += 1

            if import_notes:
                ntext = _notes_text(zf, part)
                if ntext:
                    notes.set_notes(slide, ntext)
                    noted += 1
            count += 1

        if pres.slide_count() == 0:
            pages.add_slide(pres, C.LayoutKey.TITLE)
        pages.relayout_pages(pres)

    return count, _summary(name, count, pics, boxes, noted, bgs, aspect, overrides)


def _summary(name, count, pics, boxes, noted, bgs, aspect, overrides):
    lines = ["Imported %d slide%s from %s." % (count, "" if count == 1 else "s", name)]
    if aspect:
        lines.append("   slide size: %s" % aspect)
    if bgs:
        lines.append("   slide backgrounds: %d" % bgs)
    if pics:
        lines.append("   pictures / shapes: %d" % pics)
    if boxes:
        lines.append("   text boxes: %d" % boxes)
    if noted:
        lines.append("   speaker notes on %d slide%s" % (noted, "" if noted == 1 else "s"))
    if overrides.get("font_family"):
        lines.append("   font: %s" % overrides["font_family"])
    return "\n".join(lines)
