import json
import re

import inkex
import lxml.etree as ET
from pplib import jsexport
from pplib import notes as notes_mod
from pplib.model import Presentation


def test_notes_roundtrip(presentation):
    slide = presentation.slides()[0]
    text = "First line\nSecond line\n- a point"
    notes_mod.set_notes(slide, text)
    data = ET.tostring(presentation.svg.getroottree())
    reloaded = Presentation(inkex.load_svg(data).getroot())
    assert notes_mod.get_notes(reloaded.slides()[0]) == text


def test_clear_notes(presentation):
    slide = presentation.slides()[0]
    notes_mod.set_notes(slide, "hi")
    notes_mod.clear_notes(slide)
    assert notes_mod.get_notes(slide) == ""


def test_notes_in_config_and_stripped(presentation):
    pres = presentation
    notes_mod.set_notes(pres.slides()[0], "intro notes")
    notes_mod.set_notes(pres.slides()[2], "closing")
    tree = jsexport.build(pres)
    data = ET.tostring(tree).decode()

    cfg = json.loads(re.search(r"PP_CONFIG = (\{.*?\});", data, re.S).group(1))
    assert len(cfg["notes"]) == 3
    assert cfg["notes"][0] == "intro notes"
    assert cfg["notes"][2] == "closing"

    # Raw pp:notes elements are not in the exported tree.
    from pplib import constants as C
    assert tree.getroot().find(".//" + C.cn(C.A_NOTES)) is None


def test_slides_get_stable_ids(presentation):
    tree = jsexport.build(presentation)
    ids = [el.get("id") for el in tree.getroot().findall(".//*[@data-pp-slide]")]
    assert "pp-slide-0" in ids and "pp-slide-1" in ids and "pp-slide-2" in ids


def test_player_has_presenter_support(presentation):
    data = ET.tostring(jsexport.build(presentation)).decode()
    assert "pp-presenter" in data       # presenter window mode
    assert "BroadcastChannel" in data   # cross-window sync
