"""Slide margin guides.

A margin (a fraction of the slide) defines a safe area. A dashed guide rectangle
is drawn on every slide as an authoring aid; it is a managed element stripped from
the presentation (browser export, PDF, PPTX, raster HTML), so it never shows
during playback -- the same pattern as build badges and placeholder prompts.
"""

from . import constants as C
from . import svgutil as S

MANAGED = "margin"  # pp:managed value marking a margin guide
DEFAULT = 0.06


def get_margin(pres):
    try:
        return float(pres.get_config(C.A_MARGIN, "0") or 0)
    except (TypeError, ValueError):
        return 0.0


def margins_shown(pres):
    return pres.get_config(C.A_SHOW_MARGINS, "true") != "false"


def set_margin(pres, frac, show=True):
    pres.set_config(C.A_MARGIN, "%g" % frac)
    pres.set_config(C.A_SHOW_MARGINS, "true" if show else "false")


def is_margin(el):
    return S.get_pp(el, C.A_MANAGED) == MANAGED


def clear_slide(slide):
    for el in list(slide.layer):
        if is_margin(el):
            slide.layer.remove(el)


def _guide(bbox, frac):
    from inkex import Rectangle

    x, y, w, h = bbox
    mx, my = frac * w, frac * h
    rect = Rectangle(x=str(round(x + mx, 2)), y=str(round(y + my, 2)),
                     width=str(round(w - 2 * mx, 2)),
                     height=str(round(h - 2 * my, 2)))
    rect.style = {"fill": "none", "stroke": "#3b82f6", "stroke-width": "1.5",
                  "stroke-dasharray": "12,8", "opacity": "0.7"}
    S.set_pp(rect, C.A_PH_ROLE, "margin")
    S.set_pp(rect, C.A_MANAGED, MANAGED)
    return rect


def refresh_slide(slide, frac, show):
    clear_slide(slide)
    if show and frac > 0:
        slide.layer.add(_guide(slide.content_bbox, frac))


def refresh(pres):
    """(Re)draw margin guides on every slide per the presentation config."""
    frac = get_margin(pres)
    show = margins_shown(pres)
    count = 0
    for slide in pres.slides():
        refresh_slide(slide, frac, show)
        if show and frac > 0:
            count += 1
    return count


def strip_tree(root):
    """Remove margin guides from an export tree (presentation never shows them)."""
    for el in list(root.iter()):
        if S.get_pp(el, C.A_MANAGED) == MANAGED:
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)
