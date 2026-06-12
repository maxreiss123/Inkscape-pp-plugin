"""Import a whole PowerPoint presentation (slides *and* content) into the deck.

Each PPTX slide is reproduced **faithfully**: its shapes are translated in
document order (so the stacking / z-order is preserved) and positioned at their
real geometry, which for placeholders is *inherited* from the slide layout and
master (a slide's ``<p:spPr/>`` is usually empty). Text keeps its run font size
and colour; pictures, auto-shapes and groups are translated to native SVG via
:mod:`ooxml_shapes`; the slide's effective background is resolved through the
slide -> slideLayout -> slideMaster chain; and speaker notes are imported.

It reuses the OOXML plumbing from :mod:`mastersimport` (colour-scheme parsing,
relationship resolution, background extraction, theme overrides).
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

# PowerPoint points -> our page user units (1pt = 2px on our 144dpi pages).
_PT_TO_PX = mastersimport._PT_TO_PX
_EMU_PER_PT = 12700.0

_PPTX_EXTS = (".pptx", ".pptm", ".ppsx", ".potx")

# Placeholder types whose dynamic content our own master fields already provide.
_FIELD_PH = {"ftr", "sldNum", "dt"}
# Default font sizes (px) when a placeholder inherits its size.
_DEFAULT_SIZE = {"ctrTitle": 80, "title": 80, "subTitle": 48,
                 "body": 36, "obj": 36}
# Default geometry (page fractions) when geometry can't be resolved.
_DEFAULT_RECT = {
    "ctrTitle": [0.10, 0.36, 0.80, 0.20], "title": [0.06, 0.05, 0.88, 0.15],
    "subTitle": [0.15, 0.60, 0.70, 0.14], "body": [0.06, 0.25, 0.88, 0.66],
    "obj": [0.06, 0.25, 0.88, 0.66],
}


def _q(ns, tag):
    return "{%s}%s" % (ns, tag)


def _num(el, attr):
    try:
        return float(el.get(attr, 0))
    except (TypeError, ValueError):
        return 0.0


def _ph_of(sp):
    return sp.find(_q(_P, "nvSpPr") + "/" + _q(_P, "nvPr") + "/" + _q(_P, "ph"))


def _localname(el):
    return ET.QName(el).localname if isinstance(el.tag, str) else ""


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
    """Return (size_px, colour, bold) from a txBody's first run."""
    if txbody is None:
        return None, None, False
    rpr = txbody.find(".//" + _q(_A, "rPr"))
    if rpr is None:
        return None, None, False
    size_px = None
    if rpr.get("sz"):
        try:
            size_px = round(int(rpr.get("sz")) / 100.0 * _PT_TO_PX)
        except ValueError:
            size_px = None
    color = mastersimport._resolve_color(rpr, scheme)
    bold = rpr.get("b") in ("1", "true")
    return size_px, color, bold


# ---------------------------------------------------------------------------
# Relationships: slide order, and slide -> layout -> master
# ---------------------------------------------------------------------------
def _rel_by_type(zf, part_name, type_suffix):
    if not part_name:
        return None
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
    layout = _rel_by_type(zf, slide_part, "/slideLayout")
    master = _rel_by_type(zf, layout, "/slideMaster") if layout else None
    return layout, master


# ---------------------------------------------------------------------------
# Placeholder geometry inheritance (slide -> layout -> master)
# ---------------------------------------------------------------------------
def _sp_xfrm(sp):
    xfrm = sp.find(_q(_P, "spPr") + "/" + _q(_A, "xfrm"))
    if xfrm is None:
        return None
    off = xfrm.find(_q(_A, "off"))
    ext = xfrm.find(_q(_A, "ext"))
    if off is None or ext is None:
        return None
    return (_num(off, "x"), _num(off, "y"), _num(ext, "cx"), _num(ext, "cy"))


def _norm_type(t):
    return "title" if t in ("ctrTitle", "title") else (t or "body")


def _algn_anchor(sp):
    """Read a shape's horizontal align (algn) and vertical anchor."""
    txbody = sp.find(_q(_P, "txBody"))
    if txbody is None:
        return None, None
    anchor = None
    bodypr = txbody.find(_q(_A, "bodyPr"))
    if bodypr is not None:
        anchor = bodypr.get("anchor")
    algn = None
    para = txbody.find(_q(_A, "p"))
    if para is not None:
        ppr = para.find(_q(_A, "pPr"))
        if ppr is not None:
            algn = ppr.get("algn")
    if algn is None:
        lvl1 = txbody.find(_q(_A, "lstStyle") + "/" + _q(_A, "lvl1pPr"))
        if lvl1 is not None:
            algn = lvl1.get("algn")
    return algn, anchor


def _ph_info_map(zf, part):
    """Map a layout/master's placeholders: {(type, idx): (rect, algn, anchor)}."""
    out = {}
    root = mastersimport._zip_xml(zf, part) if part else None
    if root is None:
        return out
    tree = root.find(".//" + _q(_P, "spTree"))
    if tree is None:
        return out
    for sp in tree.findall(_q(_P, "sp")):
        ph = _ph_of(sp)
        if ph is None:
            continue
        xf = _sp_xfrm(sp)
        algn, anchor = _algn_anchor(sp)
        out[(_norm_type(ph.get("type", "body")), ph.get("idx"))] = (xf, algn, anchor)
    return out


def _match_info(info_map, t, idx):
    if (t, idx) in info_map:
        return info_map[(t, idx)]
    for (gt, gidx), info in info_map.items():
        if idx is not None and gidx == idx:
            return info
    for (gt, gidx), info in info_map.items():
        if gt == t:
            return info
    return None


def _resolve_ph(slide_sp, layout_map, master_map, w, h, scale):
    """Return (geom_pageunits, inherited_algn, inherited_anchor) for a shape.

    Geometry inherits slide -> layout -> master: layout placeholders frequently
    omit ``<a:xfrm>`` and inherit it from the master, so we walk both maps and
    take the first non-empty xfrm / alignment.
    """
    ph = _ph_of(slide_sp)
    t = _norm_type(ph.get("type", "body")) if ph is not None else "body"
    idx = ph.get("idx") if ph is not None else None
    l_info = _match_info(layout_map, t, idx)
    m_info = _match_info(master_map, t, idx)

    inh_algn = (l_info and l_info[1]) or (m_info and m_info[1]) or None
    inh_anchor = (l_info and l_info[2]) or (m_info and m_info[2]) or None

    xf = _sp_xfrm(slide_sp)
    if xf is None and l_info is not None:
        xf = l_info[0]
    if xf is None and m_info is not None:
        xf = m_info[0]
    if xf is None:
        ptype = ph.get("type") if ph is not None else None
        rect = _DEFAULT_RECT.get(ptype or "body", _DEFAULT_RECT["body"])
        return S.frac_rect((0, 0, w, h), rect), inh_algn, inh_anchor
    x, y, cx, cy = xf
    return (x * scale, y * scale, cx * scale, cy * scale), inh_algn, inh_anchor


# ---------------------------------------------------------------------------
# Faithful per-slide content (document order, real geometry)
# ---------------------------------------------------------------------------
def _inherited_size(ptype, defn):
    """Size (px) a placeholder inherits from the template's master text styles."""
    if ptype in ("ctrTitle", "title"):
        return defn.get("title_font_size")
    if ptype == "subTitle":
        ts = defn.get("title_font_size")
        return round(ts * 0.5) if ts else None
    if ptype in ("body", "obj", None):
        return defn.get("body_font_size")
    return None


def _inherited_color(ptype, defn):
    if ptype in ("ctrTitle", "title"):
        return defn.get("title_color") or defn.get("text_color")
    return defn.get("text_color")


def _render_text(slide_sp, geom, scheme, family, defn,
                 inh_algn=None, inh_anchor=None):
    txbody = slide_sp.find(_q(_P, "txBody"))
    lines = _txbody_lines(txbody)
    if not lines:
        return None
    x, y, w, h = geom
    ph = _ph_of(slide_sp)
    ptype = ph.get("type", "body") if ph is not None else None

    # Run formatting wins; otherwise inherit the template's master style for this
    # placeholder type (real decks rarely set sz/colour on every run), then a
    # sensible default.
    size_px, color, bold = _run_format(txbody, scheme)
    fs = size_px or _inherited_size(ptype, defn) or _DEFAULT_SIZE.get(ptype, 24)
    default_color = _inherited_color(ptype, defn) or "#000000"

    own_algn, own_anchor = _algn_anchor(slide_sp)
    algn = own_algn or inh_algn
    anchor = {"ctr": "middle", "r": "end"}.get(algn, "start")
    tx = x + (w / 2 if anchor == "middle" else (w if anchor == "end" else 0))

    bullets = ph is not None and ptype in ("body", "obj")
    line_h = fs * 1.2
    total = line_h * len(lines)
    # Vertical anchor from bodyPr (t / ctr / b), inherited if not on the slide.
    vanchor = own_anchor or inh_anchor
    if vanchor == "ctr":
        ty = y + max(0, (h - total) / 2) + fs
    elif vanchor == "b":
        ty = y + max(0, h - total) + fs
    else:
        ty = y + fs

    text = S.make_text(tx, ty, lines, fs, anchor=anchor,
                       fill=color or default_color, family=family,
                       bullets=bullets)
    if bold:
        text.style["font-weight"] = "bold"
    return text


def _render_slide(zf, slide_part, layout_part, master_part, scale, scheme,
                  family, defn, w, h):
    """Return ordered native elements for a slide's spTree, preserving z-order."""
    root = mastersimport._zip_xml(zf, slide_part)
    if root is None:
        return [], 0, 0
    tree = root.find(".//" + _q(_P, "spTree"))
    if tree is None:
        return [], 0, 0

    layout_map = _ph_info_map(zf, layout_part)
    master_map = _ph_info_map(zf, master_part)

    def resolve(el):
        return mastersimport._resolve_color(el, scheme)

    def shape_of(child):
        return ooxml_shapes.element_for(
            zf, slide_part, child, (0.0, 0.0, scale), resolve,
            mastersimport._rel_target)

    out = []
    texts = shapes = 0
    for child in tree:
        tag = _localname(child)
        if tag == "sp":
            ph = _ph_of(child)
            ptype = ph.get("type") if ph is not None else None
            if ptype in _FIELD_PH:
                continue  # footer / number / date -> our own fields
            txbody = child.find(_q(_P, "txBody"))
            has_text = txbody is not None and _txbody_lines(txbody)
            geom = _resolve_ph(child, layout_map, master_map, w, h, scale)

            # 1. The shape body: a picture fill (full-bleed background etc.), a
            #    solid/gradient auto-shape, else nothing for an empty placeholder.
            sppr = child.find(_q(_P, "spPr"))
            blipfill = sppr.find(_q(_A, "blipFill")) if sppr is not None else None
            if blipfill is not None:
                el = ooxml_shapes.image_at(zf, slide_part, blipfill, geom[0],
                                           mastersimport._rel_target)
                if el is not None:
                    out.append(el)
                    shapes += 1
            elif ph is None or not has_text:
                el = shape_of(child)
                if el is not None:
                    out.append(el)
                    shapes += 1
            # 2. The text label on top (placeholders or labelled shapes).
            if has_text:
                el = _render_text(child, geom[0], scheme, family, defn,
                                  geom[1], geom[2])
                if el is not None:
                    out.append(el)
                    texts += 1
        elif tag == "pic":
            el = shape_of(child)
            if el is None:  # placeholder picture: geometry is inherited
                geom = _resolve_ph(child, layout_map, master_map, w, h, scale)
                el = ooxml_shapes.image_at(zf, slide_part, child, geom[0],
                                           mastersimport._rel_target)
            if el is not None:
                out.append(el)
                shapes += 1
        elif tag in ("grpSp", "cxnSp"):
            el = shape_of(child)
            if el is not None:
                out.append(el)
                shapes += 1
    return out, texts, shapes


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

        # 1. A presentation document carrying the imported theme essentials
        #    (base colour, fonts) but not the global bg picture/shapes -- those
        #    are resolved per slide below.
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

        count = objs = bgs = noted = 0
        for part in parts:
            # Slides are imported faithfully (blank layout, no injected
            # placeholders) so original positions and stacking survive.
            slide = pages.add_slide(pres, C.LayoutKey.BLANK)
            layout_part, master_part = _chain(zf, part)

            bg = _background_group(zf, part, layout_part, master_part,
                                   scale, scheme, theme_root, w, h)
            if bg is not None:
                slide.layer.insert(1, bg)  # above base colour, below content
                bgs += 1

            els, texts, shapes = _render_slide(
                zf, part, layout_part, master_part, scale, scheme,
                family, defn, w, h)
            for el in els:  # appended in document order -> z-order preserved
                slide.layer.append(el)
            objs += texts + shapes

            if import_notes:
                ntext = _notes_text(zf, part)
                if ntext:
                    notes.set_notes(slide, ntext)
                    noted += 1
            count += 1

        if pres.slide_count() == 0:
            pages.add_slide(pres, C.LayoutKey.TITLE)
        pages.relayout_pages(pres)

    return count, _summary(name, count, objs, bgs, noted, aspect, overrides)


def _summary(name, count, objs, bgs, noted, aspect, overrides):
    lines = ["Imported %d slide%s from %s." % (count, "" if count == 1 else "s", name)]
    if aspect:
        lines.append("   slide size: %s" % aspect)
    if bgs:
        lines.append("   slide backgrounds: %d" % bgs)
    if objs:
        lines.append("   objects (text / pictures / shapes): %d" % objs)
    if noted:
        lines.append("   speaker notes on %d slide%s" % (noted, "" if noted == 1 else "s"))
    if overrides.get("font_family"):
        lines.append("   font: %s" % overrides["font_family"])
    return "\n".join(lines)
