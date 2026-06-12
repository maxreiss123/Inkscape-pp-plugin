"""Translate a slide master's DrawingML shapes (spTree) into SVG.

Branded templates frequently build their look from vector shapes on the slide
master -- colour bands, rules, accent blocks -- rather than a background picture
or fill. This renders the common subset (auto-shapes with rect/roundRect/ellipse/
line geometry, connectors, pictures and groups, with solid fills and outlines)
into an SVG ``<g>`` so the imported master reproduces that decoration.

Colour resolution and relationship lookup are injected by the caller (so this has
no dependency back on :mod:`mastersimport`). Coordinates are EMU; ``scale`` maps
EMU to our page user units.
"""

import lxml.etree as ET

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"


def _q(ns, tag):
    return "{%s}%s" % (ns, tag)


def _localname(el):
    return ET.QName(el).localname if isinstance(el.tag, str) else None


def _num(el, attr, default=0.0):
    try:
        return float(el.get(attr, default))
    except (TypeError, ValueError):
        return default


def shapes_svg(zf, part_name, scale, resolve_color, rel_target, limit=600):
    """Return an SVG ``<g>`` of the part's spTree shapes, or None if empty."""
    try:
        root = ET.fromstring(zf.read(part_name))
    except KeyError:
        return None
    tree = root.find(".//" + _q(P, "spTree"))
    if tree is None:
        return None
    group = ET.Element(_q(SVG, "g"))
    state = {"count": 0, "limit": limit}
    _walk(zf, part_name, tree, (0.0, 0.0, scale), group,
          resolve_color, rel_target, state)
    return group if len(group) else None


def element_for(zf, part_name, child, tf, resolve_color, rel_target):
    """Translate a single spTree child (sp / cxnSp / pic / grpSp) to SVG.

    Unlike :func:`shapes_svg` this does *not* skip placeholder shapes -- the
    caller decides what to do with placeholders (the presentation importer
    renders their text itself and uses this only for non-text shapes), so z-order
    can be preserved by translating each child in document order. Returns the
    element, or None for empty / unsupported children.
    """
    tag = _localname(child)
    if tag in ("sp", "cxnSp"):
        return _shape(child, tf, resolve_color)
    if tag == "pic":
        return _picture(zf, part_name, child, tf, rel_target)
    if tag == "grpSp":
        ntf = _group_tf(child, tf)
        if ntf is None:
            return None
        group = ET.Element(_q(SVG, "g"))
        state = {"count": 0, "limit": 600}
        _walk(zf, part_name, child, ntf, group, resolve_color, rel_target, state)
        return group if len(group) else None
    return None


def _walk(zf, part_name, node, tf, out, resolve_color, rel_target, state):
    for child in node:
        if state["count"] >= state["limit"]:
            return
        tag = _localname(child)
        if tag in ("sp", "cxnSp"):
            # Placeholders define text styles, not decoration -- skip them.
            if tag == "sp" and child.find(".//" + _q(P, "ph")) is not None:
                continue
            el = _shape(child, tf, resolve_color)
            if el is not None:
                out.append(el)
                state["count"] += 1
        elif tag == "pic":
            el = _picture(zf, part_name, child, tf, rel_target)
            if el is not None:
                out.append(el)
                state["count"] += 1
        elif tag == "grpSp":
            ntf = _group_tf(child, tf)
            if ntf is not None:
                _walk(zf, part_name, child, ntf, out,
                      resolve_color, rel_target, state)


def _xfrm_of(el, container):
    sppr = el.find(_q(P, container))
    if sppr is None:
        return None
    return sppr.find(_q(A, "xfrm"))


def _rect_px(xfrm, tf):
    off = xfrm.find(_q(A, "off"))
    ext = xfrm.find(_q(A, "ext"))
    if off is None or ext is None:
        return None
    ax, ay, s = tf
    x = ax + _num(off, "x") * s
    y = ay + _num(off, "y") * s
    w = _num(ext, "cx") * s
    h = _num(ext, "cy") * s
    return x, y, w, h


def _group_tf(grp, tf):
    xfrm = _xfrm_of(grp, "grpSpPr")
    if xfrm is None:
        return tf
    off = xfrm.find(_q(A, "off"))
    ext = xfrm.find(_q(A, "ext"))
    choff = xfrm.find(_q(A, "chOff"))
    chext = xfrm.find(_q(A, "chExt"))
    if None in (off, ext, choff, chext):
        return tf
    ax, ay, s = tf
    cx = _num(chext, "cx") or 1
    cy = _num(chext, "cy") or 1
    sx = _num(ext, "cx") / cx
    sy = _num(ext, "cy") / cy
    sc = (sx + sy) / 2.0  # keep aspect; masters rarely scale groups non-uniformly
    nax = ax + (_num(off, "x") - _num(choff, "x") * sc) * s
    nay = ay + (_num(off, "y") - _num(choff, "y") * sc) * s
    return (nax, nay, s * sc)


def _fill(shape, resolve_color):
    sppr = shape.find(_q(P, "spPr"))
    if sppr is not None:
        if sppr.find(_q(A, "noFill")) is not None:
            return "none"
        sf = sppr.find(_q(A, "solidFill"))
        if sf is not None:
            return resolve_color(sf) or "none"
        gf = sppr.find(_q(A, "gradFill"))
        if gf is not None:
            return resolve_color(gf) or "none"
    style = shape.find(_q(P, "style"))
    if style is not None:
        fr = style.find(_q(A, "fillRef"))
        if fr is not None:
            return resolve_color(fr) or "none"
    return "none"


def _stroke(shape, resolve_color, scale):
    sppr = shape.find(_q(P, "spPr"))
    ln = sppr.find(_q(A, "ln")) if sppr is not None else None
    if ln is not None:
        if ln.find(_q(A, "noFill")) is not None:
            return None, 0
        color = resolve_color(ln)
        w = _num(ln, "w") * scale or 1.0
        if color:
            return color, w
    style = shape.find(_q(P, "style"))
    if style is not None:
        lr = style.find(_q(A, "lnRef"))
        if lr is not None:
            color = resolve_color(lr)
            if color:
                return color, max(1.0, scale * 9525)
    return None, 0


def _apply_style(el, fill, stroke, sw):
    parts = ["fill:%s" % fill]
    if stroke and sw:
        parts.append("stroke:%s" % stroke)
        parts.append("stroke-width:%s" % round(sw, 2))
    else:
        parts.append("stroke:none")
    el.set("style", ";".join(parts))
    return el


def _shape(shape, tf, resolve_color):
    xfrm = _xfrm_of(shape, "spPr")
    if xfrm is None:
        return None
    rect = _rect_px(xfrm, tf)
    if rect is None:
        return None
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return None
    sppr = shape.find(_q(P, "spPr"))
    geom = sppr.find(_q(A, "prstGeom")) if sppr is not None else None
    prst = geom.get("prst") if geom is not None else "rect"
    fill = _fill(shape, resolve_color)
    stroke, sw = _stroke(shape, resolve_color, tf[2])
    if fill == "none" and not stroke:
        return None  # invisible -- skip

    if prst in ("ellipse", "oval"):
        el = ET.Element(_q(SVG, "ellipse"))
        el.set("cx", str(round(x + w / 2, 2)))
        el.set("cy", str(round(y + h / 2, 2)))
        el.set("rx", str(round(w / 2, 2)))
        el.set("ry", str(round(h / 2, 2)))
    elif prst in ("line", "straightConnector1", "bentConnector2", "bentConnector3"):
        el = ET.Element(_q(SVG, "line"))
        el.set("x1", str(round(x, 2)))
        el.set("y1", str(round(y, 2)))
        el.set("x2", str(round(x + w, 2)))
        el.set("y2", str(round(y + h, 2)))
        if not stroke:
            stroke, sw = fill if fill != "none" else "#000000", max(1.0, sw or 2)
        fill = "none"
    else:  # rect, roundRect, snip*, and unknown -> bounding rectangle
        el = ET.Element(_q(SVG, "rect"))
        el.set("x", str(round(x, 2)))
        el.set("y", str(round(y, 2)))
        el.set("width", str(round(w, 2)))
        el.set("height", str(round(h, 2)))
        if prst and "round" in prst.lower():
            el.set("rx", str(round(min(w, h) * 0.08, 2)))

    _apply_style(el, fill, stroke, sw)
    _maybe_rotate(el, xfrm, x + w / 2, y + h / 2)
    return el


def _maybe_rotate(el, xfrm, cx, cy):
    rot = _num(xfrm, "rot")
    if rot:
        el.set("transform", "rotate(%g %g %g)" % (rot / 60000.0, cx, cy))


def _picture(zf, part_name, pic, tf, rel_target):
    import base64
    import posixpath

    xfrm = _xfrm_of(pic, "spPr")
    if xfrm is None:
        return None
    rect = _rect_px(xfrm, tf)
    if rect is None:
        return None
    blip = pic.find(".//" + _q(A, "blip"))
    if blip is None:
        return None
    embed = blip.get(_q(R, "embed")) or blip.get("embed")
    target = rel_target(zf, part_name, embed) if embed else None
    if not target:
        return None
    try:
        data = zf.read(target)
    except KeyError:
        return None
    ext = posixpath.splitext(target)[1].lstrip(".").lower() or "png"
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    x, y, w, h = rect
    img = ET.Element(_q(SVG, "image"))
    img.set("x", str(round(x, 2)))
    img.set("y", str(round(y, 2)))
    img.set("width", str(round(w, 2)))
    img.set("height", str(round(h, 2)))
    href = "data:image/%s;base64,%s" % (mime, base64.b64encode(data).decode("ascii"))
    img.set(_q(XLINK, "href"), href)
    img.set("href", href)
    _maybe_rotate(img, xfrm, x + w / 2, y + h / 2)
    return img
