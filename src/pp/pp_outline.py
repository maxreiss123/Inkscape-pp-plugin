#!/usr/bin/env python3
"""Generate a deck from a Markdown / text outline.

# Title becomes a title slide; ## Heading becomes a content slide; bullets become
the body; fenced code / ```mermaid blocks become rendered content regions.
"""

import inkex
from pplib import constants as C
from pplib import outline
from pplib.model import Presentation


def _unescape(text):
    return (text.replace("\\r\\n", "\n").replace("\\n", "\n")
                .replace("\\t", "\t").replace("\\r", "\n"))


class Outline(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--text", default="")
        pars.add_argument("--file", default="")
        pars.add_argument("--default_layout", default=C.LayoutKey.TITLE_CONTENT)
        pars.add_argument("--apply_master", type=inkex.Boolean, default=True)
        pars.add_argument("--replace", type=inkex.Boolean, default=False)

    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        text = ""
        if self.options.file:
            try:
                with open(self.options.file, encoding="utf-8") as fh:
                    text = fh.read()
            except OSError as exc:
                inkex.errormsg("Could not read outline file: %s" % exc)
                return
        if not text:
            text = _unescape(self.options.text)
        if not text.strip():
            inkex.errormsg("Paste an outline or choose an outline file.")
            return

        created, removed = outline.generate(
            pres, text,
            default_layout=self.options.default_layout,
            apply_master=self.options.apply_master,
            replace=self.options.replace)
        if created == 0:
            inkex.errormsg("No slides could be generated from the outline.")


if __name__ == "__main__":
    Outline().run()
