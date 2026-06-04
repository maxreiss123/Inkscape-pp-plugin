#!/usr/bin/env python3
"""Add a rich-content region (Mermaid / code / Markdown / web / HTML).

Choose where it goes by selecting a rectangle for the bounds; choose what goes in
it via the source text, a source file, or a selected text object. The region
renders live in the interactive SVG export / browser preview. On the canvas it is
a labelled box showing a short preview of the source.
"""

import inkex
from pplib import constants as C
from pplib import svgutil as S
from pplib import webcontent
from pplib.model import Presentation


def _unescape(text):
    """Decode the escapes Inkscape's multiline/string fields pass (\\n, \\t).

    A multiline field encodes line breaks as the two characters backslash-n;
    decode those (and tabs / carriage returns) back into real whitespace.
    """
    return (text.replace("\\r\\n", "\n")
                .replace("\\n", "\n")
                .replace("\\t", "\t")
                .replace("\\r", "\n"))


class AddContent(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--kind", default=C.ContentKind.MERMAID)
        pars.add_argument("--source", default="")
        pars.add_argument("--source_file", default="")
        pars.add_argument("--lang", default="")
        pars.add_argument("--label", default="")
        pars.add_argument("--replace_selection", type=inkex.Boolean, default=True)

    @staticmethod
    def _abs_bbox(el):
        parent = el.getparent()
        tf = parent.composed_transform() if parent is not None else None
        return el.bounding_box(tf)

    def _resolve_source(self, text_elements):
        if self.options.source_file:
            try:
                with open(self.options.source_file, encoding="utf-8") as fh:
                    return fh.read()
            except OSError as exc:
                inkex.errormsg("Could not read source file: %s" % exc)
                return None
        if self.options.source:
            return _unescape(self.options.source)
        if text_elements:
            return "\n".join(S.text_content(t) for t in text_elements)
        return ""

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

        selection = list(self.svg.selection.values())
        text_elements = [e for e in selection if isinstance(e, TextElement)]
        bounds_elements = [e for e in selection if not isinstance(e, TextElement)]

        src = self._resolve_source(text_elements)
        if src is None:
            return
        if not src and self.options.kind != C.ContentKind.WEB:
            inkex.errormsg("Provide source text, a source file, or select a text "
                           "object to use as the content.")
            return

        px, py, pw, ph = slide.bbox
        bbox_source = bounds_elements or selection
        if bbox_source:
            bb = self._abs_bbox(bbox_source[0])
            for el in bbox_source[1:]:
                bb += self._abs_bbox(el)
            local_rect = (bb.left - px, bb.top - py, bb.width, bb.height)
        else:
            local_rect = (0.15 * pw, 0.22 * ph, 0.70 * pw, 0.62 * ph)

        if self.options.replace_selection:
            for el in selection:
                el.getparent().remove(el)

        group = webcontent.add_content_region(
            slide, local_rect, self.options.kind, src,
            lang=self.options.lang or None,
            label=self.options.label or None,
        )
        # Render Markdown / code / Mermaid to native SVG now so it shows on the
        # slide (and in PDF). Web/HTML stay as a labelled box (browser-only).
        bounds = None
        for sub in group:
            if sub.get(C.cn("ph-bounds")) == "true":
                bounds = sub
                break
        webcontent.render_into(group, bounds)


if __name__ == "__main__":
    AddContent().run()
