#!/usr/bin/env python3
"""Preview the presentation in the default web browser (presentation mode)."""

import inkex
from pplib import preview
from pplib.model import Presentation


class Preview(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--transition", default="fade")
        pars.add_argument("--start_index", type=int, default=1)
        pars.add_argument("--loop", type=inkex.Boolean, default=False)

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        path = preview.build_temp(pres, transition=self.options.transition,
                                  loop=self.options.loop,
                                  start=max(0, self.options.start_index - 1))
        preview.open_in_browser(path)


if __name__ == "__main__":
    Preview().run()
