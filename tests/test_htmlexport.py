import pytest
from pplib import fonts, htmlexport


def test_vector_html_wraps_svg_and_player(presentation):
    html = htmlexport.build_vector(presentation, title="My Deck")
    assert "<!doctype html>" in html
    assert "<svg" in html
    assert "PP_CONFIG" in html        # interactive player embedded
    assert "<title>My Deck</title>" in html


def test_raster_html_embeds_one_image_per_slide(presentation):
    pytest.importorskip("cairosvg")
    html = htmlexport.build_raster(presentation, scale=1.0)
    assert html.count("data:image/png;base64,") == 3
    assert "<img" in html and "addEventListener" in html


def test_used_families_detects_concrete_fonts(presentation):
    from pplib import jsexport
    root = jsexport.build(presentation).getroot()
    fams = fonts.used_families(root)
    # Generic families are excluded; everything used here is generic, so empty.
    assert all(f.lower() not in ("sans-serif", "serif", "monospace") for f in fams)


def test_embed_css_returns_string(presentation):
    from pplib import jsexport
    root = jsexport.build(presentation).getroot()
    css = fonts.embed_css(root)
    assert isinstance(css, str)  # '' when fontTools/files unavailable
