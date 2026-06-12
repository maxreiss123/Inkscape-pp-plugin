#!/usr/bin/env python3
"""Set the current slide as the slide master.

Design a slide on the canvas -- background colour/picture, a logo, a colour band,
styled title/body text -- then run this to make it the master for the whole deck
or just for slides of the same layout (so title and content masters can differ).
"""

import inkex
from pplib import masterfromslide
from pplib.model import Presentation


class SetMaster(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--scope", default="all")  # all | layout

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("This document is not a presentation yet. "
                           "Run Presentation > Setup first.")
            return
        slide = pres.active_slide()
        if slide is None:
            inkex.errormsg("No slide is selected. Click a slide, then try again.")
            return
        summary = masterfromslide.apply(pres, slide, scope=self.options.scope)
        inkex.errormsg(summary)


if __name__ == "__main__":
    SetMaster().run()
