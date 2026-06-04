from pplib import constants as C
from pplib import fields, pages
from pplib import svgutil as S


def _numbers(pres):
    out = []
    for s in pres.slides():
        for el in s.layer.iter():
            if S.get_pp(el, C.A_FIELD) == C.Field.NUMBER:
                out.append(S.text_content(el))
    return out


def _footers(pres):
    out = []
    for s in pres.slides():
        for el in s.layer.iter():
            if S.get_pp(el, C.A_FIELD) == C.Field.FOOTER:
                out.append(S.text_content(el))
    return out


def test_numbers_match_index(presentation):
    fields.update_all(presentation)
    assert _numbers(presentation) == ["1", "2", "3"]


def test_numbers_reflow_after_reorder(presentation):
    pres = presentation
    pages.reorder(pres, pres.slides()[2], 0)
    fields.update_all(pres)
    assert _numbers(pres) == ["1", "2", "3"]


def test_numbers_reflow_after_duplicate(presentation):
    pres = presentation
    pages.duplicate_slide(pres, pres.slides()[0])
    fields.update_all(pres)
    assert _numbers(pres) == ["1", "2", "3", "4"]


def test_footer_text(presentation):
    fields.update_all(presentation)
    assert all(f == "Talk" for f in _footers(presentation))


def test_date_modes():
    assert fields.format_date(C.DateMode.NONE) == ""
    assert fields.format_date(C.DateMode.FIXED, "2026-01-01") == "2026-01-01"
    import datetime
    assert fields.format_date(C.DateMode.TODAY) == datetime.date.today().isoformat()
