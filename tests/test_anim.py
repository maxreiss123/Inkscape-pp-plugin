import inkex
import lxml.etree as ET
from pplib import anim, jsexport
from pplib import constants as C
from pplib import svgutil as S

SVG = "http://www.w3.org/2000/svg"


def _text_box(lines):
    return S.make_text(100, 100, lines, 28)


def test_split_text_lines():
    text = _text_box(["one", "two", "three"])
    g = inkex.Group()
    g.add(text)
    parts = anim.split_text_lines(text)
    assert len(parts) == 3
    assert [S.text_content(p) for p in parts] == ["one", "two", "three"]
    # Original removed, replaced by 3 lines.
    assert len(list(g)) == 3


def test_apply_sequence_orders_top_to_bottom(presentation):
    slide = presentation.slides()[0]
    a = inkex.Rectangle(x="0", y="200", width="10", height="10")
    b = inkex.Rectangle(x="0", y="50", width="10", height="10")
    slide.layer.add(a)
    slide.layer.add(b)
    anim.apply([a, b], 1, C.EffectType.FADE)
    # b is higher (y=50) so it animates first.
    assert S.get_pp(b, C.A_EFFECT_ORDER) == "1"
    assert S.get_pp(a, C.A_EFFECT_ORDER) == "2"
    assert S.get_pp(b, C.A_EFFECT_TYPE) == "fade"


def test_together_same_order(presentation):
    a = inkex.Rectangle(x="0", y="0", width="10", height="10")
    b = inkex.Rectangle(x="0", y="0", width="10", height="10")
    anim.apply([a, b], 3, C.EffectType.APPEAR, together=True)
    assert S.get_pp(a, C.A_EFFECT_ORDER) == "3"
    assert S.get_pp(b, C.A_EFFECT_ORDER) == "3"


def test_slide_max_order(presentation):
    slide = presentation.slides()[0]
    r = inkex.Rectangle(x="0", y="0", width="10", height="10")
    slide.layer.add(r)
    anim.set_effect(r, 4, C.EffectType.APPEAR)
    assert anim.slide_max_order(slide) == 4


def test_clear_effects_deep():
    g = inkex.Group()
    r = inkex.Rectangle(x="0", y="0", width="1", height="1")
    g.add(r)
    anim.set_effect(r, 2, C.EffectType.APPEAR)
    anim.clear_effects_deep(g)
    assert S.get_pp(r, C.A_EFFECT_ORDER) is None


def test_effects_exported_as_data_attrs(presentation):
    slide = presentation.slides()[0]
    r = inkex.Rectangle(x="0", y="0", width="10", height="10")
    slide.layer.add(r)
    anim.set_effect(r, 2, C.EffectType.FLY)
    tree = jsexport.build(presentation)
    hits = tree.getroot().findall(".//*[@data-pp-effect-order]")
    assert any(h.get("data-pp-effect-order") == "2"
               and h.get("data-pp-effect-type") == "fly" for h in hits)
    # Player understands build steps.
    assert "data-pp-effect-order" in ET.tostring(tree).decode()
    assert "maxStep" in ET.tostring(tree).decode()


def test_badges_drawn_and_stripped_from_export(presentation):
    slide = presentation.slides()[0]
    box = S.make_text(300, 300, ["one", "two", "three"], 40)
    slide.layer.add(box)
    lines = anim.split_text_lines(box)
    anim.apply(lines, 1, C.EffectType.APPEAR)
    n = anim.refresh_badges(slide)
    assert n == 3
    assert len([e for e in slide.layer if anim.is_badge(e)]) == 3

    # Badges must not appear in the interactive export.
    tree = jsexport.build(presentation)
    badges = [e for e in tree.getroot().iter() if anim.is_badge(e)]
    assert badges == []


def test_refresh_badges_is_idempotent(presentation):
    slide = presentation.slides()[0]
    r = inkex.Rectangle(x="10", y="10", width="50", height="50")
    slide.layer.add(r)
    anim.set_effect(r, 1, C.EffectType.APPEAR)
    anim.refresh_badges(slide)
    anim.refresh_badges(slide)
    assert len([e for e in slide.layer if anim.is_badge(e)]) == 1


def test_clear_badges(presentation):
    slide = presentation.slides()[0]
    r = inkex.Rectangle(x="10", y="10", width="50", height="50")
    slide.layer.add(r)
    anim.set_effect(r, 1, C.EffectType.APPEAR)
    anim.refresh_badges(slide)
    anim.clear_badges(slide)
    assert [e for e in slide.layer if anim.is_badge(e)] == []
