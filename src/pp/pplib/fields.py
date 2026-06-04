"""Auto-updated text fields: slide number, total count, date and footer."""

import datetime

from . import constants as C
from . import svgutil as S


def format_date(mode, value=None):
    if mode == C.DateMode.TODAY:
        return datetime.date.today().isoformat()
    if mode == C.DateMode.FIXED:
        return value or ""
    return ""


def field_text(kind, slide_index, total, footer, date_str):
    """Return the rendered text for a field of the given ``kind``."""
    if kind == C.Field.NUMBER:
        return str(slide_index + 1)
    if kind == C.Field.TOTAL:
        return str(total)
    if kind == C.Field.FOOTER:
        return footer or ""
    if kind == C.Field.DATE:
        return date_str or ""
    return ""


def _field_elements(layer):
    # Materialise the list: callers mutate each element's children, and lxml's
    # tree iteration skips siblings if the tree is modified mid-iteration.
    return [el for el in layer.iter() if S.has_pp(el, C.A_FIELD)]


def update_all(pres, date_value=None):
    """Walk all slides and refresh every auto-field text element."""
    slides = pres.slides()
    total = len(slides)
    footer = pres.get_config(C.A_FOOTER_TEXT, "")
    date_mode = pres.get_config(C.A_DATE_MODE, C.DateMode.NONE)
    if date_value is None:
        date_value = pres.get_config(C.A_DATE_VALUE, "")
    date_str = format_date(date_mode, date_value)

    for slide in slides:
        for el in _field_elements(slide.layer):
            kind = S.get_pp(el, C.A_FIELD)
            text = field_text(kind, slide.index, total, footer, date_str)
            S.set_text_lines(el, [text])
