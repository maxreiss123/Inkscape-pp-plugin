#!/usr/bin/env python3
"""Apply Master (Quick): one-click action (no dialog). Assign a keyboard shortcut for speed."""

import inkex
from pplib import panel_actions as A
from pplib.model import Presentation


class QMaster(inkex.EffectExtension):
    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        A.apply_master(pres)


if __name__ == "__main__":
    QMaster().run()
