#!/usr/bin/env python3
"""Duplicate the current (or a chosen) slide."""

import inkex
from pplib import fields, pages
from pplib.model import Presentation


class DuplicateSlide(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--source", default="current")  # current | index
        pars.add_argument("--index", type=int, default=1)
        pars.add_argument("--count", type=int, default=1)

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        slides = pres.slides()
        if not slides:
            inkex.errormsg("No slides to duplicate.")
            return
        if self.options.source == "index":
            i = max(1, min(self.options.index, len(slides))) - 1
            source = slides[i]
        else:
            source = pres.active_slide() or slides[0]
        for _ in range(max(1, self.options.count)):
            source = pages.duplicate_slide(pres, source)
        fields.update_all(pres)


if __name__ == "__main__":
    DuplicateSlide().run()
