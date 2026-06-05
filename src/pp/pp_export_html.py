#!/usr/bin/env python3
"""Export the presentation as a self-contained HTML file.

Vector mode inlines the interactive SVG (selectable text; optional font
embedding). Raster mode renders each slide to a PNG for guaranteed-identical
display with no font dependencies (needs cairosvg).
"""

import inkex
from pplib import htmlexport
from pplib.model import Presentation


class ExportHTML(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--out_path", default="")
        pars.add_argument("--mode", default="vector")  # vector | raster
        pars.add_argument("--transition", default="fade")
        pars.add_argument("--loop", type=inkex.Boolean, default=False)
        pars.add_argument("--embed_fonts", type=inkex.Boolean, default=False)
        pars.add_argument("--scale", type=float, default=2.0)
        pars.add_argument("--title", default="Presentation")

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        if not self.options.out_path:
            inkex.errormsg("Please choose an output .html path.")
            return
        try:
            if self.options.mode == "raster":
                try:
                    import cairosvg  # noqa: F401
                except Exception:
                    inkex.errormsg("Raster HTML needs the 'cairosvg' package "
                                   "(pip install cairosvg).")
                    return
                htmlexport.write(pres, self.options.out_path, mode="raster",
                                 scale=self.options.scale, title=self.options.title)
            else:
                htmlexport.write(pres, self.options.out_path, mode="vector",
                                 transition=self.options.transition,
                                 loop=self.options.loop, title=self.options.title,
                                 embed_fonts=self.options.embed_fonts)
        except Exception as exc:  # noqa: BLE001
            inkex.errormsg("HTML export failed: %s" % exc)
            return
        inkex.errormsg("Exported %s HTML to %s"
                       % (self.options.mode, self.options.out_path))


if __name__ == "__main__":
    ExportHTML().run()
