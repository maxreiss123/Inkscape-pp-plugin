"""Content regions: live web, Mermaid, code and Markdown embeds.

A content region is a rectangle on a slide that, in the interactive SVG export,
becomes a live ``<foreignObject>``: an ``<iframe>`` (web), a Mermaid diagram, a
syntax-highlighted code block or rendered Markdown. On the Inkscape canvas it
shows as a labelled dashed box with a short preview of the source so the author
can position it; the rendered output only appears in the browser export.
"""

from . import constants as C
from . import svgutil as S

XHTML = "http://www.w3.org/1999/xhtml"
SVG = "http://www.w3.org/2000/svg"

_KIND_LABEL = {
    C.ContentKind.WEB: "🌐 Web",
    C.ContentKind.HTML: "</> HTML",
    C.ContentKind.MERMAID: "🧜 Mermaid",
    C.ContentKind.CODE: "⌨ Code",
    C.ContentKind.MARKDOWN: "📝 Markdown",
}


def add_content_region(slide, local_rect, kind, src, lang=None, label=None):
    """Create a content region group on ``slide`` and return it.

    ``local_rect`` is (x, y, w, h) in the slide's local coordinates. ``kind`` is
    one of :class:`constants.ContentKind`; ``src`` is the URL / code / Mermaid /
    Markdown source.
    """
    from inkex import Group, Rectangle

    x, y, w, h = local_rect
    group = Group()
    S.set_pp(group, C.A_PH_ROLE, C.PhRole.CONTENT)
    S.set_pp(group, C.A_PH_ID, S.new_id(slide.layer, "content"))
    S.set_pp(group, C.A_CONTENT_KIND, kind)
    if lang:
        S.set_pp(group, C.A_CONTENT_LANG, lang)
    # Store the source as a child element's TEXT (not an attribute): XML
    # normalises newlines in attribute values to spaces on save/reload, which
    # would collapse multi-line code and Markdown to a single line.
    set_region_source(group, src or "")

    rect = Rectangle(x=str(x), y=str(y), width=str(w), height=str(h))
    rect.style = {
        "fill": "#f6f8fa",
        "stroke": "#2a6fb0",
        "stroke-width": "2",
        "stroke-dasharray": "8,6",
    }
    rect.set(C.cn("ph-bounds"), "true")
    group.add(rect)

    # Canvas preview: a label chip plus the first few lines of the source so the
    # author sees what is inside the box.
    chip = _KIND_LABEL.get(kind, "Content")
    if label:
        chip += " — " + label
    header = S.make_text(x + 14, y + 30, [chip], 22, fill="#2a6fb0",
                         family="sans-serif")
    header.set(C.cn("prompt"), "true")
    group.add(header)

    preview_lines = _preview(src, kind)
    if preview_lines:
        body = S.make_text(x + 14, y + 64, preview_lines, 16, fill="#586069",
                           family="monospace")
        body.set(C.cn("prompt"), "true")
        group.add(body)

    slide.layer.add(group)
    return group


def add_web_region(slide, local_rect, src=None, html=None, label=None):
    """Backward-compatible helper: a web (iframe) or inline-HTML region."""
    if html:
        return add_content_region(slide, local_rect, C.ContentKind.HTML, html,
                                  label=label)
    return add_content_region(slide, local_rect, C.ContentKind.WEB, src or "",
                              label=label)


def _preview(src, kind, max_lines=6, max_chars=48):
    if not src:
        return []
    if kind == C.ContentKind.WEB:
        return [src[:max_chars]]
    out = []
    for line in src.splitlines()[:max_lines]:
        out.append(line[:max_chars])
    return out


def region_kind(group):
    """Return the content kind for a region group (handles legacy web attrs)."""
    kind = S.get_pp(group, C.A_CONTENT_KIND)
    if kind:
        return kind
    if S.get_pp(group, C.A_WEB_SRC) is not None:
        return C.ContentKind.WEB
    if S.get_pp(group, C.A_WEB_HTML) is not None:
        return C.ContentKind.HTML
    return C.ContentKind.WEB


def _source_el(group):
    return group.find(C.cn("source"))


def set_region_source(group, src):
    """Store the region source as the text of a ``pp:source`` child element."""
    el = _source_el(group)
    if el is None:
        import lxml.etree as ET
        el = ET.SubElement(group, C.cn("source"))
    el.text = src or ""


def region_source(group):
    el = _source_el(group)
    if el is not None and el.text is not None:
        return el.text
    # Back-compat: older regions stored the source in an attribute.
    src = S.get_pp(group, C.A_CONTENT_SRC)
    if src is not None:
        return src
    return S.get_pp(group, C.A_WEB_SRC) or S.get_pp(group, C.A_WEB_HTML) or ""


def iter_regions(layer):
    """Yield (group, bounds_rect) for each content region in a layer."""
    from inkex import Group

    roles = (C.PhRole.CONTENT, C.PhRole.WEBCONTENT)
    for child in layer:
        if isinstance(child, Group) and S.get_pp(child, C.A_PH_ROLE) in roles:
            bounds = None
            for sub in child:
                if sub.get(C.cn("ph-bounds")) == "true":
                    bounds = sub
                    break
            yield child, bounds


def kinds_in(presentation):
    """Return the set of content kinds used anywhere in the presentation."""
    found = set()
    for slide in presentation.slides():
        for group, _ in iter_regions(slide.layer):
            found.add(region_kind(group))
    return found


def render_into(group, bounds):
    """Render a region's source into native SVG inside the group.

    Removes any previous render and the canvas prompt preview, leaving the
    rendered content (so it shows on the slide, in PDF and in the browser).
    Returns the render wrapper, or None for web/html / empty regions.
    """
    from . import render

    # Drop a previous render so re-rendering is idempotent.
    for child in list(group):
        if S.get_pp(child, C.A_MANAGED) == "render":
            group.remove(child)

    wrapper = render.render_region(group, bounds) if bounds is not None else None
    if wrapper is None:
        return None

    # Replace the authoring preview with the rendered content; keep a faint frame.
    for child in list(group):
        if child.get(C.cn("prompt")) == "true":
            group.remove(child)
        elif child.get(C.cn("ph-bounds")) == "true":
            child.style = {"fill": "none", "stroke": "#e1e4e8", "stroke-width": "1"}
    group.add(wrapper)
    return wrapper


def render_all(presentation):
    """(Re)render every renderable content region. Returns the count rendered."""
    count = 0
    for slide in presentation.slides():
        for group, bounds in iter_regions(slide.layer):
            if render_into(group, bounds) is not None:
                count += 1
    return count


def build_foreign_object(group, bounds):
    """Build a <foreignObject> rendering the region, by kind.

    Returns an lxml element to append to the slide layer (so it inherits the
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
    body.set("style", "margin:0;width:100%;height:100%;overflow:auto;"
                      "background:#fff;box-sizing:border-box")

    kind = region_kind(group)
    src = region_source(group)

    if kind == C.ContentKind.WEB:
        iframe = ET.SubElement(body, "{%s}iframe" % XHTML)
        iframe.set("src", src)
        iframe.set("style", "width:100%;height:100%;border:0")
        iframe.set("allow", "autoplay; fullscreen")
    elif kind == C.ContentKind.HTML:
        wrapper = ET.SubElement(body, "{%s}div" % XHTML)
        wrapper.set("style", "width:100%;height:100%")
        _inject_html(wrapper, src)
    elif kind == C.ContentKind.MERMAID:
        pre = ET.SubElement(body, "{%s}pre" % XHTML)
        pre.set("class", "mermaid")
        pre.set("style", "margin:0")
        pre.text = src
    elif kind == C.ContentKind.CODE:
        lang = S.get_pp(group, C.A_CONTENT_LANG) or "plaintext"
        pre = ET.SubElement(body, "{%s}pre" % XHTML)
        pre.set("style", "margin:0;height:100%")
        code = ET.SubElement(pre, "{%s}code" % XHTML)
        code.set("class", "language-%s" % lang)
        code.text = src
    elif kind == C.ContentKind.MARKDOWN:
        div = ET.SubElement(body, "{%s}div" % XHTML)
        div.set("class", "pp-md")
        div.set("style", "padding:8px")
        div.text = src
    return fo


def _inject_html(wrapper, html):
    import lxml.etree as ET

    try:
        frag = ET.fromstring("<div xmlns='%s'>%s</div>" % (XHTML, html))
        wrapper.text = frag.text
        for child in frag:
            wrapper.append(child)
    except ET.XMLSyntaxError:
        wrapper.text = html
