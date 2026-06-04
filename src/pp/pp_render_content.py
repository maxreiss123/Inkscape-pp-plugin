#!/usr/bin/env python3
"""(Re)render content regions (Mermaid / code / Markdown) into native SVG.

Run this after editing a region's source so the rendered output on the slide is
refreshed. Markdown and code render in pure Python; Mermaid renders only if the
``mmdc`` (mermaid-cli) tool is installed, otherwise it falls back to a code block.
"""

import inkex
from pplib import webcontent
from pplib.model import Presentation


class RenderContent(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--scope", default="all")  # all | current

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        if self.options.scope == "current":
            slide = pres.active_slide()
            slides = [slide] if slide is not None else []
        else:
            slides = pres.slides()
        count = 0
        for slide in slides:
            for group, bounds in webcontent.iter_regions(slide.layer):
                if webcontent.render_into(group, bounds) is not None:
                    count += 1
        if count == 0:
            inkex.errormsg("No renderable content regions found.")


if __name__ == "__main__":
    RenderContent().run()
