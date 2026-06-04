#!/usr/bin/env python3
"""Reorder the current slide (move up/down/front/back or to an index)."""

import inkex
from pplib import fields, pages
from pplib.model import Presentation


class ReorderSlide(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--mode", default="up")  # up | down | front | back | index
        pars.add_argument("--target_index", type=int, default=1)

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        slides = pres.slides()
        if not slides:
            inkex.errormsg("No slides to reorder.")
            return
        slide = pres.active_slide() or slides[0]
        mode = self.options.mode
        if mode == "up":
            pages.move_relative(pres, slide, -1)
        elif mode == "down":
            pages.move_relative(pres, slide, +1)
        elif mode == "front":
            pages.reorder(pres, slide, 0)
        elif mode == "back":
            pages.reorder(pres, slide, len(slides) - 1)
        else:  # index (1-based)
            pages.reorder(pres, slide, self.options.target_index - 1)
        fields.update_all(pres)


if __name__ == "__main__":
    ReorderSlide().run()
