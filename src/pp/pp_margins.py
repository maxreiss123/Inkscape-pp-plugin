#!/usr/bin/env python3
"""Set or toggle the slide safe-area margin guides.

Guides are shown on every slide while editing and are hidden in the presentation
(browser export, PDF, PPTX, raster HTML).
"""

import inkex
from pplib import margins
from pplib.model import Presentation


class Margins(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--margin", type=float, default=0.05)
        pars.add_argument("--show", type=inkex.Boolean, default=True)

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        margins.set_margin(pres, self.options.margin, show=self.options.show)
        margins.refresh(pres)


if __name__ == "__main__":
    Margins().run()
