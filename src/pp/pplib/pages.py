"""Page <-> layer synchronisation -- the heart of the slide model.

Each slide owns a native ``inkscape:page`` (drives PDF export) and a parallel
Inkscape layer (the authoritative content container). This module creates,
duplicates, reorders and re-tiles them while keeping the two in lock-step.

All native-page API calls are funnelled through here so version differences are
contained. We construct :class:`inkex.elements._meta.Page` elements directly
rather than via ``namedview.new_page`` because the latter auto-inserts an extra
viewBox page on the first call of a fresh document.
"""

from . import constants as C
from . import layouts as L
from . import svgutil as S
from .model import Slide


def _Page():
    from inkex.elements._meta import Page
    return Page


def _new_layer(label):
    from inkex import Layer
    return Layer.new(label)


# ---------------------------------------------------------------------------
# Linking
# ---------------------------------------------------------------------------
def iter_pages(pres):
    # NB: use _get_pages() (raw findall), not get_pages(): the latter
    # synthesises a fake viewBox page for single-page documents and would hide
    # the real page element (and our page-id link) when only one slide exists.
    return pres.namedview._get_pages()


def page_for_slide(pres, slide):
    sid = slide.slide_id
    for page in iter_pages(pres):
        if S.get_pp(page, C.A_PAGE_ID) == sid:
            return page
    return None


def slide_for_page(pres, page):
    pid = S.get_pp(page, C.A_PAGE_ID)
    return pres.slide_by_id(pid) if pid else None


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------
def _make_page(pres, slide_id, index, x, y, w, h):
    Page = _Page()
    page = Page.new(width=str(w), height=str(h), x=str(x), y=str(y))
    page.label = "Slide %d" % (index + 1)
    S.set_pp(page, C.A_PAGE_ID, slide_id)
    pres.namedview.add(page)
    return page


def _make_slide_layer(pres, slide_id, index, layout_key):
    layer = _new_layer("Slide %d" % (index + 1))
    S.set_pp(layer, C.A_ROLE, C.Role.SLIDE)
    S.set_pp(layer, C.A_SLIDE_ID, slide_id)
    S.set_pp(layer, C.A_INDEX, index)
    S.set_pp(layer, C.A_LAYOUT, layout_key)
    pres.svg.add(layer)
    return layer


def add_slide(pres, layout_key=C.LayoutKey.BLANK, position=None, apply_master=True):
    """Create a new slide (page + layer) and return a :class:`Slide`.

    ``position`` is the zero-based index to insert at; ``None`` appends at end.
    Placeholders for ``layout_key`` are instantiated and (optionally) the
    presentation's default master is applied.
    """
    count = pres.slide_count()
    if position is None or position > count:
        position = count
    if position < 0:
        position = 0

    slide_id = S.uuid_slide_id()
    w, h = pres.width, pres.height

    # Append at logical end first; relayout_pages fixes geometry/order.
    layer = _make_slide_layer(pres, slide_id, count, layout_key)
    _make_page(pres, slide_id, count, count * (w + C.PAGE_GUTTER), 0, w, h)
    slide = Slide(pres, layer)

    # Shift indices to open a slot at `position`, then place the new slide.
    _open_slot(pres, slide, position)

    # Placeholders are authored in local coordinates (0,0,w,h); the slide layer's
    # transform (set by relayout_pages) translates them onto the page.
    family = _font_family(pres)
    L.instantiate(layer, layout_key, slide.content_bbox, font_family=family)

    if apply_master:
        from . import template
        # Always ensure a master exists so a new slide reliably gets its
        # background and number/footer fields (never a blank white page).
        master = template.ensure_master(pres)
        template.apply_master(pres, slide, master.definition)

    # Draw the safe-area margin guide (authoring aid, stripped from exports).
    from . import margins
    margins.refresh_slide(slide, margins.get_margin(pres), margins.margins_shown(pres))

    relayout_pages(pres)
    return slide


def _open_slot(pres, new_slide, position):
    """Renumber slides so ``new_slide`` ends up at ``position``."""
    others = [s for s in pres.slides() if s.slide_id != new_slide.slide_id]
    others.sort(key=lambda s: s.index)
    ordered = others[:position] + [new_slide] + others[position:]
    for i, s in enumerate(ordered):
        s.index = i


# ---------------------------------------------------------------------------
# Duplication
# ---------------------------------------------------------------------------
def duplicate_slide(pres, source):
    """Deep-copy ``source`` slide; the copy is inserted right after it."""
    new_id = S.uuid_slide_id()
    new_layer = source.layer.copy()
    S.set_pp(new_layer, C.A_SLIDE_ID, new_id)
    # Refresh ids on the clone so nothing collides.
    new_layer.set("id", S.new_id(pres.svg, "layer"))
    _reset_ids(pres.svg, new_layer)
    pres.svg.add(new_layer)

    w, h = source.bbox[2], source.bbox[3]
    _make_page(pres, new_id, pres.slide_count() - 1, 0, 0, w, h)

    clone = Slide(pres, new_layer)
    _open_slot(pres, clone, source.index + 1)
    relayout_pages(pres)
    return clone


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------
def delete_slide(pres, slide):
    """Remove a slide's layer and its page, then re-tile the remainder."""
    page = page_for_slide(pres, slide)
    if page is not None:
        page.getparent().remove(page)
    slide.layer.getparent().remove(slide.layer)
    relayout_pages(pres)


def _reset_ids(svg, root):
    for el in root.iter():
        if el is root:
            continue
        if el.get("id"):
            el.set("id", S.new_id(svg, "el"))


# ---------------------------------------------------------------------------
# Reordering
# ---------------------------------------------------------------------------
def reorder(pres, slide, new_index):
    """Move ``slide`` to ``new_index`` (clamped) and re-tile pages."""
    slides = pres.slides()
    count = len(slides)
    new_index = max(0, min(new_index, count - 1))
    others = [s for s in slides if s.slide_id != slide.slide_id]
    ordered = others[:new_index] + [slide] + others[new_index:]
    for i, s in enumerate(ordered):
        s.index = i
    relayout_pages(pres)


def move_relative(pres, slide, delta):
    reorder(pres, slide, slide.index + delta)


# ---------------------------------------------------------------------------
# Re-tiling / sync
# ---------------------------------------------------------------------------
def relayout_pages(pres):
    """Recompute page x-offsets and DOM/page order from slide pp:index.

    The slide layer's content keeps its own coordinates; the page simply frames
    a horizontal strip of the canvas. Each slide layer is translated so its
    local origin lands on its page origin.
    """
    slides = pres.slides()  # already sorted by index
    w, h = pres.width, pres.height
    for i, slide in enumerate(slides):
        slide.index = i
        x = i * (w + C.PAGE_GUTTER)
        page = page_for_slide(pres, slide)
        if page is None:
            page = _make_page(pres, slide.slide_id, i, x, 0, w, h)
        else:
            page.set("x", str(x))
            page.set("y", "0")
            page.set("width", str(w))
            page.set("height", str(h))
            page.label = "Slide %d" % (i + 1)
        _place_layer(slide.layer, x, 0)
        # Keep DOM layer order aligned with slide order for predictable z-stacking
        # between slides (within a slide, child z-order is preserved).
    _reorder_layers_in_dom(pres, slides)


def _place_layer(layer, x, y):
    """Set the layer transform so its local (0,0) maps to canvas (x, y)."""
    from inkex import Transform
    layer.transform = Transform(translate=(x, y))


def _reorder_layers_in_dom(pres, slides):
    """Re-append slide layers to the SVG root in slide order."""
    for slide in slides:
        pres.svg.append(slide.layer)  # append moves the existing element


def sync(pres):
    """Repair missing page<->layer links and re-tile.

    Ensures every slide layer has a matching page; drops orphan pages whose
    slide id no longer exists.
    """
    valid_ids = {s.slide_id for s in pres.slides()}
    for page in list(iter_pages(pres)):
        pid = S.get_pp(page, C.A_PAGE_ID)
        if pid and pid not in valid_ids:
            page.getparent().remove(page)
    relayout_pages(pres)


def _font_family(pres):
    master = pres.master_by_id(None)
    if master is not None:
        return master.definition.get("font_family", "sans-serif")
    return "sans-serif"
