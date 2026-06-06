#!/usr/bin/env python3
"""New Slide (Quick): one-click action (no dialog). Assign a keyboard shortcut for speed."""

import inkex
from pplib import panel_actions as A
from pplib.model import Presentation


class QNewSlide(inkex.EffectExtension):
    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        A.new_slide(pres)


if __name__ == "__main__":
    QNewSlide().run()
