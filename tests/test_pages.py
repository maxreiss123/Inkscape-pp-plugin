from pplib import constants as C
from pplib import pages
from pplib import svgutil as S


def test_add_slide_creates_page_and_layer(presentation):
    pres = presentation
    assert pres.slide_count() == 3
    # Every slide has a matching, distinct page.
    page_ids = []
    for slide in pres.slides():
        page = slide.page
        assert page is not None
        assert S.get_pp(page, C.A_PAGE_ID) == slide.slide_id
        page_ids.append(id(page))
    assert len(set(page_ids)) == 3


def test_indices_are_monotonic(presentation):
    idx = [s.index for s in presentation.slides()]
    assert idx == [0, 1, 2]


def test_pages_tiled_with_gutter(presentation):
    pres = presentation
    w = pres.width
    xs = [S.page_bbox(s.page)[0] for s in pres.slides()]
    assert xs == [0.0, w + C.PAGE_GUTTER, 2 * (w + C.PAGE_GUTTER)]


def test_reorder_moves_slide_to_front(presentation):
    pres = presentation
    last = pres.slides()[-1]
    last_id = last.slide_id
    pages.reorder(pres, last, 0)
    assert pres.slides()[0].slide_id == last_id
    assert [s.index for s in pres.slides()] == [0, 1, 2]


def test_duplicate_increases_count_and_keeps_order(presentation):
    pres = presentation
    src = pres.slides()[1]
    clone = pages.duplicate_slide(pres, src)
    assert pres.slide_count() == 4
    assert clone.slide_id != src.slide_id
    # Clone is inserted right after the source.
    assert pres.slides()[2].slide_id == clone.slide_id
    assert [s.index for s in pres.slides()] == [0, 1, 2, 3]


def test_insert_after_position(presentation):
    pres = presentation
    mid = pres.slides()[0]
    new = pages.add_slide(pres, C.LayoutKey.BLANK, position=mid.index + 1)
    assert pres.slides()[1].slide_id == new.slide_id


def test_sync_drops_orphan_pages(presentation):
    pres = presentation
    # Remove a slide layer but leave its page -> sync should drop the page.
    victim = pres.slides()[1]
    victim.layer.getparent().remove(victim.layer)
    pages.sync(pres)
    assert pres.slide_count() == 2
    assert len(pages.iter_pages(pres)) == 2
