#!/usr/bin/env python3
"""Import a whole PowerPoint presentation (slides + content) into the deck.

Reads .pptx / .pptm / .ppsx (and .potx) files: every slide's title, subtitle and
bullet text, free text boxes, pictures / shapes and speaker notes are recreated
as native slides, and the file's theme (size, master background, fonts, colours)
is applied on top. Use *Import Master* instead if you only want a template's look.
"""

import os
import zipfile

import inkex
from pplib import pptximport
from pplib.model import Presentation


class ImportPptx(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--file", default="")
        pars.add_argument("--replace", type=inkex.Boolean, default=True)
        pars.add_argument("--import_notes", type=inkex.Boolean, default=True)

    def effect(self):
        pres = Presentation(self.svg)
        path = self.options.file
        if not path:
            inkex.errormsg("Choose a .pptx / .pptm / .ppsx file to import.")
            return
        if not os.path.exists(path):
            inkex.errormsg("File not found:\n%s" % path)
            return
        try:
            count, summary = pptximport.import_presentation(
                pres, path,
                replace=self.options.replace,
                import_notes=self.options.import_notes)
        except ValueError as exc:
            inkex.errormsg(str(exc))
            return
        except zipfile.BadZipFile:
            inkex.errormsg(
                "This is not a valid PowerPoint file:\n%s\n"
                "(Old binary .ppt files are not supported -- save as .pptx.)"
                % path)
            return
        except Exception as exc:  # noqa: BLE001
            inkex.errormsg("Could not import presentation: %s" % exc)
            return
        if count == 0:
            inkex.errormsg(
                "No slides were found in this file.\n"
                "If it is only a template (no slides), use Import Master.")
            return
        inkex.errormsg(summary)


if __name__ == "__main__":
    ImportPptx().run()
