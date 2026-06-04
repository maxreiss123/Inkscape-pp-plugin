"""Master / template system: storage and the apply-refresh engine.

A master is stored as a JSON *definition* (the source of truth for applying) on a
hidden master layer, plus an editable visual layer the user can tweak. Applying a
master regenerates all ``pp:managed`` elements on a slide (background, logo,
footer/number/date fields) while preserving any placeholder the user has edited.
The operation is idempotent: applying twice yields the same tree.
"""

import json
import os

from . import constants as C
from . import fields
from . import layouts as L
from . import svgutil as S

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_default_definition():
    with open(os.path.join(_DATA_DIR, "masters", "default.json"), encoding="utf-8") as fh:
        return json.load(fh)


def ensure_master(pres, definition=None):
    """Return the presentation's master, creating a default one if needed."""
    from inkex import Layer

    existing = pres.master_by_id(None)
    if existing is not None:
        if definition is not None:
            existing.definition = definition
        return existing

    if definition is None:
        definition = load_default_definition()
    layer = Layer.new("Master: %s" % definition.get("label", "Default"))
    layer.set("id", definition.get("id", "master-default"))
    S.set_pp(layer, C.A_ROLE, C.Role.MASTER)
    # Masters are not shown on slides directly; hide the layer.
    layer.style["display"] = "none"
    pres.svg.add(layer)
    from .model import Master
    master = Master(pres, layer)
    master.definition = definition
    return master


# ---------------------------------------------------------------------------
# Managed-element generation
# ---------------------------------------------------------------------------
def _clear_managed(layer):
    for el in list(layer):
        if S.get_pp(el, C.A_MANAGED) == "true":
            layer.remove(el)


def _bg_rect(bbox, color):
    from inkex import Rectangle
    x, y, w, h = bbox
    rect = Rectangle(x=str(x), y=str(y), width=str(w), height=str(h))
    rect.style = {"fill": color, "stroke": "none"}
    S.set_pp(rect, C.A_PH_ROLE, C.PhRole.BACKGROUND)
    S.set_pp(rect, C.A_MANAGED, "true")
    return rect


def _logo(bbox, defn):
    from inkex import Image
    href = defn.get("logo_href")
    if not href:
        return None
    x, y, w, h = S.frac_rect(bbox, defn.get("logo_rect", [0.86, 0.04, 0.10, 0.08]))
    img = Image()
    img.set("x", str(x))
    img.set("y", str(y))
    img.set("width", str(w))
    img.set("height", str(h))
    img.set("{http://www.w3.org/1999/xlink}href", href)
    S.set_pp(img, C.A_PH_ROLE, C.PhRole.LOGO)
    S.set_pp(img, C.A_MANAGED, "true")
    return img


def _field_text(bbox, defn, rect_key, field_kind, ph_role, anchor, font_scale=0.6):
    x, y, w, h = S.frac_rect(bbox, defn.get(rect_key))
    font = max(12.0, defn.get("body_font_size", 28) * font_scale)
    tx = x + (w / 2 if anchor == "middle" else (w if anchor == "end" else 0))
    ty = y + font
    el = S.make_text(tx, ty, [""], font, anchor=anchor, fill="#555555",
                     family=defn.get("font_family", "sans-serif"))
    S.set_pp(el, C.A_PH_ROLE, ph_role)
    S.set_pp(el, C.A_FIELD, field_kind)
    S.set_pp(el, C.A_MANAGED, "true")
    return el


def apply_master(pres, slide, definition, overwrite_user=False):
    """(Re)generate master-managed content on ``slide`` from ``definition``.

    Inserts background/logo/footer/number/date at the bottom of the layer so
    user content stays on top, then ensures layout placeholders exist and
    refreshes auto-fields.
    """
    layer = slide.layer
    bbox = slide.content_bbox  # author in local coords; layer transform places it
    slide.master_id = definition.get("id", "master-default")

    _clear_managed(layer)

    # Build managed elements bottom-up, then insert them at the front (index 0+)
    # so they sit beneath user content.
    managed = [_bg_rect(bbox, definition.get("bg_color", "#ffffff"))]
    logo = _logo(bbox, definition)
    if logo is not None:
        managed.append(logo)
    if definition.get("show_footer"):
        managed.append(_field_text(bbox, definition, "footer_rect",
                                    C.Field.FOOTER, C.PhRole.FOOTER, "start"))
    if definition.get("show_number"):
        managed.append(_field_text(bbox, definition, "number_rect",
                                    C.Field.NUMBER, C.PhRole.SLIDENUMBER, "end"))
    if definition.get("show_date"):
        managed.append(_field_text(bbox, definition, "date_rect",
                                    C.Field.DATE, C.PhRole.DATE, "start"))
    for i, el in enumerate(managed):
        layer.insert(i, el)

    # Ensure layout placeholders exist (never clobber user-edited ones).
    family = definition.get("font_family", "sans-serif")
    L.instantiate(layer, slide.layout, bbox, font_family=family)

    fields.update_all(pres)


def apply_to_all(pres, definition, overwrite_user=False):
    for slide in pres.slides():
        apply_master(pres, slide, definition, overwrite_user=overwrite_user)
