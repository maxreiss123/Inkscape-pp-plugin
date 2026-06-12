"""Import a whole PowerPoint presentation (slides *and* content) into the deck.

Where :mod:`mastersimport` reads only a template's *theme* (size, master
background, fonts, colours), this module reads the actual **slides**: their
order, the title / subtitle / bullet text in placeholders, free-floating text
boxes, pictures and decorative shapes, and the speaker notes -- and rebuilds
them as native slides in our model so they render in Inkscape, PDF and every
export.

It deliberately reuses the OOXML plumbing already proven by the master import:
``mastersimport`` for colour-scheme parsing / relationship resolution and the
theme overrides, and :mod:`ooxml_shapes` to translate DrawingML shapes and
pictures to SVG. Placeholder *text* is mapped onto our layouts (title /
title+content / two-content) so it stays editable and theme-restyleable; the
master/theme is applied on top so the imported deck immediately looks right.
"""

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

# 1 point = 12700 EMU; our EMU->page scale already folds in the page size, so a
# point size becomes page units via pt * EMU_PER_PT * scale.
_EMU_PER_PT = 12700.0

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


# ---------------------------------------------------------------------------
# Slide order and per-slide text
# ---------------------------------------------------------------------------
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


def _slide_text(zf, part):
    """Return (title_lines, subtitle_lines, [body_blocks]) for a slide part."""
    root = mastersimport._zip_xml(zf, part)
    if root is None:
        return None
    tree = root.find(".//" + _q(_P, "spTree"))
    if tree is None:
        return [], [], []
    title = subtitle = None
    bodies = []
    for sp in tree.findall(_q(_P, "sp")):
        ph = _ph_of(sp)
        if ph is None:
            continue
        lines = _txbody_lines(sp.find(_q(_P, "txBody")))
        kind = ph.get("type", "body")
        if kind in ("ctrTitle", "title"):
            title = lines
        elif kind == "subTitle":
            subtitle = lines
        elif kind in ("ftr", "sldNum", "dt"):
            continue  # handled by our own footer / number / date fields
        elif lines:
            bodies.append(lines)
    return title or [], subtitle or [], bodies


def _choose_layout(title, subtitle, bodies):
    if subtitle and not bodies:
        return C.LayoutKey.TITLE
    if len(bodies) >= 2:
        return C.LayoutKey.TWO_CONTENT
    if bodies or title:
        return C.LayoutKey.TITLE_CONTENT
    return C.LayoutKey.BLANK


def _populate(slide, title, subtitle, bodies):
    from . import placeholders as Ph

    if title:
        g = slide.placeholder("title")
        if g is not None:
            Ph.set_placeholder_text(g, title)
    if subtitle:
        g = slide.placeholder("subtitle")
        if g is not None:
            Ph.set_placeholder_text(g, subtitle)
    if slide.layout == C.LayoutKey.TWO_CONTENT:
        for ph_id, lines in zip(("content-left", "content-right"), bodies):
            g = slide.placeholder(ph_id)
            if g is not None:
                Ph.set_placeholder_text(g, lines, bullets=True)
    elif bodies:
        g = slide.placeholder("body")
        if g is not None:
            merged = []
            for block in bodies:
                merged.extend(block)
            Ph.set_placeholder_text(g, merged, bullets=True)


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
        rpr = txbody.find(".//" + _q(_A, "rPr"))
        sz = None
        if rpr is not None and rpr.get("sz"):
            try:
                sz = int(rpr.get("sz"))
            except ValueError:
                sz = None
        font_px = max(8.0, (sz or 1800) / 100.0 * _EMU_PER_PT * scale)
        color = mastersimport._resolve_color(rpr, scheme) if rpr is not None else None
        text = S.make_text(x, y + font_px, lines, round(font_px, 1),
                           fill=color or default_color, family=family)
        out.append(text)
    return out


def _num(el, attr):
    try:
        return float(el.get(attr, 0))
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Speaker notes
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
# Main entry points
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
        theme_name = next((n for n in zf.namelist()
                           if n.startswith("ppt/theme/") and n.endswith(".xml")),
                          None)
        if theme_name:
            scheme = mastersimport._parse_scheme(
                mastersimport._zip_xml(zf, theme_name))

        cx_emu = None
        proot = mastersimport._zip_xml(zf, "ppt/presentation.xml")
        if proot is not None:
            sldsz = proot.find(_q(_P, "sldSz"))
            if sldsz is not None:
                try:
                    cx_emu = float(sldsz.get("cx"))
                except (TypeError, ValueError):
                    cx_emu = None

        # 1. A presentation document carrying the imported master/theme.
        if not pres.is_initialized():
            document.init_presentation(
                pres,
                aspect=aspect if aspect in ("16:9", "4:3") else "16:9",
                first_layout=C.LayoutKey.BLANK)
        master = template.ensure_master(pres)
        defn = master.definition
        defn.update(overrides)
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

        scale = (pres.width / cx_emu) if cx_emu else 1.0
        family = defn.get("font_family", "sans-serif")
        text_color = defn.get("text_color", "#000000")

        def _resolve(el):
            return mastersimport._resolve_color(el, scheme)

        count = pics = boxes = noted = 0
        for part in parts:
            info = _slide_text(zf, part)
            if info is None:
                continue
            title, subtitle, bodies = info
            slide = pages.add_slide(pres, _choose_layout(title, subtitle, bodies))
            _populate(slide, title, subtitle, bodies)

            shapes = ooxml_shapes.shapes_svg(
                zf, part, scale, _resolve, mastersimport._rel_target)
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

        # Apply the theme to the freshly populated text (fonts, sizes, colours)
        # so dark-master decks get readable, on-theme text rather than black.
        template.apply_to_all(pres, defn, restyle=True)
        pages.relayout_pages(pres)

    return count, _summary(name, count, pics, boxes, noted, aspect, overrides)


def _summary(name, count, pics, boxes, noted, aspect, overrides):
    lines = ["Imported %d slide%s from %s." % (count, "" if count == 1 else "s", name)]
    if aspect:
        lines.append("   slide size: %s" % aspect)
    if pics:
        lines.append("   pictures / shapes: %d" % pics)
    if boxes:
        lines.append("   text boxes: %d" % boxes)
    if noted:
        lines.append("   speaker notes on %d slide%s" % (noted, "" if noted == 1 else "s"))
    extras = []
    if "bg_image" in overrides:
        extras.append("background image")
    if "bg_shapes" in overrides:
        extras.append("master graphics")
    if overrides.get("bg_color", "#FFFFFF").upper() != "#FFFFFF":
        extras.append("background colour")
    if overrides.get("font_family"):
        extras.append("font %s" % overrides["font_family"])
    if extras:
        lines.append("   theme applied: %s" % ", ".join(extras))
    return "\n".join(lines)
