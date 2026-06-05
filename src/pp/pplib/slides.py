"""Render a single slide to a standalone, cropped SVG (and optionally PNG).

Shared by the PowerPoint and rasterised-HTML exporters. Content regions are
materialised to native SVG, build animations are flattened to their final state
(everything visible), and authoring chrome (badges, master, namedview, notes) is
removed, so the output is exactly what the audience should see.
"""

import copy

import lxml.etree as ET

from . import anim
from . import constants as C
from . import notes as notes_mod
from . import svgutil as S

SVG = "http://www.w3.org/2000/svg"


def slide_svg_tree(pres, slide):
    """Return an lxml ElementTree for ``slide`` cropped to its page box."""
    from . import webcontent
    from .model import Presentation

    root = copy.deepcopy(pres.svg)
    work = Presentation(root)
    target_id = slide.slide_id

    # Materialise content + drop every other slide layer.
    keep = None
    for s in work.slides():
        if s.slide_id == target_id:
            keep = s
            for group, bounds in list(webcontent.iter_regions(s.layer)):
                kind = webcontent.region_kind(group)
                if kind in (C.ContentKind.WEB, C.ContentKind.HTML):
                    fo = webcontent.build_foreign_object(group, bounds)
                    if fo is not None:
                        group.append(fo)
                else:
                    webcontent.render_into(group, bounds)
        else:
            s.layer.getparent().remove(s.layer)

    # Remove authoring-only content.
    from . import placeholders as ph
    anim.strip_badges_tree(root)
    notes_mod.strip_notes_tree(root)
    ph.strip_prompts(root)
    for el in list(root):
        if S.get_pp(el, C.A_ROLE) == C.Role.MASTER:
            root.remove(el)
    nv = root.find("{%s}namedview" % C.SODIPODI_NS)
    if nv is not None:
        root.remove(nv)

    bbox = keep.bbox if keep is not None else (0.0, 0.0, pres.width, pres.height)
    x, y, w, h = bbox
    root.set("viewBox", "%s %s %s %s" % bbox)
    root.set("width", str(w))
    root.set("height", str(h))
    root.attrib.pop("preserveAspectRatio", None)
    return root.getroottree(), (w, h)


def slide_svg_bytes(pres, slide):
    tree, size = slide_svg_tree(pres, slide)
    return ET.tostring(tree, xml_declaration=True, encoding="UTF-8"), size


def slide_png_bytes(pres, slide, scale=2.0):
    """Rasterise a slide to PNG bytes via cairosvg. Raises if cairosvg missing."""
    import cairosvg

    svg_bytes, (w, h) = slide_svg_bytes(pres, slide)
    out_w = max(1, int(round(w * scale)))
    out_h = max(1, int(round(h * scale)))
    png = cairosvg.svg2png(bytestring=svg_bytes, output_width=out_w, output_height=out_h)
    return png, (out_w, out_h)
