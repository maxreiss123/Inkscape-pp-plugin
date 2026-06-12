import inkex
from pplib import constants as C
from pplib import document, jsexport, margins, slides
from pplib import svgutil as S
from pplib.model import Presentation


def _fresh(margin=0.0):
    root = inkex.load_svg(
        b'<svg xmlns="http://www.w3.org/2000/svg" '
        b'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
        b'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd" '
        b'width="100" height="100" viewBox="0 0 100 100">'
        b'<sodipodi:namedview id="nv"/></svg>').getroot()
    pres = Presentation(root)
    document.init_presentation(pres, aspect="16:9",
                               first_layout=C.LayoutKey.BLANK, margin=margin)
    return pres


def _guides(slide):
    return [e for e in slide.layer if margins.is_margin(e)]


def test_setup_with_margin_draws_guide():
    pres = _fresh(margin=0.05)
    assert margins.get_margin(pres) == 0.05
    assert margins.margins_shown(pres)
    g = _guides(pres.slides()[0])
    assert len(g) == 1
    # Guide is inset by 5% of the page (1920x1080 -> x=96, y=54).
    assert abs(float(g[0].get("x")) - 96) < 1 and abs(float(g[0].get("y")) - 54) < 1


def test_no_margin_no_guide():
    pres = _fresh(margin=0.0)
    assert _guides(pres.slides()[0]) == []


def test_new_slides_get_guides():
    from pplib import pages
    pres = _fresh(margin=0.06)
    s = pages.add_slide(pres, C.LayoutKey.TITLE_CONTENT)
    assert len(_guides(s)) == 1


def test_toggle_off_removes_guides():
    pres = _fresh(margin=0.05)
    margins.set_margin(pres, 0.05, show=False)
    margins.refresh(pres)
    assert _guides(pres.slides()[0]) == []


def test_guides_stripped_from_interactive_export():
    pres = _fresh(margin=0.05)
    tree = jsexport.build(pres)
    assert [e for e in tree.getroot().iter() if margins.is_margin(e)] == []


def test_guides_stripped_from_slide_render():
    pres = _fresh(margin=0.05)
    tree, _ = slides.slide_svg_tree(pres, pres.slides()[0])
    assert [e for e in tree.getroot().iter()
            if S.get_pp(e, C.A_MANAGED) == margins.MANAGED] == []
