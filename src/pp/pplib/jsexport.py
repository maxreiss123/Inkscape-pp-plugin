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


def _export_effects(layer):
    """Copy build-animation metadata to data-* attributes for the player."""
    for el in layer.iter():
        order = S.get_pp(el, C.A_EFFECT_ORDER)
        if order:
            el.set("data-pp-effect-order", order)
            el.set("data-pp-effect-type", S.get_pp(el, C.A_EFFECT_TYPE) or "appear")


def _materialize_regions(layer):
    """Turn content regions into renderable output for the browser export.

    Markdown / code / Mermaid are rendered to native SVG (so they appear with no
    network dependency); web / inline-HTML become a live <foreignObject>.
    """
    from . import webcontent

    for group, bounds in list(webcontent.iter_regions(layer)):
        kind = webcontent.region_kind(group)
        if kind in (C.ContentKind.WEB, C.ContentKind.HTML):
            fo = webcontent.build_foreign_object(group, bounds)
            if fo is None:
                continue
            for child in list(group):
                if child.get(C.cn("prompt")) == "true":
                    group.remove(child)
            group.append(fo)
        else:
            webcontent.render_into(group, bounds)


def build(pres, transition="fade", loop=False, start=0):
    """Return a deep-copied lxml tree ready to write as a standalone SVG."""
    from .model import Presentation

    root = copy.deepcopy(pres.svg)
    work = Presentation(root)
    slides = work.slides()

    from . import notes as notes_mod

    first_bbox = None
    notes_list = []
    for slide in slides:
        layer = slide.layer
        bbox = slide.bbox
        if first_bbox is None:
            first_bbox = bbox
        layer.set("data-pp-slide", str(slide.index))
        layer.set("data-pp-bbox", "%s %s %s %s" % bbox)
        # Stable id so the presenter view can reference slides via <use>.
        layer.set("id", "pp-slide-%d" % slide.index)
        notes_list.append(notes_mod.get_notes(slide))
        # Make sure the authoring "hidden layer" display state does not hide it.
        if "display" in layer.style:
            layer.style["display"] = "inline"
        _materialize_regions(layer)
        _export_effects(layer)

    # Authoring-only speaker notes go into PP_CONFIG, not the visible tree.
    notes_mod.strip_notes_tree(root)

    # Strip on-canvas build-order badges (authoring aid only).
    from . import anim
    anim.strip_badges_tree(root)

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
              "loop": bool(loop), "start": int(start), "notes": notes_list}
    cfg_script = ET.SubElement(root, "{%s}script" % SVG)
    cfg_script.set("type", "application/ecmascript")
    cfg_script.text = ET.CDATA("\nwindow.PP_CONFIG = %s;\n" % json.dumps(config))

    player = ET.SubElement(root, "{%s}script" % SVG)
    player.set("type", "application/ecmascript")
    player.text = ET.CDATA("\n" + embed_asset("player.js") + "\n")

    return root.getroottree()


def write(pres, path, **kw):
    tree = build(pres, **kw)
    tree.write(path, xml_declaration=True, encoding="UTF-8")
    return path
