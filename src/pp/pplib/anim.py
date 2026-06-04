"""Build / appear animations: reveal objects one click at a time in the player.

Objects carry a ``pp:effect-order`` (the build step, >=1, at which they appear)
and a ``pp:effect-type``. Order 0 / no order means always visible. The browser
player reveals each step on click before advancing to the next slide; Inkscape and
PDF show everything (the correct static fallback).
"""

from . import constants as C
from . import svgutil as S

_CONTENT_TAGS = {
    "{http://www.w3.org/2000/svg}text",
    "{http://www.w3.org/2000/svg}image",
    "{http://www.w3.org/2000/svg}g",
    "{http://www.w3.org/2000/svg}use",
    "{http://www.w3.org/2000/svg}rect",
    "{http://www.w3.org/2000/svg}path",
    "{http://www.w3.org/2000/svg}ellipse",
    "{http://www.w3.org/2000/svg}circle",
    "{http://www.w3.org/2000/svg}polygon",
    "{http://www.w3.org/2000/svg}polyline",
}


def set_effect(el, order, etype):
    S.set_pp(el, C.A_EFFECT_ORDER, int(order))
    S.set_pp(el, C.A_EFFECT_TYPE, etype)


def clear_effect(el):
    S.del_pp(el, C.A_EFFECT_ORDER)
    S.del_pp(el, C.A_EFFECT_TYPE)


def clear_effects_deep(el):
    clear_effect(el)
    for d in el.iter():
        clear_effect(d)


def slide_max_order(slide):
    m = 0
    for el in slide.layer.iter():
        v = S.get_pp(el, C.A_EFFECT_ORDER)
        if v:
            try:
                m = max(m, int(v))
            except ValueError:
                pass
    return m


def _is_content(el):
    return el.tag in _CONTENT_TAGS and S.get_pp(el, C.A_PH_ID) is None


def _top(el):
    try:
        return el.bounding_box().top
    except Exception:
        return 0.0


def split_text_lines(text_el):
    """Split a multi-line TextElement into one TextElement per visual line.

    Returns the new line elements in top-to-bottom order. Used so each bullet of
    a text box can animate separately.
    """
    from inkex import TextElement, Tspan

    parent = text_el.getparent()
    if parent is None:
        return [text_el]
    idx = parent.index(text_el)
    base_x = float(text_el.get("x", 0) or 0)
    base_y = float(text_el.get("y", 0) or 0)
    style = dict(text_el.style)

    def num(v):
        if not v:
            return 0.0
        try:
            return float(str(v).replace("px", ""))
        except ValueError:
            return 0.0

    out = []
    cy = base_y
    tspans = [c for c in text_el if c.tag.endswith("}tspan")]
    if len(tspans) <= 1:
        return [text_el]
    for sp in tspans:
        cy += num(sp.get("dy"))
        x = num(sp.get("x")) if sp.get("x") else base_x
        line = TextElement()
        line.set("x", str(x))
        line.set("y", str(round(cy, 2)))
        line.style = style
        ns = Tspan()
        ns.text = sp.text
        ns.set("x", str(x))
        if sp.style:
            ns.style = dict(sp.style)
        line.add(ns)
        out.append(line)

    for j, line in enumerate(out):
        parent.insert(idx + j, line)
    parent.remove(text_el)
    return out


def resolve_targets(selection, action):
    """Pick the objects to animate from the current selection.

    - bullets: a single multi-line text box is split into per-line objects; a
      single group animates its direct content children.
    - otherwise: the selected objects (a single group expands to its children).
    """
    from inkex import Group, TextElement

    if len(selection) == 1:
        el = selection[0]
        if action == "bullets":
            if isinstance(el, TextElement):
                return split_text_lines(el)
            if isinstance(el, Group):
                kids = [c for c in el if _is_content(c)]
                if len(kids) > 1:
                    return kids
            return [el]
        if isinstance(el, Group):
            kids = [c for c in el if _is_content(c)]
            if len(kids) > 1:
                return kids
        return [el]
    return list(selection)


def apply(targets, start_order, etype, together=False):
    """Assign build orders to ``targets`` (top-to-bottom) and return the count."""
    if together:
        for el in targets:
            set_effect(el, start_order, etype)
        return len(targets)
    ordered = sorted(targets, key=_top)
    for i, el in enumerate(ordered):
        set_effect(el, start_order + i, etype)
    return len(ordered)
