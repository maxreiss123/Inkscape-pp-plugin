"""Presentation document initialisation (used by the Setup command)."""

from . import constants as C
from . import pages, template
from . import svgutil as S


def resolve_size(aspect, width=None, height=None):
    """Return (width, height) in user units for an aspect choice."""
    if aspect in C.ASPECT_SIZES:
        return C.ASPECT_SIZES[aspect]
    # custom
    w = float(width or C.ASPECT_SIZES["16:9"][0])
    h = float(height or C.ASPECT_SIZES["16:9"][1])
    return (w, h)


def init_presentation(pres, aspect="16:9", width=None, height=None,
                      footer_text="", date_mode=C.DateMode.NONE,
                      date_value="", author="", first_layout=C.LayoutKey.TITLE):
    """Turn the current SVG into a presentation document.

    Sets the canvas size/viewBox, writes presentation config, creates the
    default master and one starting slide. Returns the first :class:`Slide`.
    """
    w, h = resolve_size(aspect, width, height)
    svg = pres.svg

    # Canvas size + viewBox in user units.
    svg.set("width", str(w))
    svg.set("height", str(h))
    svg.set("viewBox", "0 0 %s %s" % (w, h))

    S.set_pp(svg, C.A_ROLE, C.Role.PRESENTATION)
    pres.set_config(C.A_ASPECT, aspect)
    pres.set_config(C.A_FOOTER_TEXT, footer_text)
    pres.set_config(C.A_DATE_MODE, date_mode)
    pres.set_config(C.A_DATE_VALUE, date_value)
    pres.set_config(C.A_AUTHOR, author)

    template.ensure_master(pres)
    slide = pages.add_slide(pres, first_layout)
    return slide
