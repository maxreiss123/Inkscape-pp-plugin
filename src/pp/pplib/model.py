"""High-level wrappers over the SVG document: Presentation, Slide, Master.

These give a stable object model on top of the raw SVG so the command handlers
stay thin. A *slide* is an Inkscape layer (the authoritative container) paired
with a native page; a *master* is a hidden layer plus a JSON definition.
"""

import json

from . import constants as C
from . import svgutil as S


class Slide:
    """Wraps a slide layer (``inkscape:groupmode='layer'`` with pp:role=slide)."""

    def __init__(self, pres, layer):
        self.pres = pres
        self.layer = layer

    @property
    def slide_id(self):
        return S.get_pp(self.layer, C.A_SLIDE_ID)

    @property
    def index(self):
        return int(S.get_pp(self.layer, C.A_INDEX, "0"))

    @index.setter
    def index(self, value):
        S.set_pp(self.layer, C.A_INDEX, int(value))

    @property
    def layout(self):
        return S.get_pp(self.layer, C.A_LAYOUT, C.LayoutKey.BLANK)

    @property
    def master_id(self):
        return S.get_pp(self.layer, C.A_MASTER)

    @master_id.setter
    def master_id(self, value):
        S.set_pp(self.layer, C.A_MASTER, value)

    @property
    def label(self):
        return self.layer.get(C.ink("label"))

    @property
    def page(self):
        return self.pres.page_for_slide(self)

    @property
    def bbox(self):
        page = self.page
        if page is not None:
            return S.page_bbox(page)
        return (0.0, 0.0, self.pres.width, self.pres.height)

    def placeholders(self):
        from . import layouts
        return list(layouts.iter_placeholders(self.layer))

    def placeholder(self, ph_id):
        for g in self.placeholders():
            if S.get_pp(g, C.A_PH_ID) == ph_id:
                return g
        return None

    def __repr__(self):
        return "<Slide id=%s index=%s layout=%s>" % (
            self.slide_id, self.index, self.layout)


class Master:
    """Wraps a master layer and its JSON definition."""

    def __init__(self, pres, layer):
        self.pres = pres
        self.layer = layer

    @property
    def master_id(self):
        return self.layer.get("id")

    @property
    def definition(self):
        raw = S.get_pp(self.layer, C.A_MASTER_DEF)
        return json.loads(raw) if raw else {}

    @definition.setter
    def definition(self, value):
        S.set_pp(self.layer, C.A_MASTER_DEF, json.dumps(value))


class Presentation:
    """Wraps the SVG document as a presentation."""

    def __init__(self, svg):
        self.svg = svg

    # -- discovery ----------------------------------------------------------
    @classmethod
    def from_svg(cls, svg):
        return cls(svg)

    @property
    def root(self):
        return self.svg

    @property
    def namedview(self):
        return self.svg.namedview

    @property
    def width(self):
        return float(self.svg.viewbox_width or self.svg.unittouu(self.svg.get("width", 0)))

    @property
    def height(self):
        return float(self.svg.viewbox_height or self.svg.unittouu(self.svg.get("height", 0)))

    def is_initialized(self):
        return S.get_pp(self.svg, C.A_ROLE) == C.Role.PRESENTATION

    # -- config -------------------------------------------------------------
    def get_config(self, name, default=None):
        return S.get_pp(self.svg, name, default)

    def set_config(self, name, value):
        S.set_pp(self.svg, name, value)

    # -- slides -------------------------------------------------------------
    def _slide_layers(self):
        from inkex import Layer
        out = []
        for child in self.svg:
            if isinstance(child, Layer) and S.get_pp(child, C.A_ROLE) == C.Role.SLIDE:
                out.append(child)
        return out

    def slides(self):
        """Return slides ordered by their pp:index."""
        slides = [Slide(self, layer) for layer in self._slide_layers()]
        slides.sort(key=lambda s: s.index)
        return slides

    def slide_count(self):
        return len(self._slide_layers())

    def slide_by_id(self, slide_id):
        for s in self.slides():
            if s.slide_id == slide_id:
                return s
        return None

    def active_slide(self):
        """Best-effort current slide via the namedview current-layer attr."""
        from inkex import Layer
        cur = self.namedview.get(C.ink("current-layer"))
        if cur:
            el = self.svg.getElementById(cur)
            # Walk up to the enclosing slide layer.
            while el is not None:
                if isinstance(el, Layer) and S.get_pp(el, C.A_ROLE) == C.Role.SLIDE:
                    return Slide(self, el)
                el = el.getparent()
        slides = self.slides()
        return slides[0] if slides else None

    # -- masters ------------------------------------------------------------
    def _master_layers(self):
        from inkex import Layer
        return [c for c in self.svg
                if isinstance(c, Layer) and S.get_pp(c, C.A_ROLE) == C.Role.MASTER]

    def masters(self):
        return [Master(self, layer) for layer in self._master_layers()]

    def master_by_id(self, master_id):
        for m in self.masters():
            if m.master_id == master_id:
                return m
        if self.masters():
            return self.masters()[0]
        return None

    # -- page <-> slide linking (implemented in pages.py) -------------------
    def page_for_slide(self, slide):
        from . import pages
        return pages.page_for_slide(self, slide)
