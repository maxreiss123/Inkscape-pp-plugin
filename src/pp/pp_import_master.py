#!/usr/bin/env python3
"""Import a slide master's theme from a PowerPoint (.pptx) or LibreOffice (.odp)
file: slide size/aspect, background colour, accent colour and body font.
"""

import inkex
from pplib import mastersimport
from pplib.model import Presentation


class ImportMaster(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--file", default="")
        pars.add_argument("--resize", type=inkex.Boolean, default=True)

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        if not self.options.file:
            inkex.errormsg("Choose a .pptx or .odp file to import.")
            return
        try:
            summary = mastersimport.apply_import(pres, self.options.file,
                                                 resize=self.options.resize)
        except ValueError as exc:
            inkex.errormsg(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            inkex.errormsg("Could not import master: %s" % exc)
            return
        inkex.errormsg(summary)


if __name__ == "__main__":
    ImportMaster().run()
