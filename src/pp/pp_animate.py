#!/usr/bin/env python3
"""Add build / appear animations so objects reveal on click during playback.

Select the objects (or a multi-line text box / a group of bullets) and choose how
they should appear. In the browser preview / interactive export each click reveals
the next step before moving to the next slide. Inkscape and PDF show everything.
"""

import inkex
from pplib import anim
from pplib import constants as C
from pplib.model import Presentation


class Animate(inkex.EffectExtension):
    def add_arguments(self, pars):
        # sequence | bullets | together | clear | badges | hide_badges
        pars.add_argument("--action", default="sequence")
        pars.add_argument("--type", default=C.EffectType.APPEAR)
        pars.add_argument("--start", type=int, default=0)  # 0 => continue from slide max
        pars.add_argument("--badges", type=inkex.Boolean, default=True)

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        slide = pres.active_slide()

        # Badge-only actions don't need a selection.
        if self.options.action == "badges":
            if slide is not None:
                anim.refresh_badges(slide)
            return
        if self.options.action == "hide_badges":
            if slide is not None:
                anim.clear_badges(slide)
            return

        selection = list(self.svg.selection.values())
        if not selection:
            inkex.errormsg("Select one or more objects (or a bullet text box) first.")
            return

        if self.options.action == "clear":
            for el in selection:
                anim.clear_effects_deep(el)
            if slide is not None:
                anim.refresh_badges(slide)
            return

        start = self.options.start if self.options.start > 0 else (
            anim.slide_max_order(slide) + 1 if slide is not None else 1)

        targets = anim.resolve_targets(selection, self.options.action)
        anim.apply(targets, start, self.options.type,
                   together=(self.options.action == "together"))
        if slide is not None and self.options.badges:
            anim.refresh_badges(slide)


if __name__ == "__main__":
    Animate().run()
