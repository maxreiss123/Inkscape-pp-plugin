import inkex
from pplib import align as A


def _rect(x, y, w, h):
    r = inkex.Rectangle(x=str(x), y=str(y), width=str(w), height=str(h))
    return r


def _svg_with(objects):
    root = inkex.load_svg(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000" '
        b'viewBox="0 0 1000 1000"/>'
    ).getroot()
    for o in objects:
        root.add(o)
    return root


def test_align_left_to_page():
    a, b = _rect(100, 10, 50, 50), _rect(300, 10, 50, 50)
    _svg_with([a, b])
    A.align([a, b], "left", (0, 0, 1000, 1000))
    assert a.bounding_box().left == 0
    assert b.bounding_box().left == 0


def test_align_center_h_to_page():
    a = _rect(100, 10, 100, 50)
    _svg_with([a])
    A.align([a], "center_h", (0, 0, 1000, 1000))
    assert abs(a.bounding_box().center_x - 500) < 1e-6


def test_distribute_h_even_spacing():
    a, b, c = _rect(0, 0, 10, 10), _rect(50, 0, 10, 10), _rect(200, 0, 10, 10)
    _svg_with([a, b, c])
    A.distribute([a, b, c], "h")
    centers = sorted(o.bounding_box().center_x for o in (a, b, c))
    # Middle element should be midway between the outer two.
    assert abs(centers[1] - (centers[0] + centers[2]) / 2) < 1e-6


def test_reference_margins():
    ref = A.reference_box([], "margins", (0, 0, 1000, 500), margin=0.1)
    assert ref == (100.0, 50.0, 900.0, 450.0)
