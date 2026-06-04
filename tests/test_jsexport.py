import json
import re

import lxml.etree as ET
from pplib import jsexport


def test_export_is_valid_xml(presentation):
    tree = jsexport.build(presentation, transition="fade")
    data = ET.tostring(tree)
    # Re-parse to ensure it is well-formed.
    ET.fromstring(data)


def test_slides_tagged(presentation):
    tree = jsexport.build(presentation)
    root = tree.getroot()
    tagged = root.findall(".//*[@data-pp-slide]")
    assert len(tagged) == 3
    for el in tagged:
        assert el.get("data-pp-bbox")


def test_config_count_matches(presentation):
    tree = jsexport.build(presentation, transition="fade", loop=True)
    data = ET.tostring(tree).decode()
    m = re.search(r"PP_CONFIG = (\{.*?\});", data, re.S)
    assert m
    cfg = json.loads(m.group(1))
    assert cfg["count"] == 3
    assert cfg["transition"] == "fade"
    assert cfg["loop"] is True


def test_player_script_embedded(presentation):
    data = ET.tostring(jsexport.build(presentation)).decode()
    assert "PP_CONFIG" in data
    assert "addEventListener" in data  # player.js content present


def test_master_and_namedview_stripped(presentation):
    tree = jsexport.build(presentation)
    root = tree.getroot()
    from pplib import constants as C
    from pplib import svgutil as S
    masters = [e for e in root if S.get_pp(e, C.A_ROLE) == C.Role.MASTER]
    assert masters == []
    assert root.find("{%s}namedview" % C.SODIPODI_NS) is None
