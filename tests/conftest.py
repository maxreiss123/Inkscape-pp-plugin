"""Test fixtures and a helper to drive extensions headlessly.

We import the plugin from ``src/pp`` and exercise the handlers by driving their
``effect()`` method directly (bypassing inkex's ``has_changed`` output
optimisation, which suppresses stdout for no-op runs).
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PP_DIR = os.path.join(ROOT, "src", "pp")
# Make both ``pplib`` (handlers) and ``pp.pplib`` (library) importable.
sys.path.insert(0, PP_DIR)
sys.path.insert(0, os.path.join(ROOT, "src"))

import inkex  # noqa: E402

BLANK_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" '
    'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
    'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd" '
    'width="100" height="100" viewBox="0 0 100 100">'
    '<sodipodi:namedview id="nv"/></svg>'
)


def run_effect(ext_class, args, svg_bytes):
    """Run an extension's effect() on ``svg_bytes`` and return its svg root."""
    import io
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".svg")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(svg_bytes)
        ext = ext_class()
        ext.parse_arguments(list(args) + [path])
        ext.document = inkex.load_svg(io.BytesIO(svg_bytes))
        ext.original_document = ext.document
        ext.svg = ext.document.getroot()
        ext.svg.selection.set()
        ext.effect()
        return ext.svg
    finally:
        os.remove(path)


def to_bytes(svg_root):
    import lxml.etree as ET
    return ET.tostring(svg_root.getroottree())


@pytest.fixture
def blank_svg():
    return BLANK_SVG.encode()


@pytest.fixture
def presentation():
    """A 3-slide presentation (title, title_content, two_content) as svg root."""
    from pplib import constants as C
    from pplib import document, pages
    from pplib.model import Presentation

    root = inkex.load_svg(BLANK_SVG.encode()).getroot()
    pres = Presentation(root)
    document.init_presentation(pres, aspect="16:9", footer_text="Talk",
                               date_mode=C.DateMode.NONE,
                               first_layout=C.LayoutKey.TITLE)
    pages.add_slide(pres, C.LayoutKey.TITLE_CONTENT)
    pages.add_slide(pres, C.LayoutKey.TWO_CONTENT)
    return pres
