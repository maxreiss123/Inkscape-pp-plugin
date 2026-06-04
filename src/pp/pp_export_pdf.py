#!/usr/bin/env python3
"""Convenience PDF export: shells out to the Inkscape CLI (one page per slide).

Note: an effect extension cannot directly drive Inkscape's own file export, so we
save the current document to a temp file and invoke ``inkscape`` on it with
``--export-area-page`` (each native page becomes one PDF page). If the inkscape
binary is not on PATH, we tell the user to use File > Export instead.
"""

import copy
import os
import tempfile

import inkex
from pplib import anim


class ExportPDF(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--out_path", default="")

    def effect(self):
        if not self.options.out_path:
            inkex.errormsg("Please choose an output PDF path.")
            return
        fd, tmp_svg = tempfile.mkstemp(prefix="pp-export-", suffix=".svg")
        os.close(fd)
        # Export a copy with the authoring-only build badges removed, leaving the
        # user's document (and its badges) untouched.
        doc_copy = copy.deepcopy(self.document)
        anim.strip_badges_tree(doc_copy.getroot())
        doc_copy.write(tmp_svg)
        try:
            from inkex.command import inkscape
            inkscape(tmp_svg, export_type="pdf",
                     export_filename=self.options.out_path,
                     export_area_page=True)
            inkex.errormsg("Exported PDF to %s" % self.options.out_path)
        except Exception as exc:  # noqa: BLE001
            inkex.errormsg(
                "Automatic PDF export failed (%s).\n"
                "Use File > Export, choose 'Document' / all pages, format PDF."
                % exc)
        finally:
            try:
                os.remove(tmp_svg)
            except OSError:
                pass


if __name__ == "__main__":
    ExportPDF().run()
