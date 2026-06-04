"""Data-driven slide layouts.

Layouts are loaded from ``data/layouts.json`` and describe placeholder positions
as fractions of the page size, so they scale across 16:9, 4:3 and custom sizes.
"""

import json
import os

from . import constants as C
from . import placeholders as P
from . import svgutil as S

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_cache = None


def load_layouts():
    """Load and cache the layout definitions dict."""
    global _cache
    if _cache is None:
        with open(os.path.join(_DATA_DIR, "layouts.json"), encoding="utf-8") as fh:
            _cache = json.load(fh)
    return _cache


def layout_keys():
    return list(load_layouts().keys())


def layout_label(key):
    return load_layouts().get(key, {}).get("label", key)


def get_layout(key):
    layouts = load_layouts()
    if key not in layouts:
        raise KeyError("Unknown layout: %s" % key)
    return layouts[key]


def instantiate(layer, layout_key, page_bbox, font_family="sans-serif"):
    """Populate ``layer`` with the placeholders defined by ``layout_key``.

    Returns the list of created placeholder groups. Existing placeholders are
    not duplicated -- only placeholder ids missing from the layer are added.
    """
    layout = get_layout(layout_key)
    existing = {S.get_pp(g, C.A_PH_ID) for g in iter_placeholders(layer)}
    created = []
    for ph_def in layout.get("placeholders", []):
        if ph_def["id"] in existing:
            continue
        abs_rect = S.frac_rect(page_bbox, ph_def["rect"])
        group = P.build_placeholder(ph_def, abs_rect, font_family=font_family)
        layer.add(group)
        created.append(group)
    return created


def iter_placeholders(layer):
    """Yield placeholder groups (have a ph-id) directly under a slide layer."""
    from inkex import Group

    for child in layer:
        if isinstance(child, Group) and S.has_pp(child, C.A_PH_ID):
            yield child
