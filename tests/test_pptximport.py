"""Full-presentation PPTX import: slides, text, notes and theme round-trip.

The fixtures are generated with python-pptx (a real PowerPoint writer) so the
parser is exercised against genuine OOXML, not a hand-written stub.
"""

import os
import tempfile

import pytest

pptx = pytest.importorskip("pptx")
from pplib import constants as C  # noqa: E402
from pplib import notes, pptximport  # noqa: E402
from pplib import svgutil as S  # noqa: E402
from pptx import Presentation as PptxPresentation  # noqa: E402
from pptx.util import Emu  # noqa: E402


def _make_deck(path):
    p = PptxPresentation()
    p.slide_width = Emu(12192000)   # 16:9
    p.slide_height = Emu(6858000)

    # Slide 1: title + subtitle (title layout).
    s1 = p.slides.add_slide(p.slide_layouts[0])
    s1.shapes.title.text = "Welcome"
    s1.placeholders[1].text = "An imported deck"

    # Slide 2: title + bullet body (title+content layout).
    s2 = p.slides.add_slide(p.slide_layouts[1])
    s2.shapes.title.text = "Agenda"
    body = s2.placeholders[1].text_frame
    body.text = "First point"
    body.add_paragraph().text = "Second point"
    body.add_paragraph().text = "Third point"
    s2.notes_slide.notes_text_frame.text = "Remember to slow down here.\nBreathe."

    # Slide 3: a free-floating text box on a blank layout.
    s3 = p.slides.add_slide(p.slide_layouts[6])
    tb = s3.shapes.add_textbox(Emu(1000000), Emu(1000000), Emu(4000000), Emu(800000))
    tb.text_frame.text = "Free text box"

    p.save(path)


@pytest.fixture
def deck_path():
    fd, path = tempfile.mkstemp(suffix=".pptx")
    os.close(fd)
    _make_deck(path)
    yield path
    os.remove(path)


_BLANK_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" '
    'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
    'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd" '
    'width="100" height="100" viewBox="0 0 100 100">'
    '<sodipodi:namedview id="nv"/></svg>'
)


def _blank_pres():
    import inkex
    from pplib.model import Presentation

    root = inkex.load_svg(_BLANK_SVG.encode()).getroot()
    return Presentation(root)


def test_import_creates_all_slides(deck_path):
    pres = _blank_pres()
    count, summary = pptximport.import_presentation(pres, deck_path)
    assert count == 3
    assert pres.slide_count() == 3
    assert "Imported 3 slides" in summary


def test_title_and_subtitle_roundtrip(deck_path):
    from pplib import placeholders as Ph

    pres = _blank_pres()
    pptximport.import_presentation(pres, deck_path)
    slide = pres.slides()[0]
    assert slide.layout == C.LayoutKey.TITLE
    title = Ph.placeholder_text_el(slide.placeholder("title"))
    assert "Welcome" in S.text_content(title)
    sub = Ph.placeholder_text_el(slide.placeholder("subtitle"))
    assert "An imported deck" in S.text_content(sub)


def test_bullets_roundtrip(deck_path):
    from pplib import placeholders as Ph

    pres = _blank_pres()
    pptximport.import_presentation(pres, deck_path)
    slide = pres.slides()[1]
    assert slide.layout == C.LayoutKey.TITLE_CONTENT
    body = Ph.placeholder_text_el(slide.placeholder("body"))
    text = S.text_content(body)
    assert "First point" in text
    assert "Second point" in text
    assert "Third point" in text


def test_notes_imported(deck_path):
    pres = _blank_pres()
    pptximport.import_presentation(pres, deck_path)
    note = notes.get_notes(pres.slides()[1])
    assert "slow down" in note
    assert "Breathe" in note


def test_free_text_box_imported(deck_path):
    pres = _blank_pres()
    pptximport.import_presentation(pres, deck_path)
    slide = pres.slides()[2]
    texts = [S.text_content(t) for t in slide.layer.iter()
             if t.tag.endswith("}text")]
    assert any("Free text box" in t for t in texts)


def test_append_mode_keeps_existing(deck_path, presentation):
    before = presentation.slide_count()
    count, _ = pptximport.import_presentation(
        presentation, deck_path, replace=False)
    assert presentation.slide_count() == before + count


def test_replace_mode_replaces(deck_path, presentation):
    count, _ = pptximport.import_presentation(
        presentation, deck_path, replace=True)
    assert presentation.slide_count() == count


def test_non_pptx_rejected():
    pres = _blank_pres()
    with pytest.raises(ValueError):
        pptximport.import_presentation(pres, "/tmp/whatever.odp")
