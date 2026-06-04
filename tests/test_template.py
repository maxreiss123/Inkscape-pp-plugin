import lxml.etree as ET
from pplib import constants as C
from pplib import placeholders as P
from pplib import svgutil as S
from pplib import template


def _managed(layer):
    return [e for e in layer if S.get_pp(e, C.A_MANAGED) == "true"]


def test_apply_master_creates_managed_elements(presentation):
    pres = presentation
    slide = pres.slides()[0]
    roles = {S.get_pp(e, C.A_PH_ROLE) for e in _managed(slide.layer)}
    assert C.PhRole.BACKGROUND in roles
    assert C.PhRole.FOOTER in roles
    assert C.PhRole.SLIDENUMBER in roles


def test_apply_master_is_idempotent(presentation):
    pres = presentation
    slide = pres.slides()[2]
    defn = pres.master_by_id(None).definition
    template.apply_master(pres, slide, defn)
    first = ET.tostring(slide.layer)
    template.apply_master(pres, slide, defn)
    second = ET.tostring(slide.layer)
    assert first == second


def test_apply_master_preserves_user_edits(presentation):
    pres = presentation
    slide = pres.slides()[1]
    title = slide.placeholder("title")
    P.set_placeholder_text(title, ["My real title"])
    assert P.is_user_edited(title)

    defn = pres.master_by_id(None).definition
    template.apply_master(pres, slide, defn, overwrite_user=False)

    title2 = slide.placeholder("title")
    assert S.text_content(P.placeholder_text_el(title2)) == "My real title"


def test_master_definition_roundtrip(presentation):
    pres = presentation
    master = pres.master_by_id(None)
    defn = master.definition
    defn["bg_color"] = "#123456"
    master.definition = defn
    assert pres.master_by_id(None).definition["bg_color"] == "#123456"
