#!/usr/bin/env python3
"""Export the presentation as a self-contained interactive SVG+JS file."""

import inkex
from pplib import jsexport
from pplib.model import Presentation


class ExportJS(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--out_path", default="")
        pars.add_argument("--transition", default="fade")
        pars.add_argument("--loop", type=inkex.Boolean, default=False)

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        if not self.options.out_path:
            inkex.errormsg("Please choose an output file path.")
            return
        jsexport.write(pres, self.options.out_path,
                       transition=self.options.transition,
                       loop=self.options.loop)
        inkex.errormsg("Exported interactive presentation to %s" % self.options.out_path)


if __name__ == "__main__":
    ExportJS().run()
