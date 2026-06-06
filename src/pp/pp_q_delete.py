#!/usr/bin/env python3
"""Delete Slide (Quick): one-click action (no dialog). Assign a keyboard shortcut for speed."""

import inkex
from pplib import panel_actions as A
from pplib.model import Presentation


class QDelete(inkex.EffectExtension):
    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        msg = A.delete(pres)
        if msg.startswith(("Cannot", "No ")):
            inkex.errormsg(msg)


if __name__ == "__main__":
    QDelete().run()
