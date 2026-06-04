#!/usr/bin/env python3
"""Position / alignment helpers for the selected objects."""

import inkex
from pplib import align as A
from pplib import svgutil as S
from pplib.model import Presentation


class AlignHelper(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--op", default="center_h")
        pars.add_argument("--relative_to", default="page")  # page | margins | selection

    def _current_page_bbox(self, pres):
        slide = pres.active_slide()
        if slide is not None and slide.page is not None:
            return S.page_bbox(slide.page)
        return (0.0, 0.0, pres.width, pres.height)

    def effect(self):
        pres = Presentation(self.svg)
        objects = list(self.svg.selection.values())
        page_bbox = self._current_page_bbox(pres)

        op = self.options.op
        if op == "add_guides":
            A.add_guides(self.svg, page_bbox)
            return
        if not objects:
            inkex.errormsg("Select one or more objects first.")
            return
        if op in ("distribute_h", "distribute_v"):
            A.distribute(objects, "h" if op.endswith("_h") else "v")
            return

        ref = A.reference_box(objects, self.options.relative_to, page_bbox)
        A.align(objects, op, ref)


if __name__ == "__main__":
    AlignHelper().run()
