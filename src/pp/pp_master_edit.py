#!/usr/bin/env python3
"""Edit the slide master: background, logo, fonts, sizes, colours and fields.

Updates the master definition and re-applies it to every slide (restyling text
so changes are visible immediately). Images are embedded, so they survive
save/reload and export.
"""

import base64
import os

import inkex
from pplib import template
from pplib.model import Presentation

_MIME = {"png": "png", "jpg": "jpeg", "jpeg": "jpeg", "gif": "gif",
         "svg": "svg+xml", "webp": "webp", "bmp": "bmp"}


def _data_uri(path):
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    with open(path, "rb") as fh:
        data = fh.read()
    return "data:image/%s;base64,%s" % (_MIME.get(ext, "png"),
                                        base64.b64encode(data).decode("ascii"))


def _hex(color):
    if color is None:
        return None
    rgb = inkex.Color(color).to_rgb()
    return "#%02X%02X%02X" % (int(rgb[0]), int(rgb[1]), int(rgb[2]))


_LOGO_POS = {
    "top-left": lambda s: [0.04, 0.04, s, s],
    "top-right": lambda s: [0.96 - s, 0.04, s, s],
    "bottom-left": lambda s: [0.04, 0.96 - s, s, s],
    "bottom-right": lambda s: [0.96 - s, 0.96 - s, s, s],
}


class EditMaster(inkex.EffectExtension):
    def add_arguments(self, pars):
        # Background
        pars.add_argument("--bg_mode", default="keep")  # keep|color|image|none
        pars.add_argument("--bg_color", type=inkex.Color, default=None)
        pars.add_argument("--bg_image", default="")
        # Logo
        pars.add_argument("--logo_path", default="")
        pars.add_argument("--logo_pos", default="top-right")
        pars.add_argument("--logo_size", type=float, default=0.12)
        pars.add_argument("--logo_clear", type=inkex.Boolean, default=False)
        # Fonts / colours
        pars.add_argument("--font_family", default="")
        pars.add_argument("--title_font_size", type=int, default=0)
        pars.add_argument("--body_font_size", type=int, default=0)
        pars.add_argument("--accent_color", type=inkex.Color, default=None)
        pars.add_argument("--title_color", type=inkex.Color, default=None)
        pars.add_argument("--text_color", type=inkex.Color, default=None)
        # Fields
        pars.add_argument("--show_footer", type=inkex.Boolean, default=None)
        pars.add_argument("--show_number", type=inkex.Boolean, default=None)
        pars.add_argument("--show_date", type=inkex.Boolean, default=None)
        pars.add_argument("--footer_text", default=None)
        pars.add_argument("--apply_now", type=inkex.Boolean, default=True)

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        o = self.options
        master = template.ensure_master(pres)
        defn = master.definition

        # --- Background ---------------------------------------------------
        if o.bg_mode == "color" and o.bg_color is not None:
            defn["bg_color"] = _hex(o.bg_color)
            defn.pop("bg_image", None)
        elif o.bg_mode == "image" and o.bg_image:
            if not os.path.exists(o.bg_image):
                inkex.errormsg("Background image not found:\n%s" % o.bg_image)
                return
            defn["bg_image"] = _data_uri(o.bg_image)
        elif o.bg_mode == "none":
            defn["bg_color"] = "#ffffff"
            defn.pop("bg_image", None)
            defn.pop("bg_shapes", None)

        # --- Logo ---------------------------------------------------------
        if o.logo_clear:
            defn.pop("logo_href", None)
        elif o.logo_path:
            if not os.path.exists(o.logo_path):
                inkex.errormsg("Logo image not found:\n%s" % o.logo_path)
                return
            defn["logo_href"] = _data_uri(o.logo_path)
            size = min(0.5, max(0.03, o.logo_size))
            defn["logo_rect"] = _LOGO_POS.get(o.logo_pos, _LOGO_POS["top-right"])(size)

        # --- Fonts / colours ---------------------------------------------
        if o.font_family:
            defn["font_family"] = o.font_family
        if o.title_font_size:
            defn["title_font_size"] = o.title_font_size
        if o.body_font_size:
            defn["body_font_size"] = o.body_font_size
        for key, val in (("accent_color", o.accent_color),
                         ("title_color", o.title_color),
                         ("text_color", o.text_color)):
            if val is not None:
                defn[key] = _hex(val)

        # --- Fields -------------------------------------------------------
        for key, val in (("show_footer", o.show_footer),
                         ("show_number", o.show_number),
                         ("show_date", o.show_date)):
            if val is not None:
                defn[key] = val
        if o.footer_text is not None:
            pres.set_config("footer-text", o.footer_text)

        master.definition = defn
        if o.apply_now:
            template.apply_to_all(pres, defn, restyle=True)


if __name__ == "__main__":
    EditMaster().run()
