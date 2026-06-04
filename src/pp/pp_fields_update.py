#!/usr/bin/env python3
"""Refresh auto-fields (slide numbers, total, date, footer) across all slides."""

import inkex
from pplib import constants as C
from pplib import fields
from pplib.model import Presentation


class UpdateFields(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--footer_text", default=None)
        pars.add_argument("--date_mode", default=None)
        pars.add_argument("--date_value", default=None)

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        if self.options.footer_text is not None:
            pres.set_config(C.A_FOOTER_TEXT, self.options.footer_text)
        if self.options.date_mode:
            pres.set_config(C.A_DATE_MODE, self.options.date_mode)
        if self.options.date_value is not None:
            pres.set_config(C.A_DATE_VALUE, self.options.date_value)
        fields.update_all(pres)


if __name__ == "__main__":
    UpdateFields().run()
