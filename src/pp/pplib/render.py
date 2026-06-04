"""Render content-region source into native SVG (so it shows on the slide).

Inkscape's renderer and PDF export do not support HTML ``<foreignObject>``, so
Markdown / code / Mermaid must be rendered to real SVG to appear on a slide.
This module produces SVG groups for:

* code     -- syntax highlighted via Pygments when available, else plain mono.
* markdown -- a practical subset (headings, lists, block-quotes, rules, fenced
              code, tables, inline bold/italic/code/links).
* mermaid  -- via the ``mmdc`` CLI when installed; otherwise a code-block fallback.

Each renderer lays content out top-left in local coordinates; the orchestrator
scales the result to fit the region box.
"""

import os
import re
import shutil
import subprocess
import tempfile

from . import constants as C
from . import svgutil as S

XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

# Approximate glyph width as a fraction of font size (for wrapping/fit).
_CHAR_W = 0.55
_MONO_CHAR_W = 0.6
_LINE_H = 1.35

_CODE_BG = "#f6f8fa"
_CODE_FG = "#24292e"
_TEXT_FG = "#24292e"
_ACCENT = "#2a6fb0"


# ---------------------------------------------------------------------------
# Low-level SVG text helpers
# ---------------------------------------------------------------------------
def _text(x, y, font, mono=False):
    from inkex import TextElement

    t = TextElement()
    t.set("x", str(round(x, 2)))
    t.set("y", str(round(y, 2)))
    t.set(XML_SPACE, "preserve")
    t.style = {
        "font-size": "%gpx" % font,
        "font-family": "monospace" if mono else "sans-serif",
        "fill": _TEXT_FG,
    }
    return t


def _span(text, color=None, bold=False, italic=False, mono=False):
    from inkex import Tspan

    sp = Tspan()
    sp.text = text
    st = {}
    if color:
        st["fill"] = color
    if bold:
        st["font-weight"] = "bold"
    if italic:
        st["font-style"] = "italic"
    if mono:
        st["font-family"] = "monospace"
    if st:
        sp.style = st
    return sp


def _char_w(font, mono=False):
    return font * (_MONO_CHAR_W if mono else _CHAR_W)


def _wrap(text, width_px, font, mono=False):
    """Greedy word-wrap; returns a list of line strings."""
    max_chars = max(4, int(width_px / _char_w(font, mono)))
    words = text.split()
    if not words:
        return [""]
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = w if not cur else cur + " " + w
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------------------
# Inline Markdown parsing (**bold**, *italic*, `code`, [text](url))
# ---------------------------------------------------------------------------
_INLINE_RE = re.compile(
    r"(\*\*.+?\*\*|__.+?__|\*.+?\*|_.+?_|`.+?`|\[.+?\]\(.+?\))")


def _parse_inline(text):
    """Return a list of (text, bold, italic, code) runs."""
    runs = []
    for part in _INLINE_RE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            runs.append((part[2:-2], True, False, False))
        elif part.startswith("__") and part.endswith("__"):
            runs.append((part[2:-2], True, False, False))
        elif part.startswith("`") and part.endswith("`"):
            runs.append((part[1:-1], False, False, True))
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            runs.append((part[1:-1], False, True, False))
        elif part.startswith("_") and part.endswith("_") and len(part) > 2:
            runs.append((part[1:-1], False, True, False))
        elif part.startswith("[") and "](" in part:
            label = part[1:part.index("]")]
            runs.append((label, False, False, False))
        else:
            runs.append((part, False, False, False))
    return runs or [(text, False, False, False)]


def _emit_wrapped_runs(group, runs, x, y, width, font, line_h):
    """Lay out inline runs with word wrapping. Returns the new y cursor."""
    max_chars = max(4, int(width / _char_w(font)))
    line_words = []  # list of (word, bold, italic, code)
    cur_len = 0

    def flush():
        nonlocal y, line_words, cur_len
        if not line_words:
            return
        t = _text(x, y, font)
        for i, (w, b, it, cd) in enumerate(line_words):
            sp = _span((" " if i else "") + w,
                       color="#d6336c" if cd else None,
                       bold=b, italic=it, mono=cd)
            t.add(sp)
        group.add(t)
        y += font * line_h
        line_words = []
        cur_len = 0

    for text, b, it, cd in runs:
        for word in text.split():
            wlen = len(word) + (1 if line_words else 0)
            if line_words and cur_len + wlen > max_chars:
                flush()
                wlen = len(word)
            line_words.append((word, b, it, cd))
            cur_len += wlen
    flush()
    return y


# ---------------------------------------------------------------------------
# Code rendering
# ---------------------------------------------------------------------------
def _pygments_lines(src, lang):
    """Yield lines, each a list of (text, color) spans, using Pygments."""
    try:
        from pygments import lex
        from pygments.lexers import get_lexer_by_name, guess_lexer
        from pygments.styles import get_style_by_name
        from pygments.util import ClassNotFound
    except Exception:
        return None

    try:
        lexer = get_lexer_by_name(lang) if lang else guess_lexer(src)
    except ClassNotFound:
        try:
            lexer = guess_lexer(src)
        except Exception:
            return None

    style = get_style_by_name("default")

    def color_for(ttype):
        try:
            s = style.style_for_token(ttype)
        except Exception:
            return None
        return ("#" + s["color"]) if s.get("color") else None

    lines = [[]]
    for ttype, value in lex(src, lexer):
        color = color_for(ttype)
        parts = value.split("\n")
        for i, part in enumerate(parts):
            if i > 0:
                lines.append([])
            if part:
                lines[-1].append((part, color))
    return lines


def render_code(src, lang, width, height, font=20, with_bg=True):
    """Return (group, content_w, content_h) for a code block."""
    from inkex import Group, Rectangle

    src = src.rstrip("\n")
    rows = src.split("\n")
    pyg = _pygments_lines(src, lang)

    group = Group()
    line_h = font * 1.3
    pad = font * 0.6
    longest = max((len(r) for r in rows), default=1)
    content_w = longest * _char_w(font, mono=True) + 2 * pad
    content_h = len(rows) * line_h + 2 * pad

    if with_bg:
        bg = Rectangle(x="0", y="0", width=str(round(content_w, 2)),
                       height=str(round(content_h, 2)))
        bg.style = {"fill": _CODE_BG, "stroke": "#e1e4e8", "stroke-width": "1",
                    "rx": "6"}
        group.add(bg)

    y = pad + font
    if pyg is not None:
        for spans in pyg:
            t = _text(pad, y, font, mono=True)
            if not spans:
                t.add(_span(" "))
            for text, color in spans:
                t.add(_span(text, color=color or _CODE_FG, mono=True))
            group.add(t)
            y += line_h
    else:
        for row in rows:
            t = _text(pad, y, font, mono=True)
            t.add(_span(row or " ", color=_CODE_FG, mono=True))
            group.add(t)
            y += line_h
    return group, content_w, content_h


# ---------------------------------------------------------------------------
# Mermaid rendering (via mmdc CLI if available)
# ---------------------------------------------------------------------------
def mermaid_available():
    return shutil.which("mmdc") is not None


def render_mermaid(src, width, height):
    """Render Mermaid to an SVG group via mmdc, or None if unavailable/failed."""
    import lxml.etree as ET
    from inkex import Group

    if not mermaid_available():
        return None
    tmp = tempfile.mkdtemp(prefix="pp-mmd-")
    in_path = os.path.join(tmp, "d.mmd")
    out_path = os.path.join(tmp, "d.svg")
    try:
        with open(in_path, "w", encoding="utf-8") as fh:
            fh.write(src)
        subprocess.run(["mmdc", "-i", in_path, "-o", out_path, "-b", "transparent"],
                       check=True, capture_output=True, timeout=60)
        tree = ET.parse(out_path)
        svg = tree.getroot()
        vb = svg.get("viewBox")
        group = Group()
        for child in svg:
            group.append(child)
        cw = ch = None
        if vb:
            parts = vb.split()
            if len(parts) == 4:
                cw, ch = float(parts[2]), float(parts[3])
        if cw is None:
            cw, ch = width, height
        return group, cw, ch
    except Exception:
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Markdown rendering (subset)
# ---------------------------------------------------------------------------
_H_SIZES = {1: 40, 2: 32, 3: 26, 4: 22, 5: 20, 6: 18}


def render_markdown(src, width, height, base=24):
    """Return (group, content_w, content_h) for rendered Markdown."""
    from inkex import Group, Rectangle

    group = Group()
    lines = src.replace("\r\n", "\n").split("\n")
    y = base
    x = 0.0
    line_h = _LINE_H

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Fenced code block
        m = re.match(r"^```+\s*(\w+)?\s*$", stripped)
        if m:
            lang = m.group(1) or ""
            block = []
            i += 1
            while i < n and not re.match(r"^```+\s*$", lines[i].strip()):
                block.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            code = "\n".join(block)
            sub = None
            if lang.lower() == "mermaid":
                sub = render_mermaid(code, width, base * 8)
            if sub is not None:
                cg, cw, ch = sub
            else:
                cg, cw, ch = render_code(code, lang, width, base * 8,
                                         font=base * 0.8)
            scale = min(1.0, width / cw) if cw else 1.0
            cg.transform = "translate(0,%g) scale(%g)" % (y, scale)
            group.add(cg)
            y += ch * scale + base * 0.5
            continue

        # Horizontal rule
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            rule = Rectangle(x="0", y=str(round(y - base * 0.3, 2)),
                             width=str(round(width, 2)), height="2")
            rule.style = {"fill": "#d0d7de"}
            group.add(rule)
            y += base * 0.8
            i += 1
            continue

        # Heading
        h = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if h:
            level = len(h.group(1))
            size = _H_SIZES.get(level, base)
            y += size * 0.3
            t = _text(x, y, size)
            for text, b, it, cd in _parse_inline(h.group(2)):
                t.add(_span(text, color=_ACCENT if level <= 2 else None,
                            bold=True, italic=it, mono=cd))
            group.add(t)
            y += size * line_h
            i += 1
            continue

        # Block quote
        if stripped.startswith(">"):
            quote = stripped.lstrip(">").strip()
            bar = Rectangle(x="0", y=str(round(y - base, 2)),
                            width="3", height=str(round(base * line_h, 2)))
            bar.style = {"fill": "#d0d7de"}
            group.add(bar)
            y = _emit_quote(group, quote, base, y, width, line_h)
            i += 1
            continue

        # Table (consecutive lines containing '|', with a separator row)
        if "|" in line and i + 1 < n and re.match(r"^[\s|:-]+$", lines[i + 1].strip()) \
                and "-" in lines[i + 1]:
            rows = []
            while i < n and "|" in lines[i]:
                rows.append(lines[i])
                i += 1
            y = _render_table(group, rows, width, y, base)
            continue

        # List item
        li = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", line)
        if li:
            indent = len(li.group(1))
            marker = "• " if li.group(2) in ("-", "*", "+") else (li.group(2) + " ")
            bullet_x = x + (indent / 2) * base * 0.5
            runs = _parse_inline(li.group(3))
            runs = [(marker, False, False, False)] + runs
            y = _emit_wrapped_runs(group, runs, bullet_x, y, width - bullet_x,
                                   base, line_h)
            i += 1
            continue

        # Blank line
        if not stripped:
            y += base * 0.5
            i += 1
            continue

        # Paragraph
        runs = _parse_inline(stripped)
        y = _emit_wrapped_runs(group, runs, x, y, width, base, line_h)
        i += 1

    return group, width, y


def _emit_quote(group, text, base, y, width, line_h):
    for line in _wrap(text, width - base, base):
        t = _text(base * 0.6, y, base)
        t.add(_span(line, color="#57606a", italic=True))
        group.add(t)
        y += base * line_h
    return y


def _render_table(group, rows, width, y, base):
    cells = [[c.strip() for c in re.split(r"\s*\|\s*", r.strip().strip("|"))]
             for r in rows]
    if len(cells) >= 2:
        cells.pop(1)  # drop the separator row
    if not cells:
        return y
    ncol = max(len(r) for r in cells)
    col_w = width / ncol
    font = base * 0.85
    row_h = font * 1.8
    from inkex import Rectangle
    for ri, row in enumerate(cells):
        ry = y + ri * row_h
        if ri == 0:
            hdr = Rectangle(x="0", y=str(round(ry - font, 2)),
                            width=str(round(width, 2)), height=str(round(row_h, 2)))
            hdr.style = {"fill": "#f0f3f6"}
            group.add(hdr)
        for ci in range(ncol):
            txt = row[ci] if ci < len(row) else ""
            t = _text(ci * col_w + 6, ry + font * 0.4, font)
            for tx, b, it, cd in _parse_inline(txt):
                t.add(_span(tx, bold=(ri == 0) or b, italic=it, mono=cd))
            group.add(t)
    return y + len(cells) * row_h + base * 0.4


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def render_region(group, bounds):
    """Render a content region's source into a native SVG group.

    Returns a new <g> positioned/scaled to the bounds rectangle, or None for
    kinds that cannot be rendered statically (web/html).
    """
    from inkex import Group

    from . import webcontent

    kind = webcontent.region_kind(group)
    if kind in (C.ContentKind.WEB, C.ContentKind.HTML):
        return None
    src = webcontent.region_source(group)
    if not src.strip():
        return None

    x = float(bounds.get("x", 0))
    y = float(bounds.get("y", 0))
    w = float(bounds.get("width", 0))
    h = float(bounds.get("height", 0))
    pad = min(w, h) * 0.04

    inner_w = max(10.0, w - 2 * pad)
    if kind == C.ContentKind.CODE:
        lang = S.get_pp(group, C.A_CONTENT_LANG) or ""
        content, cw, ch = render_code(src, lang, inner_w, h)
    elif kind == C.ContentKind.MERMAID:
        sub = render_mermaid(src, inner_w, h - 2 * pad)
        content, cw, ch = sub if sub else render_code(src, "", inner_w, h)
    elif kind == C.ContentKind.MARKDOWN:
        content, cw, ch = render_markdown(src, inner_w, h - 2 * pad)
    else:
        return None

    scale = 1.0
    if cw and ch:
        scale = min(inner_w / cw, (h - 2 * pad) / ch, 1.0)
        if scale <= 0:
            scale = 1.0

    wrapper = Group()
    S.set_pp(wrapper, C.A_MANAGED, "render")
    wrapper.transform = "translate(%g,%g) scale(%g)" % (x + pad, y + pad, scale)
    wrapper.add(content)
    return wrapper
