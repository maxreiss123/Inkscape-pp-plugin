#!/usr/bin/env python3
"""Add a new slide from a layout."""

import inkex
from pplib import constants as C
from pplib import pages
from pplib.model import Presentation


class NewSlide(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--layout", default=C.LayoutKey.TITLE_CONTENT)
        pars.add_argument("--position", default="end")  # end | after
        pars.add_argument("--apply_master", type=inkex.Boolean, default=True)

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        position = None
        if self.options.position == "after":
            active = pres.active_slide()
            if active is not None:
                position = active.index + 1
        pages.add_slide(pres, self.options.layout, position=position,
                        apply_master=self.options.apply_master)


if __name__ == "__main__":
    NewSlide().run()
