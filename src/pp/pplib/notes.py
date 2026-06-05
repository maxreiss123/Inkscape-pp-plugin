"""Per-slide speaker notes.

Notes are stored as the text of a ``pp:notes`` child element on the slide layer
(not an attribute) so newlines survive save/reload -- the same pattern used for
content-region sources in :mod:`webcontent`. They are shown in the presenter view
of the browser export and never appear on the slide itself.
"""

import lxml.etree as ET

from . import constants as C


def _notes_el(slide):
    return slide.layer.find(C.cn(C.A_NOTES))


def set_notes(slide, text):
    el = _notes_el(slide)
    if el is None:
        el = ET.SubElement(slide.layer, C.cn(C.A_NOTES))
    el.text = text or ""


def get_notes(slide):
    el = _notes_el(slide)
    if el is not None and el.text:
        return el.text
    return ""


def clear_notes(slide):
    el = _notes_el(slide)
    if el is not None:
        slide.layer.remove(el)


def strip_notes_tree(root):
    """Remove all raw pp:notes elements from a subtree (for exports)."""
    for el in list(root.iter(C.cn(C.A_NOTES))):
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)
