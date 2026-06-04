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
# Mermaid rendering
# ---------------------------------------------------------------------------
def mermaid_available():
    return shutil.which("mmdc") is not None


def render_mermaid(src, width, height):
    """Render Mermaid to an SVG group.

    Order of preference: the ``mmdc`` CLI (full fidelity) if installed, then a
    built-in native renderer for flowchart/graph diagrams. Returns
    (group, content_w, content_h) or None when nothing can render it (the caller
    then falls back to a code block).
    """
    via = _render_mermaid_mmdc(src, width, height)
    if via is not None:
        return via
    if _mermaid_kind(src) in ("flowchart", "graph"):
        return render_flowchart(src, width, height)
    return None


def _mermaid_kind(src):
    for line in src.splitlines():
        s = line.strip()
        if not s or s.startswith("%%"):
            continue
        first = s.split()[0].lower()
        if first in ("flowchart", "graph"):
            return "flowchart" if first == "flowchart" else "graph"
        return first
    return ""


def _render_mermaid_mmdc(src, width, height):
    """Render Mermaid via the mmdc CLI, or None if unavailable/failed."""
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
# Native Mermaid flowchart renderer (subset: flowchart / graph)
# ---------------------------------------------------------------------------
# Shape wrappers, longest/compound first so e.g. ([..]) wins over (..).
_NODE_SHAPES = [
    ("stadium", r"\(\[(.*?)\]\)"),
    ("subroutine", r"\[\[(.*?)\]\]"),
    ("cylinder", r"\[\((.*?)\)\]"),
    ("circle", r"\(\((.*?)\)\)"),
    ("hexagon", r"\{\{(.*?)\}\}"),
    ("rhombus", r"\{(.*?)\}"),
    ("round", r"\((.*?)\)"),
    ("rect", r"\[(.*?)\]"),
    ("flag", r">(.*?)\]"),
]
_EDGE_RE = re.compile(r"\s*(<?-{2,3}[->ox]?|<?={2,3}>?|-\.-+>?|o-{2,3}|x-{2,3})"
                      r"\s*(?:\|([^|]*)\|\s*)?")
_FLOW_NODE_FILL = "#eef2ff"
_FLOW_NODE_STROKE = "#5b6b9a"
_FLOW_EDGE = "#4b5563"


def _clean_label(text):
    if text is None:
        return None
    text = text.strip().strip('"').strip("'")
    return text.replace("<br/>", "\n").replace("<br>", "\n").replace("<br />", "\n")


def _read_node(line, pos, nodes, order):
    m = re.match(r"\s*([A-Za-z0-9_]+)", line[pos:])
    if not m:
        return None, pos
    nid = m.group(1)
    pos += m.end()
    label, shape = None, "rect"
    for sh, pat in _NODE_SHAPES:
        mm = re.match(r"\s*" + pat, line[pos:], re.S)
        if mm:
            shape, label, pos = sh, _clean_label(mm.group(1)), pos + mm.end()
            break
    if nid not in nodes:
        nodes[nid] = {"label": label if label is not None else nid, "shape": shape}
        order.append(nid)
    elif label is not None:
        nodes[nid]["label"] = label
        nodes[nid]["shape"] = shape
    return nid, pos


def _read_group(line, pos, nodes, order):
    first, pos = _read_node(line, pos, nodes, order)
    if first is None:
        return None, pos
    ids = [first]
    while True:
        m = re.match(r"\s*&\s*", line[pos:])
        if not m:
            break
        pos += m.end()
        nid, pos = _read_node(line, pos, nodes, order)
        if nid is None:
            break
        ids.append(nid)
    return ids, pos


def _parse_line(line, nodes, edges, order):
    line = line.strip()
    if not line or line.startswith("%%"):
        return
    low = line.lower()
    if low.startswith(("subgraph", "end", "direction", "style", "classdef",
                       "class ", "click", "linkstyle")):
        return
    # Normalise mid-text link labels (A -- text --> B) to the |label| form.
    line = re.sub(r"--\s*([^|>\-][^>|]*?)\s*-->", r"-->|\1|", line)
    line = re.sub(r"==\s*([^|>=][^>|]*?)\s*==>", r"==>|\1|", line)

    grp, pos = _read_group(line, 0, nodes, order)
    if grp is None:
        return
    while pos < len(line):
        m = _EDGE_RE.match(line, pos)
        if not m:
            break
        op, label = m.group(1), m.group(2) or ""
        pos = m.end()
        grp2, pos = _read_group(line, pos, nodes, order)
        if grp2 is None:
            break
        style = "thick" if "=" in op else "dotted" if "." in op else "solid"
        for a in grp:
            for b in grp2:
                edges.append({"src": a, "dst": b, "label": _clean_label(label),
                              "style": style})
        grp = grp2


def parse_flowchart(src):
    nodes, edges, order = {}, [], []
    direction = "TD"
    for raw in src.splitlines():
        s = raw.strip()
        if not s:
            continue
        m = re.match(r"(?:flowchart|graph)\s+(TB|TD|BT|RL|LR)\b", s, re.I)
        if m:
            direction = m.group(1).upper()
            continue
        _parse_line(raw, nodes, edges, order)
    return direction, nodes, edges, order


def _rank_nodes(order, edges):
    rank = {n: 0 for n in order}
    adj = [(e["src"], e["dst"]) for e in edges if e["src"] != e["dst"]]
    for _ in range(len(order) + 1):
        changed = False
        for a, b in adj:
            if a in rank and b in rank and rank[b] < rank[a] + 1:
                rank[b] = rank[a] + 1
                changed = True
        if not changed:
            break
    return rank


def _node_size(node, font):
    lines = node["label"].split("\n")
    pad = font * 0.9
    w = max((len(ln) for ln in lines), default=1) * _char_w(font) + 2 * pad
    h = len(lines) * font * 1.25 + 2 * pad
    if node["shape"] in ("circle", "rhombus", "hexagon"):
        w = h = max(w, h)
    return max(90.0, w), max(48.0, h)


def _flow_shape(node, cx, cy, w, h):
    from inkex import Ellipse, PathElement, Rectangle

    shape = node["shape"]
    style = {"fill": _FLOW_NODE_FILL, "stroke": _FLOW_NODE_STROKE,
             "stroke-width": "2"}
    if shape == "circle":
        el = Ellipse()
        el.set("cx", str(cx))
        el.set("cy", str(cy))
        el.set("rx", str(w / 2))
        el.set("ry", str(h / 2))
    elif shape == "rhombus":
        el = PathElement()
        el.set("d", "M %g %g L %g %g L %g %g L %g %g Z" % (
            cx, cy - h / 2, cx + w / 2, cy, cx, cy + h / 2, cx - w / 2, cy))
    else:
        el = Rectangle()
        el.set("x", str(cx - w / 2))
        el.set("y", str(cy - h / 2))
        el.set("width", str(w))
        el.set("height", str(h))
        if shape in ("round", "stadium"):
            el.set("rx", str(h / 2 if shape == "stadium" else 12))
    el.style = style
    return el


def _centered_text(cx, cy, lines, font, color=_TEXT_FG):
    t = _text(cx, cy, font)
    t.style["text-anchor"] = "middle"
    t.style["fill"] = color
    total = (len(lines) - 1) * font * 1.2
    y0 = cy - total / 2 + font * 0.33
    t.set("y", str(round(y0, 2)))
    for i, ln in enumerate(lines):
        sp = _span(ln)
        sp.set("x", str(round(cx, 2)))
        sp.set("dy", "0" if i == 0 else str(round(font * 1.2, 2)))
        t.add(sp)
    return t


def _border_point(cx, cy, hw, hh, tx, ty):
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    sx = hw / abs(dx) if dx else 1e9
    sy = hh / abs(dy) if dy else 1e9
    s = min(sx, sy)
    return cx + dx * s, cy + dy * s


def render_flowchart(src, width, height, font=22):
    """Render a Mermaid flowchart/graph to a native SVG group, or None."""
    import math

    from inkex import Group, PathElement, Rectangle

    direction, nodes, edges, order = parse_flowchart(src)
    if not nodes:
        return None

    horizontal = direction in ("LR", "RL")
    rank = _rank_nodes(order, edges)
    sizes = {n: _node_size(nodes[n], font) for n in order}

    layers = {}
    for n in order:
        layers.setdefault(rank[n], []).append(n)

    gap_main, gap_cross = 80.0, 44.0
    pos = {}
    main_cursor = 0.0
    for r in sorted(layers):
        members = layers[r]
        if horizontal:
            layer_extent = max(sizes[n][0] for n in members)
            cross_total = sum(sizes[n][1] for n in members) + gap_cross * (len(members) - 1)
            c = -cross_total / 2
            for n in members:
                w, h = sizes[n]
                pos[n] = (main_cursor + layer_extent / 2, c + h / 2)
                c += h + gap_cross
            main_cursor += layer_extent + gap_main
        else:
            layer_extent = max(sizes[n][1] for n in members)
            cross_total = sum(sizes[n][0] for n in members) + gap_cross * (len(members) - 1)
            c = -cross_total / 2
            for n in members:
                w, h = sizes[n]
                pos[n] = (c + w / 2, main_cursor + layer_extent / 2)
                c += w + gap_cross
            main_cursor += layer_extent + gap_main

    # Flip for reversed directions.
    if direction == "RL":
        pos = {n: (-x, y) for n, (x, y) in pos.items()}
    elif direction == "BT":
        pos = {n: (x, -y) for n, (x, y) in pos.items()}

    # Normalise to a (0,0) origin with a margin.
    margin = 20.0
    xs = [pos[n][0] - sizes[n][0] / 2 for n in order] + \
         [pos[n][0] + sizes[n][0] / 2 for n in order]
    ys = [pos[n][1] - sizes[n][1] / 2 for n in order] + \
         [pos[n][1] + sizes[n][1] / 2 for n in order]
    minx, miny = min(xs) - margin, min(ys) - margin
    cw = max(xs) - minx + margin
    ch = max(ys) - miny + margin
    pos = {n: (x - minx, y - miny) for n, (x, y) in pos.items()}

    group = Group()

    # Edges first (under nodes).
    for e in edges:
        a, b = e["src"], e["dst"]
        if a not in pos or b not in pos:
            continue
        ax, ay = pos[a]
        bx, by = pos[b]
        aw, ah = sizes[a]
        bw, bh = sizes[b]
        sx, sy = _border_point(ax, ay, aw / 2, ah / 2, bx, by)
        ex, ey = _border_point(bx, by, bw / 2, bh / 2, ax, ay)
        line = PathElement()
        line.set("d", "M %g %g L %g %g" % (sx, sy, ex, ey))
        dash = "6,5" if e["style"] == "dotted" else "none"
        line.style = {"fill": "none", "stroke": _FLOW_EDGE,
                      "stroke-width": "3" if e["style"] == "thick" else "2",
                      "stroke-dasharray": dash}
        group.add(line)
        # Arrowhead.
        ang = math.atan2(ey - sy, ex - sx)
        size = 11.0
        p1 = (ex, ey)
        p2 = (ex - size * math.cos(ang - 0.45), ey - size * math.sin(ang - 0.45))
        p3 = (ex - size * math.cos(ang + 0.45), ey - size * math.sin(ang + 0.45))
        head = PathElement()
        head.set("d", "M %g %g L %g %g L %g %g Z" % (p1 + p2 + p3))
        head.style = {"fill": _FLOW_EDGE, "stroke": "none"}
        group.add(head)
        if e["label"]:
            mx, my = (sx + ex) / 2, (sy + ey) / 2
            lblw = len(e["label"]) * _char_w(font * 0.7) + 8
            bg = Rectangle(x=str(mx - lblw / 2), y=str(my - font * 0.55),
                           width=str(lblw), height=str(font * 0.95))
            bg.style = {"fill": "#ffffff", "stroke": "none"}
            group.add(bg)
            group.add(_centered_text(mx, my, [e["label"]], font * 0.7, color="#374151"))

    # Nodes.
    for n in order:
        cx, cy = pos[n]
        w, h = sizes[n]
        group.add(_flow_shape(nodes[n], cx, cy, w, h))
        group.add(_centered_text(cx, cy, nodes[n]["label"].split("\n"), font))

    return group, cw, ch


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
