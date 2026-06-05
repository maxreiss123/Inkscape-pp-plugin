"""Optional font embedding for the HTML/SVG export.

Scans the export tree for the font families it uses, resolves each to a font file
(via ``fc-match`` when available), subsets it to the glyphs actually used and
emits base64 ``@font-face`` rules so the deck renders with the right fonts on any
machine. Requires fontTools; when it (or a font file) is unavailable, returns an
empty stylesheet and the deck falls back to the document's font stack.
"""

import base64
import shutil
import subprocess

SVG = "http://www.w3.org/2000/svg"
_GENERIC = {"sans-serif", "serif", "monospace", "system-ui", "cursive",
            "fantasy", "ui-sans-serif", "ui-serif", "ui-monospace", "inherit",
            "-apple-system"}


def _has_fonttools():
    try:
        import fontTools  # noqa: F401
        return True
    except Exception:
        return False


def used_families(root):
    """Return the set of concrete (non-generic) font-family names in the tree."""
    fams = set()
    for el in root.iter():
        style = el.get("style")
        fam = None
        if style and "font-family" in style:
            for decl in style.split(";"):
                if decl.strip().startswith("font-family"):
                    fam = decl.split(":", 1)[1]
                    break
        fam = fam or el.get("font-family")
        if not fam:
            continue
        first = fam.split(",")[0].strip().strip("'\"")
        if first and first.lower() not in _GENERIC:
            fams.add(first)
    return fams


def used_text(root):
    chars = set(" ")
    for el in root.iter():
        if el.text:
            chars.update(el.text)
        if el.tail:
            chars.update(el.tail)
    return chars


def _resolve_file(family):
    if not shutil.which("fc-match"):
        return None
    try:
        out = subprocess.run(["fc-match", "-f", "%{file}", family],
                             capture_output=True, text=True, timeout=10)
        path = out.stdout.strip()
        return path or None
    except Exception:
        return None


def _subset_b64(path, chars):
    from fontTools import subset

    text = "".join(sorted(chars))
    opts = subset.Options()
    opts.flavor = "woff"  # zlib-based; no brotli needed
    opts.desubroutinize = True
    font = subset.load_font(path, opts)
    subsetter = subset.Subsetter(options=opts)
    subsetter.populate(text=text)
    subsetter.subset(font)
    import io
    buf = io.BytesIO()
    subset.save_font(font, buf, opts)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def embed_css(root):
    """Return an @font-face stylesheet for the fonts used, or '' if unavailable."""
    if not _has_fonttools():
        return ""
    fams = used_families(root)
    if not fams:
        return ""
    chars = used_text(root)
    rules = []
    for fam in sorted(fams):
        path = _resolve_file(fam)
        if not path:
            continue
        try:
            b64 = _subset_b64(path, chars)
        except Exception:
            continue
        rules.append(
            "@font-face{font-family:'%s';src:url(data:font/woff;base64,%s) "
            "format('woff');font-weight:normal;font-style:normal;}" % (fam, b64))
    return "\n".join(rules)
