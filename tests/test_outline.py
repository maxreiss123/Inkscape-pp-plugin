import inkex
from pplib import constants as C
from pplib import document, outline, webcontent
from pplib import svgutil as S
from pplib.model import Presentation

OUTLINE = """# My Talk
A subtitle line

## Agenda
- First point
- Second point
  - nested point

## Architecture
Some intro paragraph.

```mermaid
flowchart LR
  A --> B
```

---

## Code
```python
def f():
    return 1
```
"""


def test_parse_maps_headings_bullets_blocks():
    specs = outline.parse_outline(OUTLINE)
    layouts = [s["layout"] for s in specs]
    assert layouts[0] == C.LayoutKey.TITLE
    assert specs[0]["title"] == "My Talk"
    assert specs[0]["subtitle"] == "A subtitle line"
    # Agenda slide
    agenda = specs[1]
    assert agenda["layout"] == C.LayoutKey.TITLE_CONTENT
    assert agenda["title"] == "Agenda"
    assert "First point" in agenda["body"][0]
    assert any("nested point" in b for b in agenda["body"])
    # Architecture slide has a mermaid block
    arch = specs[2]
    assert arch["blocks"][0]["kind"] == C.ContentKind.MERMAID
    assert "flowchart" in arch["blocks"][0]["src"]
    # Code slide (after --- break) has a python code block
    code = specs[-1]
    assert code["title"] == "Code"
    assert code["blocks"][0]["kind"] == C.ContentKind.CODE
    assert code["blocks"][0]["lang"] == "python"
    assert "return 1" in code["blocks"][0]["src"]


def _fresh_pres():
    root = inkex.load_svg(
        b'<svg xmlns="http://www.w3.org/2000/svg" '
        b'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
        b'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd" '
        b'width="100" height="100" viewBox="0 0 100 100">'
        b'<sodipodi:namedview id="nv"/></svg>').getroot()
    pres = Presentation(root)
    document.init_presentation(pres, aspect="16:9", first_layout=C.LayoutKey.BLANK)
    return pres


def test_build_creates_slides_with_content():
    pres = _fresh_pres()
    created, removed = outline.generate(pres, OUTLINE, replace=True)
    assert created == 4
    slides = pres.slides()
    assert len(slides) == 4  # the initial blank slide was replaced

    # Title slide text.
    title = slides[0].placeholder("title")
    assert S.text_content(__import__("pplib.placeholders", fromlist=["placeholder_text_el"])
                          .placeholder_text_el(title)) == "My Talk"

    # Agenda body has bullets.
    body = slides[1].placeholder("body")
    from pplib.placeholders import placeholder_text_el
    assert "First point" in S.text_content(placeholder_text_el(body))

    # Architecture + Code slides each carry a content region.
    arch_regions = list(webcontent.iter_regions(slides[2].layer))
    assert len(arch_regions) == 1
    assert webcontent.region_kind(arch_regions[0][0]) == C.ContentKind.MERMAID
    code_regions = list(webcontent.iter_regions(slides[3].layer))
    assert webcontent.region_kind(code_regions[0][0]) == C.ContentKind.CODE


def test_replace_false_appends():
    pres = _fresh_pres()
    before = pres.slide_count()
    created, removed = outline.generate(pres, "## Only\n- a\n- b\n", replace=False)
    assert removed == 0
    assert pres.slide_count() == before + created


def test_unfilled_prompts_stripped_from_export():
    from pplib import jsexport
    pres = _fresh_pres()
    # A content slide with only a code block -> body placeholder stays empty.
    outline.generate(pres, "## Code\n```python\nx=1\n```\n", replace=True)
    data = __import__("lxml.etree", fromlist=["tostring"]).tostring(
        jsexport.build(pres)).decode()
    assert "Click to add" not in data
