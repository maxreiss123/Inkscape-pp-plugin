#!/usr/bin/env python3
"""Preview in Browser (Quick): build and open the deck. Assign a shortcut."""

import inkex
from pplib import preview
from pplib.model import Presentation


class QPreview(inkex.EffectExtension):
    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        try:
            preview.open_in_browser(preview.build_temp(pres))
        except Exception as exc:  # noqa: BLE001
            inkex.errormsg("Preview failed: %s" % exc)


if __name__ == "__main__":
    QPreview().run()
