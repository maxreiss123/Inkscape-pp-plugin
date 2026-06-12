#!/usr/bin/env python3
"""Import a slide master / theme from PowerPoint or LibreOffice.

Supports .pptx, .potx (PowerPoint template), .odp and .otp. Imports the slide
size/aspect, master background, accent, fonts and title/body styles, then
restyles the deck so the change is immediately visible.
"""

import os
import zipfile

import inkex
from pplib import mastersimport
from pplib.model import Presentation


class ImportMaster(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--file", default="")
        pars.add_argument("--resize", type=inkex.Boolean, default=True)
        pars.add_argument("--restyle", type=inkex.Boolean, default=True)

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        path = self.options.file
        if not path:
            inkex.errormsg("Choose a .pptx, .potx, .odp or .otp file to import.")
            return
        if not os.path.exists(path):
            inkex.errormsg("File not found:\n%s" % path)
            return
        try:
            summary = mastersimport.apply_import(
                pres, path, resize=self.options.resize,
                restyle=self.options.restyle)
        except ValueError as exc:
            inkex.errormsg(str(exc))
            return
        except zipfile.BadZipFile:
            inkex.errormsg(
                "This is not a valid PowerPoint/LibreOffice file:\n%s\n"
                "(Old binary .ppt files are not supported -- save as .pptx.)"
                % path)
            return
        except Exception as exc:  # noqa: BLE001
            inkex.errormsg("Could not import master: %s" % exc)
            return
        inkex.errormsg(summary)


if __name__ == "__main__":
    ImportMaster().run()
