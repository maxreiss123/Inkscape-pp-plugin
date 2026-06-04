"""Build a self-contained, browser-playable SVG from a presentation.

Each slide layer is tagged with ``data-pp-slide`` / ``data-pp-bbox``, the player
JS/CSS is inlined, and authoring chrome (master layers, namedview) is stripped.
The result opens directly in any modern browser.
"""

import copy
import json
import os

import lxml.etree as ET

from . import constants as C
from . import svgutil as S

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
SVG = "http://www.w3.org/2000/svg"


def embed_asset(name):
    with open(os.path.join(_ASSETS, name), encoding="utf-8") as fh:
        return fh.read()


def _render_web_regions(layer):
    """Replace each web-content region's placeholder text with a live iframe/HTML.

    The dashed bounds rectangle is kept as a frame; a <foreignObject> with the
    actual web content is appended so it renders in the browser.
    """
    from . import webcontent

    for group, bounds in list(webcontent.iter_regions(layer)):
        fo = webcontent.build_foreign_object(group, bounds)
        if fo is None:
            continue
        # Drop the canvas-only prompt label so it does not cover the content.
        for child in list(group):
            if child.get(C.cn("prompt")) == "true":
                group.remove(child)
        group.append(fo)


def build(pres, transition="fade", loop=False, start=0):
    """Return a deep-copied lxml tree ready to write as a standalone SVG."""
    from .model import Presentation

    root = copy.deepcopy(pres.svg)
    work = Presentation(root)
    slides = work.slides()

    first_bbox = None
    for slide in slides:
        layer = slide.layer
        bbox = slide.bbox
        if first_bbox is None:
            first_bbox = bbox
        layer.set("data-pp-slide", str(slide.index))
        layer.set("data-pp-bbox", "%s %s %s %s" % bbox)
        # Make sure the authoring "hidden layer" display state does not hide it.
        if "display" in layer.style:
            layer.style["display"] = "inline"
        _render_web_regions(layer)

    # Remove master layers and namedview (authoring-only).
    for el in list(root):
        if S.get_pp(el, C.A_ROLE) == C.Role.MASTER:
            root.remove(el)
    nv = root.find("{%s}namedview" % C.SODIPODI_NS)
    if nv is not None:
        root.remove(nv)

    # Fill the viewport.
    root.set("width", "100%")
    root.set("height", "100%")
    root.set("preserveAspectRatio", "xMidYMid meet")
    if first_bbox is not None:
        root.set("viewBox", "%s %s %s %s" % first_bbox)

    # Inject CSS + config + player JS.
    style = ET.SubElement(root, "{%s}style" % SVG)
    style.set("type", "text/css")
    style.text = ET.CDATA("\n" + embed_asset("player.css") + "\n")

    config = {"count": len(slides), "transition": transition,
              "loop": bool(loop), "start": int(start)}
    cfg_script = ET.SubElement(root, "{%s}script" % SVG)
    cfg_script.set("type", "application/ecmascript")
    cfg_script.text = ET.CDATA("\nwindow.PP_CONFIG = %s;\n" % json.dumps(config))

    _inject_content_renderers(root, work)

    player = ET.SubElement(root, "{%s}script" % SVG)
    player.set("type", "application/ecmascript")
    player.text = ET.CDATA("\n" + embed_asset("player.js") + "\n")

    return root.getroottree()


def _external_script(root, url):
    el = ET.SubElement(root, "{%s}script" % SVG)
    el.set("type", "application/ecmascript")
    # Set both href forms for broad browser support of external SVG scripts.
    el.set("href", url)
    el.set("{http://www.w3.org/1999/xlink}href", url)
    return el


def _inject_content_renderers(root, work):
    """Add CDN renderer libraries + the content init script when needed."""
    from . import webcontent

    kinds = webcontent.kinds_in(work)
    if C.ContentKind.MERMAID in kinds:
        _external_script(root, C.CDN["mermaid"])
    if C.ContentKind.MARKDOWN in kinds:
        _external_script(root, C.CDN["marked"])
    if C.ContentKind.CODE in kinds:
        _external_script(root, C.CDN["hljs"])
        # An xml-stylesheet PI applies the theme document-wide, including inside
        # foreignObject XHTML -- more reliable than @import in an SVG <style>.
        pi = ET.ProcessingInstruction(
            "xml-stylesheet", 'type="text/css" href="%s"' % C.CDN["hljs_css"])
        root.addprevious(pi)
    if kinds & {C.ContentKind.MERMAID, C.ContentKind.MARKDOWN, C.ContentKind.CODE}:
        init = ET.SubElement(root, "{%s}script" % SVG)
        init.set("type", "application/ecmascript")
        init.text = ET.CDATA("\n" + embed_asset("content.js") + "\n")


def write(pres, path, **kw):
    tree = build(pres, **kw)
    tree.write(path, xml_declaration=True, encoding="UTF-8")
    return path
