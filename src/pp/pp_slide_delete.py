#!/usr/bin/env python3
"""Delete the current slide.

Tip: in Inkscape you can assign a keyboard shortcut (e.g. Delete) to this command
via Edit > Preferences > Interface > Keyboard, searching for "Delete Slide".
"""

import inkex
from pplib import fields, pages
from pplib.model import Presentation


class DeleteSlide(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--source", default="current")  # current | index
        pars.add_argument("--index", type=int, default=1)

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        slides = pres.slides()
        if not slides:
            inkex.errormsg("No slides to delete.")
            return
        if len(slides) == 1:
            inkex.errormsg("Cannot delete the last remaining slide.")
            return
        if self.options.source == "index":
            i = max(1, min(self.options.index, len(slides))) - 1
            target = slides[i]
        else:
            target = pres.active_slide() or slides[0]
        pages.delete_slide(pres, target)
        fields.update_all(pres)


if __name__ == "__main__":
    DeleteSlide().run()
