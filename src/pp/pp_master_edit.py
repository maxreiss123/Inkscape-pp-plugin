#!/usr/bin/env python3
"""Edit the master definition (colors, fonts, logo, footer/number/date toggles).

Updates the JSON master definition and re-applies it to all slides so the change
is reflected immediately.
"""

import inkex
from pplib import template
from pplib.model import Presentation


class EditMaster(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--bg_color", type=inkex.Color, default=None)
        pars.add_argument("--accent_color", type=inkex.Color, default=None)
        pars.add_argument("--title_font_size", type=int, default=None)
        pars.add_argument("--body_font_size", type=int, default=None)
        pars.add_argument("--font_family", default=None)
        pars.add_argument("--logo_path", default=None)
        pars.add_argument("--show_footer", type=inkex.Boolean, default=None)
        pars.add_argument("--show_number", type=inkex.Boolean, default=None)
        pars.add_argument("--show_date", type=inkex.Boolean, default=None)
        pars.add_argument("--apply_now", type=inkex.Boolean, default=True)

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        master = template.ensure_master(pres)
        defn = master.definition

        def maybe(key, value, conv=lambda v: v):
            if value is not None and value != "":
                defn[key] = conv(value)

        maybe("bg_color", self.options.bg_color, lambda c: str(inkex.Color(c).to_rgb()))
        maybe("accent_color", self.options.accent_color, lambda c: str(inkex.Color(c).to_rgb()))
        maybe("title_font_size", self.options.title_font_size)
        maybe("body_font_size", self.options.body_font_size)
        maybe("font_family", self.options.font_family)
        maybe("logo_href", self.options.logo_path)
        if self.options.show_footer is not None:
            defn["show_footer"] = self.options.show_footer
        if self.options.show_number is not None:
            defn["show_number"] = self.options.show_number
        if self.options.show_date is not None:
            defn["show_date"] = self.options.show_date

        master.definition = defn
        if self.options.apply_now:
            # Restyle so font/size/colour edits are visible on existing slides.
            template.apply_to_all(pres, defn, restyle=True)


if __name__ == "__main__":
    EditMaster().run()
