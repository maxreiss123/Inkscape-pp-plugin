"""Promote a designed slide to the slide master (whole deck or per layout)."""

from pplib import constants as C
from pplib import masterfromslide as MFS
from pplib import placeholders as Ph
from pplib import svgutil as S


def _draw_bg(slide, w, h, color):
    from inkex import Rectangle
    rect = Rectangle(x="0", y="0", width=str(w), height=str(h))
    rect.style = {"fill": color, "stroke": "none"}
    slide.layer.add(rect)
    return rect


def test_capture_reads_background_and_text_styles(presentation):
    slide = presentation.slides()[0]  # title layout
    _draw_bg(slide, presentation.width, presentation.height, "#123456")
    g = slide.placeholder("title")
    Ph.set_placeholder_text(g, ["Hello"])
    text = Ph.placeholder_text_el(g)
    text.style["font-size"] = "72px"
    text.style["fill"] = "#ff0000"
    text.style["font-family"] = "Georgia"

    out = MFS.capture(presentation, slide)
    assert out["bg_color"] == "#123456"
    assert out["title_font_size"] == 72
    assert out["title_color"] == "#ff0000"
    assert out["font_family"] == "Georgia"


def test_capture_ignores_master_managed_white_background(presentation):
    """The master's own white bg rect must not be captured over the user's."""
    slide = presentation.slides()[0]
    _draw_bg(slide, presentation.width, presentation.height, "#0E2A47")
    out = MFS.capture(presentation, slide)
    assert out["bg_color"] == "#0E2A47"


def test_capture_decoration_shapes(presentation):
    from inkex import Rectangle
    slide = presentation.slides()[0]
    band = Rectangle(x="0", y="0", width=str(presentation.width), height="120")
    band.style = {"fill": "#C0392B", "stroke": "none"}
    slide.layer.add(band)
    out = MFS.capture(presentation, slide)
    assert "bg_shapes" in out
    assert "#C0392B" in out["bg_shapes"]


def test_apply_all_sets_background_on_every_slide(presentation):
    slide = presentation.slides()[0]
    _draw_bg(slide, presentation.width, presentation.height, "#2E4053")
    summary = MFS.apply(presentation, slide, scope="all")
    assert "every slide" in summary
    defn = presentation.master_by_id(None).definition
    assert defn["bg_color"] == "#2E4053"
    # Every slide now carries a managed background rect with that colour.
    for s in presentation.slides():
        rects = [e for e in s.layer
                 if e.tag.endswith("}rect")
                 and S.get_pp(e, C.A_PH_ROLE) == C.PhRole.BACKGROUND]
        assert rects and rects[0].style.get("fill") == "#2E4053"


def test_apply_layout_scope_only_affects_same_layout(presentation):
    from pplib import template

    title_slide = presentation.slides()[0]          # title layout
    _draw_bg(title_slide, presentation.width, presentation.height, "#111111")
    MFS.apply(presentation, title_slide, scope="layout")

    defn = presentation.master_by_id(None).definition
    assert defn["layouts"][C.LayoutKey.TITLE]["bg_color"] == "#111111"

    # The title layout resolves to the dark background; content stays default.
    title_eff = template.effective_definition(defn, C.LayoutKey.TITLE)
    content_eff = template.effective_definition(defn, C.LayoutKey.TITLE_CONTENT)
    assert title_eff["bg_color"] == "#111111"
    assert content_eff.get("bg_color") != "#111111"


def test_apply_layout_scope_paints_only_matching_slides(presentation):
    title_slide = presentation.slides()[0]
    _draw_bg(title_slide, presentation.width, presentation.height, "#3B0A45")
    MFS.apply(presentation, title_slide, scope="layout")

    for s in presentation.slides():
        rects = [e for e in s.layer
                 if e.tag.endswith("}rect")
                 and S.get_pp(e, C.A_PH_ROLE) == C.PhRole.BACKGROUND]
        fill = rects[0].style.get("fill") if rects else None
        if s.layout == C.LayoutKey.TITLE:
            assert fill == "#3B0A45"
        else:
            assert fill != "#3B0A45"
