#!/usr/bin/env python3
"""Setup / initialise a presentation: canvas size, default master, first slide."""

import inkex
from pplib import constants as C
from pplib import document
from pplib.model import Presentation


class SetupPresentation(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--aspect", default="16:9")
        pars.add_argument("--width", type=float, default=1920.0)
        pars.add_argument("--height", type=float, default=1080.0)
        pars.add_argument("--footer_text", default="")
        pars.add_argument("--date_mode", default=C.DateMode.NONE)
        pars.add_argument("--author", default="")
        pars.add_argument("--first_layout", default=C.LayoutKey.TITLE)

    def effect(self):
        pres = Presentation(self.svg)
        if pres.is_initialized():
            inkex.errormsg("This document is already a presentation. "
                           "Use 'New slide' to add slides.")
            return
        document.init_presentation(
            pres,
            aspect=self.options.aspect,
            width=self.options.width,
            height=self.options.height,
            footer_text=self.options.footer_text,
            date_mode=self.options.date_mode,
            author=self.options.author,
            first_layout=self.options.first_layout,
        )


if __name__ == "__main__":
    SetupPresentation().run()
