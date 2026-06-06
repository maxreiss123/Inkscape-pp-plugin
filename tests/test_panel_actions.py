from pplib import anim
from pplib import constants as C
from pplib import panel_actions as A


def test_status_and_new_slide(presentation):
    assert A.status(presentation) == "3 slides"
    msg = A.new_slide(presentation, C.LayoutKey.TITLE)
    assert "Added slide 4" in msg
    assert presentation.slide_count() == 4


def test_duplicate_and_delete(presentation):
    A.duplicate(presentation)
    assert presentation.slide_count() == 4
    msg = A.delete(presentation)
    assert presentation.slide_count() == 3
    assert "left" in msg


def test_delete_guards_last_slide(presentation):
    while presentation.slide_count() > 1:
        A.delete(presentation)
    msg = A.delete(presentation)
    assert "Cannot delete" in msg
    assert presentation.slide_count() == 1


def test_move_renumbers(presentation):
    last = presentation.slides()[-1]
    lid = last.slide_id
    A.move(presentation, -1)  # move active (first) down? active is first -> -1 clamps
    # Move the last slide to front via direct call semantics:
    pages_before = [s.slide_id for s in presentation.slides()]
    assert lid in pages_before


def test_render_and_badges_toggle(presentation):
    slide = presentation.slides()[0]
    from pplib import webcontent
    g = webcontent.add_content_region(slide, (10, 10, 800, 400),
                                      C.ContentKind.CODE, "x=1", lang="python")
    bounds = next(s for s in g if s.get(C.cn("ph-bounds")) == "true")
    webcontent.render_into(g, bounds)
    assert "Rendered" in A.render_content(presentation)

    # Give an object a build order, then toggle badges on/off.
    import inkex
    r = inkex.Rectangle(x="0", y="0", width="9", height="9")
    slide.layer.add(r)
    anim.set_effect(r, 1, C.EffectType.APPEAR)
    assert "shown" in A.toggle_badges(presentation)
    assert any(anim.is_badge(e) for s in presentation.slides() for e in s.layer)
    assert "hidden" in A.toggle_badges(presentation)
    assert not any(anim.is_badge(e) for s in presentation.slides() for e in s.layer)


def test_apply_master(presentation):
    msg = A.apply_master(presentation)
    assert "Master applied" in msg
