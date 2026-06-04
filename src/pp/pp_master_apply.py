#!/usr/bin/env python3
"""Apply / refresh the master template on the current slide or all slides."""

import inkex
from pplib import template
from pplib.model import Presentation


class ApplyMaster(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--scope", default="all")  # all | current
        pars.add_argument("--overwrite_user", type=inkex.Boolean, default=False)

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        master = pres.master_by_id(None)
        if master is None:
            master = template.ensure_master(pres)
        defn = master.definition
        if self.options.scope == "current":
            slide = pres.active_slide()
            if slide is None:
                inkex.errormsg("No active slide.")
                return
            template.apply_master(pres, slide, defn,
                                  overwrite_user=self.options.overwrite_user)
        else:
            template.apply_to_all(pres, defn,
                                  overwrite_user=self.options.overwrite_user)


if __name__ == "__main__":
    ApplyMaster().run()
