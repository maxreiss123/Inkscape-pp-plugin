#!/usr/bin/env python3
"""Export the presentation to a PowerPoint .pptx file.

Each slide becomes a full-slide image (rendered via cairosvg) so it looks exactly
as authored; speaker notes are written into the notes pages. Requires cairosvg.
"""

import inkex
from pplib import pptxexport
from pplib.model import Presentation


class ExportPPTX(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--out_path", default="")
        pars.add_argument("--scale", type=float, default=2.0)
        pars.add_argument("--include_notes", type=inkex.Boolean, default=True)

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        if not self.options.out_path:
            inkex.errormsg("Please choose an output .pptx path.")
            return
        try:
            import cairosvg  # noqa: F401
        except Exception:
            inkex.errormsg("PPTX export needs the 'cairosvg' Python package "
                           "(pip install cairosvg).")
            return
        try:
            summary = pptxexport.export(
                pres, self.options.out_path,
                scale=self.options.scale,
                include_notes=self.options.include_notes)
        except Exception as exc:  # noqa: BLE001
            inkex.errormsg("PPTX export failed: %s" % exc)
            return
        inkex.errormsg(summary)


if __name__ == "__main__":
    ExportPPTX().run()
