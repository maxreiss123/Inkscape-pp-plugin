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
    assert S.get_pp(group, C.A_PH_ROLE) == C.PhRole.WEBCONTENT
    assert S.get_pp(group, C.A_WEB_SRC) == "https://example.com"
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
