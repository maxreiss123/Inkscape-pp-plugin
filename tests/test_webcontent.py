import lxml.etree as ET
from pplib import constants as C
from pplib import jsexport, webcontent
from pplib import svgutil as S

XHTML = "http://www.w3.org/1999/xhtml"
SVG = "http://www.w3.org/2000/svg"


def test_add_web_region_marks_metadata(presentation):
    slide = presentation.slides()[0]
    group = webcontent.add_web_region(slide, (100, 100, 800, 400),
                                      src="https://example.com", label="Demo")
    assert S.get_pp(group, C.A_PH_ROLE) == C.PhRole.CONTENT
    assert webcontent.region_kind(group) == C.ContentKind.WEB
    assert webcontent.region_source(group) == "https://example.com"
    regions = list(webcontent.iter_regions(slide.layer))
    assert len(regions) == 1
    _, bounds = regions[0]
    assert bounds is not None


def test_export_renders_iframe(presentation):
    slide = presentation.slides()[1]
    webcontent.add_web_region(slide, (50, 50, 600, 300), src="https://example.org")
    tree = jsexport.build(presentation)
    data = ET.tostring(tree).decode()
    assert "foreignObject" in data
    iframes = tree.getroot().findall(".//{%s}iframe" % XHTML)
    assert len(iframes) == 1
    assert iframes[0].get("src") == "https://example.org"


def test_export_inline_html(presentation):
    slide = presentation.slides()[0]
    webcontent.add_web_region(
        slide, (10, 10, 200, 200),
        html="<canvas id='c'></canvas><script>1+1</script>")
    tree = jsexport.build(presentation)
    root = tree.getroot()
    fobjs = root.findall(".//{%s}foreignObject" % SVG)
    assert len(fobjs) == 1
    # The inline markup is embedded as real XHTML nodes.
    assert root.findall(".//{%s}canvas" % XHTML)


def test_code_region_renders_native_svg(presentation):
    """Code regions render to native SVG <text> (no foreignObject, no CDN)."""
    slide = presentation.slides()[1]
    webcontent.add_content_region(slide, (10, 10, 800, 400),
                                  C.ContentKind.CODE,
                                  "def f():\n    return 1\n", lang="python")
    tree = jsexport.build(presentation)
    root = tree.getroot()
    data = ET.tostring(tree).decode()
    joined = " ".join("".join(t.itertext()) for t in root.findall(".//{%s}text" % SVG))
    assert "return" in joined and "1" in joined
    assert root.findall(".//{%s}foreignObject" % SVG) == []
    assert C.CDN["hljs"] not in data  # no network dependency


def test_markdown_region_renders_native_svg(presentation):
    slide = presentation.slides()[2]
    webcontent.add_content_region(slide, (10, 10, 1200, 600),
                                  C.ContentKind.MARKDOWN,
                                  "# Title\n\nA paragraph.\n\n- one\n- two\n")
    tree = jsexport.build(presentation)
    root = tree.getroot()
    joined = " ".join("".join(t.itertext()) for t in root.findall(".//{%s}text" % SVG))
    assert "Title" in joined and "paragraph" in joined and "one" in joined
    assert root.findall(".//{%s}foreignObject" % SVG) == []


def test_rendered_region_keeps_source(presentation):
    """The source survives rendering so the region can be re-rendered/edited."""
    slide = presentation.slides()[0]
    src = "def f():\n    return 1\n"
    group = webcontent.add_content_region(slide, (10, 10, 800, 400),
                                          C.ContentKind.CODE, src, lang="python")
    bounds = next(iter(webcontent.iter_regions(slide.layer)))[1]
    webcontent.render_into(group, bounds)
    assert webcontent.region_source(group) == src


def test_no_cdn_when_no_rich_content(presentation):
    data = ET.tostring(jsexport.build(presentation)).decode()
    assert C.CDN["mermaid"] not in data
    assert C.CDN["marked"] not in data


def test_multiline_source_survives_roundtrip(presentation):
    """Multi-line code/markdown must survive a save/reload (newlines kept).

    Regression test: storing the source in an XML attribute collapsed newlines
    to spaces on reparse; it is now kept as element text.
    """
    import inkex
    from pplib.model import Presentation

    slide = presentation.slides()[0]
    code = "def f():\n    x = 1\n    return x\n"
    webcontent.add_content_region(slide, (10, 10, 800, 400),
                                  C.ContentKind.CODE, code, lang="python")

    # Serialise the whole document and parse it back, as Inkscape would.
    data = ET.tostring(presentation.svg.getroottree())
    reloaded = Presentation(inkex.load_svg(data).getroot())
    region = next(iter(webcontent.iter_regions(reloaded.slides()[0].layer)))[0]
    assert webcontent.region_source(region) == code
    assert webcontent.region_source(region).count("\n") == 3
