"""Position / alignment helpers operating on the current selection.

Objects are repositioned by adjusting their transform translation. References can
be the selection's own bounding box, the page, or the page margins. Guides can be
dropped on the current page via the inkex Guides API.
"""

from . import constants as C


def _bbox_of(el):
    bb = el.bounding_box()
    return bb  # inkex BoundingBox with .left/.right/.top/.bottom/.center_x ...


def _translate(el, dx, dy):
    from inkex import Transform
    el.transform = Transform(translate=(dx, dy)) @ el.transform


def reference_box(objects, mode, page_bbox, margin=C.DEFAULT_MARGIN):
    """Return a reference (left, top, right, bottom) for alignment ops."""
    if mode == "page" and page_bbox is not None:
        x, y, w, h = page_bbox
        return (x, y, x + w, y + h)
    if mode == "margins" and page_bbox is not None:
        x, y, w, h = page_bbox
        return (x + margin * w, y + margin * h,
                x + (1 - margin) * w, y + (1 - margin) * h)
    # selection bbox
    boxes = [_bbox_of(o) for o in objects]
    left = min(b.left for b in boxes)
    top = min(b.top for b in boxes)
    right = max(b.right for b in boxes)
    bottom = max(b.bottom for b in boxes)
    return (left, top, right, bottom)


def align(objects, op, ref):
    """Align each object to edge/center of the reference box ``ref``."""
    rl, rt, rr, rb = ref
    for o in objects:
        bb = _bbox_of(o)
        dx = dy = 0.0
        if op == "left":
            dx = rl - bb.left
        elif op == "center_h":
            dx = (rl + rr) / 2 - bb.center_x
        elif op == "right":
            dx = rr - bb.right
        elif op == "top":
            dy = rt - bb.top
        elif op == "middle":
            dy = (rt + rb) / 2 - bb.center_y
        elif op == "bottom":
            dy = rb - bb.bottom
        if dx or dy:
            _translate(o, dx, dy)


def distribute(objects, axis):
    """Evenly space >=3 objects along 'h' or 'v' between the outer two."""
    if len(objects) < 3:
        return
    if axis == "h":
        objects = sorted(objects, key=lambda o: _bbox_of(o).center_x)
        first, last = _bbox_of(objects[0]).center_x, _bbox_of(objects[-1]).center_x
        step = (last - first) / (len(objects) - 1)
        for i, o in enumerate(objects[1:-1], start=1):
            target = first + i * step
            _translate(o, target - _bbox_of(o).center_x, 0)
    else:
        objects = sorted(objects, key=lambda o: _bbox_of(o).center_y)
        first, last = _bbox_of(objects[0]).center_y, _bbox_of(objects[-1]).center_y
        step = (last - first) / (len(objects) - 1)
        for i, o in enumerate(objects[1:-1], start=1):
            target = first + i * step
            _translate(o, 0, target - _bbox_of(o).center_y)


def add_guides(svg, page_bbox, margin=C.DEFAULT_MARGIN, title_safe=C.TITLE_SAFE_INSET):
    """Drop margin, center and title-safe guides on the current page.

    Uses ``NamedView.add_guide(position, orient)`` where ``orient`` True is a
    horizontal guide and False is vertical (inkex 1.x).
    """
    nv = svg.namedview
    x, y, w, h = page_bbox
    verticals = [x + margin * w, x + (1 - margin) * w, x + w / 2,
                 x + title_safe * w, x + (1 - title_safe) * w]
    horizontals = [y + margin * h, y + (1 - margin) * h, y + h / 2,
                   y + title_safe * h, y + (1 - title_safe) * h]
    for vx in verticals:
        _guide(nv, (vx, y + h / 2), vertical=True)
    for hy in horizontals:
        _guide(nv, (x + w / 2, hy), vertical=False)


def _guide(nv, position, vertical):
    """Create a guide line through ``position``; angle 90 = vertical, 0 = horizontal.

    The guide must be attached to the document before ``set_position`` because
    inkex resolves the y-flip against the root viewBox.
    """
    from inkex import Guide
    g = Guide()
    nv.add(g)
    g.set_position(position[0], position[1], angle=90 if vertical else 0)
