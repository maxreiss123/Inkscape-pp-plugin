#!/usr/bin/env python3
"""Add a web-content region to the current slide.

Draw a rectangle where you want the content and select it, then run this command
with a URL (embedded as an iframe) or inline HTML/JS. The region renders live in
the interactive SVG export / browser preview; on the canvas it is a labelled box.
If nothing is selected, a centred region is created.
"""

import inkex
from pplib import webcontent
from pplib.model import Presentation


class WebContent(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--url", default="")
        pars.add_argument("--html", default="")
        pars.add_argument("--label", default="")
        pars.add_argument("--replace_selection", type=inkex.Boolean, default=True)

    @staticmethod
    def _abs_bbox(el):
        """Absolute bounding box, composing ancestor (layer) transforms.

        ``bounding_box()`` alone returns coordinates local to the element's
        layer; we compose the parent's transform to get canvas coordinates.
        """
        parent = el.getparent()
        tf = parent.composed_transform() if parent is not None else None
        return el.bounding_box(tf)

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        slide = pres.active_slide()
        if slide is None:
            inkex.errormsg("No active slide.")
            return
        if not self.options.url and not self.options.html:
            inkex.errormsg("Provide a URL or inline HTML for the web content.")
            return

        px, py, pw, ph = slide.bbox  # absolute page origin + size
        selection = list(self.svg.selection.values())
        if selection:
            bb = self._abs_bbox(selection[0])
            for el in selection[1:]:
                bb += self._abs_bbox(el)
            # Convert absolute selection bbox to slide-local coordinates.
            local_rect = (bb.left - px, bb.top - py, bb.width, bb.height)
            if self.options.replace_selection:
                for el in selection:
                    el.getparent().remove(el)
        else:
            local_rect = (0.2 * pw, 0.25 * ph, 0.6 * pw, 0.55 * ph)

        webcontent.add_web_region(
            slide, local_rect,
            src=self.options.url or None,
            html=self.options.html or None,
            label=self.options.label or None,
        )


if __name__ == "__main__":
    WebContent().run()
