#!/usr/bin/env python3
"""One-click command (no dialog) — assign a keyboard shortcut for speed."""

import inkex
from pplib import panel_actions as A
from pplib.model import Presentation


class QMoveUp(inkex.EffectExtension):
    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        msg = A.move(pres, -1)
        if msg.startswith(("Cannot", "No ")):
            inkex.errormsg(msg)


if __name__ == "__main__":
    QMoveUp().run()
