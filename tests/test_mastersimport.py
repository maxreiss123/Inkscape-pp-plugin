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


# A realistic slide master: a coloured background (which lt1 does not reflect)
# plus explicit title/body text styles -- the bits a typical corporate template
# actually carries.
PPTX_MASTER = (
    '<p:sldMaster xmlns:p="%s" xmlns:a="%s">'
    "<p:cSld>"
    '<p:bg><p:bgPr><a:solidFill><a:srgbClr val="1F2933"/></a:solidFill></p:bgPr></p:bg>'
    "<p:spTree/></p:cSld>"
    "<p:txStyles>"
    '<p:titleStyle><a:lvl1pPr><a:defRPr sz="4400">'
    '<a:solidFill><a:srgbClr val="C0392B"/></a:solidFill>'
    "</a:defRPr></a:lvl1pPr></p:titleStyle>"
    '<p:bodyStyle><a:lvl1pPr><a:defRPr sz="2000"/></a:lvl1pPr></p:bodyStyle>'
    "</p:txStyles></p:sldMaster>" % (P, A)
)

PPTX_MASTER_SCHEME_BG = (
    '<p:sldMaster xmlns:p="%s" xmlns:a="%s">'
    "<p:cSld>"
    '<p:bg><p:bgRef idx="1001"><a:schemeClr val="accent1"/></p:bgRef></p:bg>'
    "<p:spTree/></p:cSld></p:sldMaster>" % (P, A)
)


def _make_pptx(suffix=".pptx", master=None):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("ppt/presentation.xml", PPTX_PRES)
        zf.writestr("ppt/theme/theme1.xml", PPTX_THEME)
        if master:
            zf.writestr("ppt/slideMasters/slideMaster1.xml", master)
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


def test_import_potx_with_slide_master():
    """The .potx template format works, and the slide master drives the look."""
    path = _make_pptx(suffix=".potx", master=PPTX_MASTER)
    try:
        overrides, aspect, size = mastersimport.import_master(path)
    finally:
        os.remove(path)
    # Master background beats the theme's lt1 white.
    assert overrides["bg_color"] == "#1F2933"
    # 44pt title -> 88px in our units; explicit title colour; 20pt body -> 40px.
    assert overrides["title_font_size"] == 88
    assert overrides["title_color"] == "#C0392B"
    assert overrides["body_font_size"] == 40
    assert aspect == "16:9"


def test_master_bgref_scheme_colour_resolves():
    path = _make_pptx(master=PPTX_MASTER_SCHEME_BG)
    try:
        overrides, _, _ = mastersimport.import_master(path)
    finally:
        os.remove(path)
    assert overrides["bg_color"] == "#4472C4"  # schemeClr accent1 resolved


def test_unsupported_message_lists_formats():
    with pytest.raises(ValueError) as err:
        mastersimport.import_master("/tmp/whatever.key")
    assert ".potx" in str(err.value)


def test_apply_import_summary_is_detailed(presentation):
    path = _make_pptx(master=PPTX_MASTER)
    try:
        summary = mastersimport.apply_import(presentation, path)
    finally:
        os.remove(path)
    assert "background: #1F2933" in summary
    assert "Applied to 3 slides." in summary


def test_apply_import_restyles_existing_text(presentation):
    from pplib import placeholders as Ph
    from pplib import svgutil as S

    slide = presentation.slides()[0]  # title layout
    Ph.set_placeholder_text(slide.placeholder("title"), ["Hello"])

    path = _make_pptx(master=PPTX_MASTER)
    try:
        mastersimport.apply_import(presentation, path)
    finally:
        os.remove(path)

    text = Ph.placeholder_text_el(presentation.slides()[0].placeholder("title"))
    assert text.style["font-family"] == "Calibri"
    assert text.style["font-size"] == "88px"
    assert text.style["fill"] == "#C0392B"
    assert "Hello" in S.text_content(text)  # content untouched
