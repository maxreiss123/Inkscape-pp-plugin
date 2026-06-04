from pplib import constants as C
from pplib import layouts


def test_all_layouts_present():
    keys = set(layouts.layout_keys())
    assert {"title", "title_content", "two_content", "blank"} <= keys


def test_placeholder_ids_per_layout(presentation):
    pres = presentation
    by_layout = {s.layout: set(_ph_ids(s)) for s in pres.slides()}
    assert by_layout["title"] == {"title", "subtitle"}
    assert by_layout["title_content"] == {"title", "body"}
    assert by_layout["two_content"] == {"title", "content-left", "content-right"}


def _ph_ids(slide):
    from pplib import svgutil as S
    return [S.get_pp(g, C.A_PH_ID) for g in slide.placeholders()]


def test_fractional_geometry_scales_to_page():
    from pplib import svgutil as S
    bbox = (0.0, 0.0, 1000.0, 500.0)
    abs_rect = S.frac_rect(bbox, [0.1, 0.2, 0.5, 0.4])
    assert abs_rect == (100.0, 100.0, 500.0, 200.0)


def test_instantiate_does_not_duplicate(presentation):
    pres = presentation
    slide = pres.slides()[1]  # title_content
    before = len(slide.placeholders())
    layouts.instantiate(slide.layer, slide.layout, slide.bbox)
    after = len(slide.placeholders())
    assert before == after
