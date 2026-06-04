"""Web-content regions.

A web-content region is a rectangle on a slide that, in the interactive SVG
export, becomes a live ``<foreignObject>`` embedding a web page (via ``<iframe>``)
or inline HTML/JS. On the Inkscape canvas it shows as a labelled dashed box so
the author can position it; the live content only appears in the browser export.
"""

from . import constants as C
from . import svgutil as S

XHTML = "http://www.w3.org/1999/xhtml"
SVG = "http://www.w3.org/2000/svg"


def add_web_region(slide, local_rect, src=None, html=None, label=None):
    """Create a web-content region group on ``slide`` and return it.

    ``local_rect`` is (x, y, w, h) in the slide's local coordinates.
    """
    from inkex import Group, Rectangle

    x, y, w, h = local_rect
    group = Group()
    S.set_pp(group, C.A_PH_ROLE, C.PhRole.WEBCONTENT)
    S.set_pp(group, C.A_PH_ID, S.new_id(slide.layer, "web"))
    if src:
        S.set_pp(group, C.A_WEB_SRC, src)
    if html:
        S.set_pp(group, C.A_WEB_HTML, html)

    rect = Rectangle(x=str(x), y=str(y), width=str(w), height=str(h))
    rect.style = {
        "fill": "#eef3f8",
        "stroke": "#2a6fb0",
        "stroke-width": "2",
        "stroke-dasharray": "8,6",
    }
    rect.set(C.cn("ph-bounds"), "true")
    group.add(rect)

    cap = label or src or "Web content"
    text = S.make_text(x + 12, y + 28, [("⊕ " + cap)], 22,
                       fill="#2a6fb0", family="sans-serif")
    text.set(C.cn("prompt"), "true")
    group.add(text)

    slide.layer.add(group)
    return group


def iter_regions(layer):
    """Yield (group, bounds_rect) for each web-content region in a layer."""
    from inkex import Group

    for child in layer:
        if isinstance(child, Group) and S.get_pp(child, C.A_PH_ROLE) == C.PhRole.WEBCONTENT:
            bounds = None
            for sub in child:
                if sub.get(C.cn("ph-bounds")) == "true":
                    bounds = sub
                    break
            yield child, bounds


def build_foreign_object(group, bounds):
    """Build a <foreignObject> rendering the region's web content.

    Returns an lxml element to be appended to the slide layer (so it inherits the
    slide transform). Geometry comes from the bounds rectangle (local coords).
    """
    import lxml.etree as ET

    if bounds is None:
        return None
    x = bounds.get("x", "0")
    y = bounds.get("y", "0")
    w = bounds.get("width", "0")
    h = bounds.get("height", "0")

    fo = ET.Element("{%s}foreignObject" % SVG)
    fo.set("x", x)
    fo.set("y", y)
    fo.set("width", w)
    fo.set("height", h)

    body = ET.SubElement(fo, "{%s}body" % XHTML)
    body.set("style", "margin:0;width:100%;height:100%;overflow:hidden")

    src = S.get_pp(group, C.A_WEB_SRC)
    html = S.get_pp(group, C.A_WEB_HTML)
    if src:
        iframe = ET.SubElement(body, "{%s}iframe" % XHTML)
        iframe.set("src", src)
        iframe.set("style", "width:100%;height:100%;border:0")
        iframe.set("allow", "autoplay; fullscreen")
    elif html:
        # Inline HTML/JS: parse as a fragment under a wrapper div.
        wrapper = ET.SubElement(body, "{%s}div" % XHTML)
        wrapper.set("style", "width:100%;height:100%")
        try:
            frag = ET.fromstring("<div xmlns='%s'>%s</div>" % (XHTML, html))
            for child in frag:
                wrapper.append(child)
            if frag.text:
                wrapper.text = frag.text
        except ET.XMLSyntaxError:
            # Fall back to treating it as plain text content.
            wrapper.text = html
    return fo
