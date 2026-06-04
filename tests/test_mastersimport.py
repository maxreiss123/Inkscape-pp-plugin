import os
import tempfile
import zipfile

import pytest
from pplib import mastersimport

A = mastersimport._A
P = mastersimport._P

PPTX_PRES = (
    '<p:presentation xmlns:p="%s">'
    '<p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>'
    "</p:presentation>" % P
)

PPTX_THEME = (
    '<a:theme xmlns:a="%s"><a:themeElements>'
    "<a:clrScheme>"
    '<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>'
    '<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
    '<a:accent1><a:srgbClr val="4472C4"/></a:accent1>'
    "</a:clrScheme>"
    "<a:fontScheme>"
    '<a:majorFont><a:latin typeface="Calibri Light"/></a:majorFont>'
    '<a:minorFont><a:latin typeface="Calibri"/></a:minorFont>'
    "</a:fontScheme>"
    "</a:themeElements></a:theme>" % A
)


def _make_pptx():
    fd, path = tempfile.mkstemp(suffix=".pptx")
    os.close(fd)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("ppt/presentation.xml", PPTX_PRES)
        zf.writestr("ppt/theme/theme1.xml", PPTX_THEME)
    return path


ODP_STYLES = (
    '<office:document-styles '
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:style="%s" xmlns:draw="%s" xmlns:fo="%s">'
    "<office:styles>"
    '<style:default-style style:family="paragraph">'
    '<style:text-properties style:font-name="Liberation Sans"/>'
    "</style:default-style>"
    '<style:style style:family="drawing-page" style:name="Mdp1">'
    '<style:drawing-page-properties draw:fill="solid" draw:fill-color="#102030"/>'
    "</style:style>"
    "</office:styles>"
    "<office:automatic-styles>"
    '<style:page-layout style:name="PL1">'
    '<style:page-layout-properties fo:page-width="25.4cm" fo:page-height="19.05cm"/>'
    "</style:page-layout>"
    "</office:automatic-styles>"
    "</office:document-styles>"
    % (mastersimport._STYLE, mastersimport._DRAW, mastersimport._FO)
)


def _make_odp():
    fd, path = tempfile.mkstemp(suffix=".odp")
    os.close(fd)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("styles.xml", ODP_STYLES)
    return path


def test_import_pptx_theme():
    path = _make_pptx()
    try:
        overrides, aspect, size = mastersimport.import_master(path)
    finally:
        os.remove(path)
    assert aspect == "16:9"
    assert overrides["bg_color"] == "#FFFFFF"
    assert overrides["accent_color"] == "#4472C4"
    assert overrides["font_family"] == "Calibri"


def test_import_odp_theme():
    path = _make_odp()
    try:
        overrides, aspect, size = mastersimport.import_master(path)
    finally:
        os.remove(path)
    assert aspect == "4:3"  # 25.4 x 19.05 cm
    assert overrides["bg_color"] == "#102030"
    assert overrides["font_family"] == "Liberation Sans"


def test_unsupported_type_raises():
    with pytest.raises(ValueError):
        mastersimport.import_master("/tmp/whatever.key")


def test_apply_import_updates_master(presentation):
    path = _make_pptx()
    try:
        summary = mastersimport.apply_import(presentation, path, resize=True)
    finally:
        os.remove(path)
    defn = presentation.master_by_id(None).definition
    assert defn["accent_color"] == "#4472C4"
    assert defn["font_family"] == "Calibri"
    assert "Imported" in summary or "theme" in summary
