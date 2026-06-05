#!/usr/bin/env python3
"""Set or clear the current slide's speaker notes.

Notes appear in the presenter view of the browser preview / interactive export
(press P), never on the slide itself. Paste them into the multi-line field, or
select a text object and use its content as the notes.
"""

import inkex
from pplib import notes as notes_mod
from pplib import svgutil as S
from pplib.model import Presentation


def _unescape(text):
    return (text.replace("\\r\\n", "\n").replace("\\n", "\n")
                .replace("\\t", "\t").replace("\\r", "\n"))


class SlideNotes(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--text", default="")
        pars.add_argument("--from_selection", type=inkex.Boolean, default=False)
        pars.add_argument("--action", default="set")  # set | clear

    def effect(self):
        from inkex import TextElement

        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        slide = pres.active_slide()
        if slide is None:
            inkex.errormsg("No active slide.")
            return

        if self.options.action == "clear":
            notes_mod.clear_notes(slide)
            return

        text = ""
        if self.options.from_selection:
            sel = [e for e in self.svg.selection.values()
                   if isinstance(e, TextElement)]
            text = "\n".join(S.text_content(t) for t in sel)
        if not text:
            text = _unescape(self.options.text)
        if not text:
            inkex.errormsg("Enter notes text or select a text object.")
            return
        notes_mod.set_notes(slide, text)


if __name__ == "__main__":
    SlideNotes().run()
