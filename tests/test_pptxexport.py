import os
import tempfile
import zipfile

import lxml.etree as ET
import pytest
from pplib import notes as notes_mod
from pplib import pptxexport

cairosvg = pytest.importorskip("cairosvg")


def _export(pres, **kw):
    fd, path = tempfile.mkstemp(suffix=".pptx")
    os.close(fd)
    pptxexport.export(pres, path, **kw)
    return path


def test_pptx_package_structure(presentation):
    notes_mod.set_notes(presentation.slides()[1], "speaker note here")
    path = _export(presentation, scale=1.0)
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            assert "[Content_Types].xml" in names
            assert "ppt/presentation.xml" in names
            assert "ppt/slideMasters/slideMaster1.xml" in names
            for i in (1, 2, 3):
                assert "ppt/slides/slide%d.xml" % i in names
                assert "ppt/media/image%d.png" % i in names
            # Notes only for slide 2.
            assert "ppt/notesSlides/notesSlide2.xml" in names
            # Every XML part is well-formed.
            for n in names:
                if n.endswith(".xml") or n.endswith(".rels"):
                    ET.fromstring(zf.read(n))
            # Notes text present.
            assert b"speaker note here" in zf.read("ppt/notesSlides/notesSlide2.xml")
            # Slide count in presentation.xml.
            pres_xml = zf.read("ppt/presentation.xml").decode()
            assert pres_xml.count("<p:sldId ") == 3
    finally:
        os.remove(path)


def test_pptx_images_are_png(presentation):
    path = _export(presentation, scale=1.0)
    try:
        with zipfile.ZipFile(path) as zf:
            assert zf.read("ppt/media/image1.png")[:8] == b"\x89PNG\r\n\x1a\n"
    finally:
        os.remove(path)
