"""Generate a whole deck from a Markdown / text outline.

Mapping:
* ``# Title``      -> a Title slide (title, optional subtitle from the next line).
* ``## Heading``   -> a Title-and-Content slide; bullets/paragraphs become the body.
* ``- item``       -> a body bullet (indentation preserved).
* fenced code      -> a content region on the slide (```mermaid renders a diagram,
                      otherwise a highlighted code block).
* ``---``          -> an explicit slide break.

Reuses :func:`pages.add_slide`, :func:`placeholders.set_placeholder_text` and
:func:`webcontent.add_content_region` / ``render_into`` so generated slides are
identical to hand-authored ones.
"""

import re

from . import constants as C
from . import pages, webcontent
from . import placeholders as P


def parse_outline(text, default_layout=C.LayoutKey.TITLE_CONTENT):
    """Parse outline text into a list of slide spec dicts."""
    lines = (text or "").replace("\r\n", "\n").split("\n")
    specs = []
    cur = {"ref": None}

    def ensure(layout=None, title=""):
        spec = {"layout": layout or default_layout, "title": title,
                "subtitle": "", "body": [], "blocks": []}
        specs.append(spec)
        cur["ref"] = spec
        return spec

    in_code = False
    fence_lang = None
    code_buf = []

    for raw in lines:
        s = raw.strip()
        if in_code:
            if re.match(r"^```+\s*$", s):
                in_code = False
                kind = (C.ContentKind.MERMAID
                        if (fence_lang or "").lower() == "mermaid"
                        else C.ContentKind.CODE)
                if cur["ref"] is None:
                    ensure()
                cur["ref"]["blocks"].append({
                    "kind": kind,
                    "lang": None if kind == C.ContentKind.MERMAID else (fence_lang or ""),
                    "src": "\n".join(code_buf)})
                code_buf = []
                fence_lang = None
            else:
                code_buf.append(raw)
            continue

        m = re.match(r"^```+\s*(\w+)?\s*$", s)
        if m:
            in_code = True
            fence_lang = m.group(1)
            code_buf = []
            continue
        if re.match(r"^(-{3,}|\*{3,})$", s):
            cur["ref"] = None  # explicit slide break
            continue
        h = re.match(r"^(#{1,6})\s+(.*)$", s)
        if h:
            level = len(h.group(1))
            layout = C.LayoutKey.TITLE if level == 1 else C.LayoutKey.TITLE_CONTENT
            ensure(layout, h.group(2).strip())
            continue
        bl = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", raw)
        if bl:
            if cur["ref"] is None:
                ensure()
            indent = "  " * (len(bl.group(1)) // 2)
            cur["ref"]["body"].append(indent + bl.group(3).strip())
            continue
        if not s:
            continue
        # Plain paragraph line.
        if cur["ref"] is None:
            ensure()
        spec = cur["ref"]
        if spec["layout"] == C.LayoutKey.TITLE and not spec["subtitle"] and not spec["body"]:
            spec["subtitle"] = s
        else:
            spec["body"].append(s)

    if in_code and code_buf:
        if cur["ref"] is None:
            ensure()
        cur["ref"]["blocks"].append(
            {"kind": C.ContentKind.CODE, "lang": fence_lang or "",
             "src": "\n".join(code_buf)})
    return specs


def _add_blocks(slide, blocks, has_body):
    if not blocks:
        return
    _, _, w, h = slide.content_bbox
    m = 0.06
    left = m * w
    width = (1 - 2 * m) * w
    top = (0.55 if has_body else 0.24) * h
    bottom = 0.92 * h
    each = (bottom - top) / len(blocks)
    for i, blk in enumerate(blocks):
        rect = (left, top + i * each + 6, width, each - 12)
        group = webcontent.add_content_region(
            slide, rect, blk["kind"], blk["src"], lang=blk.get("lang"))
        bounds = None
        for sub in group:
            if sub.get(C.cn("ph-bounds")) == "true":
                bounds = sub
                break
        webcontent.render_into(group, bounds)


def build_deck(pres, specs, apply_master=True):
    """Create slides from parsed specs. Returns the created Slide objects."""
    created = []
    for spec in specs:
        slide = pages.add_slide(pres, spec["layout"], apply_master=apply_master)
        if spec.get("title"):
            ph = slide.placeholder("title")
            if ph is not None:
                P.set_placeholder_text(ph, [spec["title"]])
        if spec.get("subtitle"):
            ph = slide.placeholder("subtitle")
            if ph is not None:
                P.set_placeholder_text(ph, [spec["subtitle"]])
        if spec.get("body"):
            ph = slide.placeholder("body")
            if ph is not None:
                P.set_placeholder_text(ph, spec["body"], bullets=True)
        _add_blocks(slide, spec.get("blocks", []), has_body=bool(spec.get("body")))
        created.append(slide)
    return created


def generate(pres, text, default_layout=C.LayoutKey.TITLE_CONTENT,
             apply_master=True, replace=False):
    """Parse ``text`` and build the deck. Returns (created, removed) counts."""
    from . import fields

    specs = parse_outline(text, default_layout=default_layout)
    if not specs:
        return 0, 0
    old_ids = {s.slide_id for s in pres.slides()}
    created = build_deck(pres, specs, apply_master=apply_master)
    removed = 0
    if replace:
        for slide in list(pres.slides()):
            if slide.slide_id in old_ids and pres.slide_count() > 1:
                pages.delete_slide(pres, slide)
                removed += 1
    fields.update_all(pres)
    return len(created), removed
