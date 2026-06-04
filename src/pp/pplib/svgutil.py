"""Small SVG / geometry / metadata helpers shared across the plugin."""

import uuid

from . import constants as C


# ---------------------------------------------------------------------------
# Namespaced metadata accessors
# ---------------------------------------------------------------------------
def set_pp(el, name, value):
    """Set a plugin metadata attribute (in the PP namespace)."""
    el.set(C.cn(name), str(value))


def get_pp(el, name, default=None):
    """Read a plugin metadata attribute, returning ``default`` if absent."""
    val = el.get(C.cn(name))
    return default if val is None else val


def has_pp(el, name):
    return el.get(C.cn(name)) is not None


def del_pp(el, name):
    key = C.cn(name)
    if el.get(key) is not None:
        del el.attrib[key]


# ---------------------------------------------------------------------------
# Ids
# ---------------------------------------------------------------------------
def uuid_slide_id():
    """Return a short stable id used to link a slide layer to its page."""
    return "pp-" + uuid.uuid4().hex[:12]


def new_id(svg, prefix):
    """Return an id that is unique within ``svg`` for the given prefix."""
    n = 1
    existing = set()
    try:
        existing = {e.get("id") for e in svg.iter() if e.get("id")}
    except Exception:
        pass
    while True:
        candidate = "%s%d" % (prefix, n)
        if candidate not in existing:
            return candidate
        n += 1


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def page_bbox(page):
    """Return (x, y, w, h) for an inkscape page element, in user units."""
    return (
        float(page.get("x", 0) or 0),
        float(page.get("y", 0) or 0),
        float(page.get("width", 0) or 0),
        float(page.get("height", 0) or 0),
    )


def frac_rect(bbox, rect):
    """Scale a fractional rect [fx, fy, fw, fh] into absolute (x, y, w, h).

    ``bbox`` is the page (x, y, w, h); ``rect`` values are fractions 0..1 of the
    page size, with the origin at the page's top-left corner.
    """
    px, py, pw, ph = bbox
    fx, fy, fw, fh = rect
    return (px + fx * pw, py + fy * ph, fw * pw, fh * ph)


# ---------------------------------------------------------------------------
# Text construction
# ---------------------------------------------------------------------------
def make_text(x, y, lines, font_size, anchor="start", fill="#000000",
              family="sans-serif", line_height=1.2, bullets=False):
    """Build a multi-line :class:`inkex.TextElement`.

    ``lines`` is a list of strings (one per visual line). Bullets, when enabled,
    are rendered with a leading glyph. Lines are stacked with explicit ``dy`` on
    each :class:`inkex.Tspan` because SVG text does not auto-wrap.
    """
    from inkex import TextElement, Tspan

    style = {
        "font-size": "%spx" % font_size,
        "font-family": family,
        "fill": fill,
        "text-anchor": anchor,
        "line-height": str(line_height),
    }
    text = TextElement(x=str(x), y=str(y))
    text.style = style
    dy = font_size * line_height
    for i, line in enumerate(lines):
        tspan = Tspan()
        tspan.set("x", str(x))
        tspan.set("dy", "0" if i == 0 else str(dy))
        tspan.text = ("• " + line) if bullets else line
        text.add(tspan)
    return text


def set_text_lines(text_el, lines, bullets=False):
    """Replace the line content of an existing text element built by make_text."""
    from inkex import Tspan

    x = text_el.get("x", "0")
    # font-size drives dy; fall back to 24px.
    try:
        fs = float(str(text_el.style.get("font-size", "24px")).replace("px", ""))
    except Exception:
        fs = 24.0
    lh = float(text_el.style.get("line-height", "1.2") or 1.2)
    dy = fs * lh
    for child in list(text_el):
        text_el.remove(child)
    for i, line in enumerate(lines):
        tspan = Tspan()
        tspan.set("x", x)
        tspan.set("dy", "0" if i == 0 else str(dy))
        tspan.text = ("• " + line) if bullets else line
        text_el.add(tspan)


def text_content(text_el):
    """Return the concatenated visible text of a text element."""
    return "".join(text_el.itertext())
