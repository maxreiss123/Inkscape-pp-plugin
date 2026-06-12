"""Turn a slide you designed on the canvas into the slide master.

Authoring a master in a tabbed dialog is fiddly. This lets you instead *draw* a
slide -- background colour or picture, a logo, a colour band, the title/body
text styled how you like -- and promote it to the master with one command, either
for the whole deck or just for slides of the same layout (so a *title* master can
differ from a *content* master).

``capture`` reads the slide's look into a master-definition dict; ``apply`` writes
it onto the master and restyles the deck.
"""

import copy

import lxml.etree as ET

from . import constants as C
from . import svgutil as S

_SVG = "http://www.w3.org/2000/svg"
_XLINK = "http://www.w3.org/1999/xlink"

# Vector shapes worth carrying onto the master as decoration.
_DECOR_TAGS = {"rect", "circle", "ellipse", "path", "line", "polyline",
               "polygon", "g"}


def _f(el, attr):
    try:
        return float(el.get(attr, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _href(el):
    return el.get(_q(_XLINK, "href")) or el.get("href")


def _q(ns, tag):
    return "{%s}%s" % (ns, tag)


def _size_px(text):
    raw = str(text.style.get("font-size", "")).strip()
    if raw.endswith("px"):
        raw = raw[:-2]
    try:
        return max(8, round(float(raw)))
    except ValueError:
        return None


def _localname(el):
    return ET.QName(el).localname if isinstance(el.tag, str) else ""


def capture(pres, slide):
    """Read ``slide``'s visual design into a master-definition overrides dict."""
    from inkex import Image, Rectangle, TextElement

    from . import placeholders as Ph

    w, h = pres.width, pres.height
    page_area = max(1.0, w * h)
    out = {}
    decor = ET.Element(_q(_SVG, "g"))

    for el in slide.layer:
        # Placeholders carry text styles (handled below); master-managed
        # elements are already represented by the definition -- skip both, so we
        # capture only what the user drew on top.
        if S.has_pp(el, C.A_PH_ID) or S.get_pp(el, C.A_MANAGED) == "true":
            continue
        if isinstance(el, Rectangle):
            ew, eh = _f(el, "width"), _f(el, "height")
            fill = el.style.get("fill")
            if ew >= 0.95 * w and eh >= 0.95 * h and fill and fill != "none":
                out["bg_color"] = fill  # topmost full rect = visible background
                continue
        if isinstance(el, Image):
            ew, eh = _f(el, "width"), _f(el, "height")
            href = _href(el)
            if not href:
                continue
            ratio = (ew * eh) / page_area
            if ratio >= 0.9:
                out["bg_image"] = href
            elif ratio < 0.25:
                out["logo_href"] = href
                out["logo_rect"] = [round(_f(el, "x") / w, 4),
                                    round(_f(el, "y") / h, 4),
                                    round(ew / w, 4), round(eh / h, 4)]
            continue
        if isinstance(el, TextElement):
            continue  # free text isn't part of the master
        if _localname(el) in _DECOR_TAGS:
            decor.append(copy.deepcopy(el))

    if len(decor):
        for el in decor.iter():
            S.del_pp(el, C.A_MANAGED)
        out["bg_shapes"] = ET.tostring(decor).decode("utf-8")

    _capture_text_styles(slide, Ph, out)
    return out


def _capture_text_styles(slide, Ph, out):
    for group in slide.placeholders():
        role = S.get_pp(group, C.A_PH_ROLE)
        text = Ph.placeholder_text_el(group)
        if text is None:
            continue
        family = text.style.get("font-family")
        size = _size_px(text)
        fill = text.style.get("fill")
        is_prompt = Ph.is_prompt(group)
        if family:
            out.setdefault("font_family", family)
        if role == C.PhRole.TITLE:
            if size:
                out["title_font_size"] = size
            if fill and not is_prompt:
                out["title_color"] = fill
        elif role == C.PhRole.BODY:
            if size:
                out["body_font_size"] = size
            if fill and not is_prompt:
                out["text_color"] = fill


_PRETTY = {
    "bg_color": "background colour", "bg_image": "background picture",
    "bg_shapes": "decoration", "logo_href": "logo",
    "font_family": "font", "title_font_size": "title size",
    "body_font_size": "body size", "title_color": "title colour",
    "text_color": "text colour",
}


def apply(pres, slide, scope="all"):
    """Promote ``slide`` to the master; return a human-readable summary.

    ``scope`` is ``"all"`` (whole deck) or ``"layout"`` (only this slide's layout).
    """
    from . import template

    overrides = capture(pres, slide)
    if not overrides:
        return ("Nothing to capture from this slide.\n"
                "Add a background, logo or styled title/body text first.")

    master = template.ensure_master(pres)
    defn = master.definition
    layout = slide.layout
    if scope == "layout":
        layers = defn.setdefault("layouts", {})
        layers[layout] = {**layers.get(layout, {}), **overrides}
    else:
        defn.update(overrides)
    master.definition = defn

    template.apply_to_all(pres, defn, restyle=True)

    where = ("the '%s' layout" % _layout_label(layout)
             if scope == "layout" else "every slide")
    lines = ["Set this slide as the master for %s." % where]
    for key in ("bg_image", "bg_color", "bg_shapes", "logo_href",
                "font_family", "title_font_size", "body_font_size",
                "title_color", "text_color"):
        if key in overrides:
            val = overrides[key]
            if key in ("bg_image", "bg_shapes", "logo_href"):
                lines.append("   captured %s" % _PRETTY[key])
            else:
                lines.append("   %s: %s" % (_PRETTY[key], val))
    n = pres.slide_count()
    lines.append("Applied to %d slide%s." % (n, "" if n == 1 else "s"))
    return "\n".join(lines)


def _layout_label(layout_key):
    from . import layouts as L
    try:
        return L.layout_label(layout_key)
    except Exception:
        return layout_key
