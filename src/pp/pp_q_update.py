#!/usr/bin/env python3
"""One-click command (no dialog) — assign a keyboard shortcut for speed."""

import inkex
from pplib import panel_actions as A
from pplib.model import Presentation


class QUpdate(inkex.EffectExtension):
    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        A.update_fields(pres)


if __name__ == "__main__":
    QUpdate().run()
