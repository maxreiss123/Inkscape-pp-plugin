"""End-to-end test driving the real command handlers via their effect()."""

import importlib.util
import os

from conftest import BLANK_SVG, run_effect, to_bytes

PP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "src", "pp")


def _load(handler):
    spec = importlib.util.spec_from_file_location(
        handler, os.path.join(PP_DIR, handler + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_full_authoring_flow():
    from pplib import constants as C
    from pplib import svgutil as S
    from pplib.model import Presentation

    setup = _load("pp_setup")
    new = _load("pp_slide_new")
    apply_master = _load("pp_master_apply")

    # Setup
    svg = run_effect(setup.SetupPresentation,
                     ["--aspect=16:9", "--footer_text=Demo", "--first_layout=title"],
                     BLANK_SVG.encode())
    data = to_bytes(svg)

    # Add two slides
    svg = run_effect(new.NewSlide, ["--layout=title_content"], data)
    data = to_bytes(svg)
    svg = run_effect(new.NewSlide, ["--layout=two_content"], data)
    data = to_bytes(svg)

    pres = Presentation(svg)
    assert pres.slide_count() == 3
    assert pres.is_initialized()

    # Apply master to all
    svg = run_effect(apply_master.ApplyMaster, ["--scope=all"], data)
    data = to_bytes(svg)

    # Numbers correct
    pres = Presentation(svg)
    nums = []
    for s in pres.slides():
        for el in s.layer.iter():
            if S.get_pp(el, C.A_FIELD) == C.Field.NUMBER:
                nums.append(S.text_content(el))
    assert nums == ["1", "2", "3"]


def test_setup_twice_is_guarded():
    from pplib.model import Presentation
    setup = _load("pp_setup")
    svg = run_effect(setup.SetupPresentation, ["--aspect=16:9"], BLANK_SVG.encode())
    data = to_bytes(svg)
    # Second setup should not add another presentation/slide.
    svg2 = run_effect(setup.SetupPresentation, ["--aspect=16:9"], data)
    assert Presentation(svg2).slide_count() == 1
