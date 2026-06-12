#!/usr/bin/env python3
"""Import a slide master / theme from PowerPoint or LibreOffice.

Supports .pptx, .potx (PowerPoint template), .odp and .otp. Imports the slide
size/aspect, master background, accent, fonts and title/body styles, then
restyles the deck so the change is immediately visible.
"""

import os
import zipfile

import inkex
from pplib import constants as C
from pplib import document, mastersimport
from pplib.model import Presentation


class ImportMaster(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--file", default="")
        pars.add_argument("--resize", type=inkex.Boolean, default=True)
        pars.add_argument("--restyle", type=inkex.Boolean, default=True)
        pars.add_argument("--new_deck", type=inkex.Boolean, default=True)

    def effect(self):
        pres = Presentation(self.svg)
        path = self.options.file
        if not path:
            inkex.errormsg("Choose a .pptx, .potx, .odp or .otp file to import.")
            return
        if not os.path.exists(path):
            inkex.errormsg("File not found:\n%s" % path)
            return

        # Importing onto a blank document should just work: create a starter
        # deck so the imported theme has slides to style (the usual reason the
        # result looked "blank" was that Setup had not been run yet).
        created_deck = False
        if not pres.is_initialized():
            if not self.options.new_deck:
                inkex.errormsg("Run Presentation > Setup first, or enable "
                               "'Create a new deck from the template'.")
                return
            document.init_presentation(pres, aspect="16:9",
                                       first_layout=C.LayoutKey.TITLE)
            from pplib import pages
            pages.add_slide(pres, C.LayoutKey.TITLE_CONTENT)
            created_deck = True

        try:
            summary = mastersimport.apply_import(
                pres, path, resize=self.options.resize,
                restyle=self.options.restyle)
            if created_deck:
                summary += "\n(Created a new 2-slide deck from the template.)"
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
