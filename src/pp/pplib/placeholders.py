"""Construction and inspection of slide placeholders.

A placeholder is a :class:`inkex.Group` carrying plugin metadata. It contains a
transparent bounding rectangle (so the user can click/select the region) and a
prompt :class:`inkex.TextElement` ("Click to add title"). Once the user types
real content the group is flagged ``pp:user-edited`` and protected from master
refresh.
"""

from . import constants as C
from . import svgutil as S


def build_placeholder(ph_def, abs_rect, font_family="sans-serif"):
    """Create a placeholder group from a layout placeholder definition.

    ``ph_def`` is a dict from ``layouts.json`` (id, role, font, align, bullets,
    prompt). ``abs_rect`` is the absolute (x, y, w, h) in user units.
    """
    from inkex import Group, Rectangle

    x, y, w, h = abs_rect
    group = Group()
    S.set_pp(group, C.A_PH_ROLE, ph_def.get("role", C.PhRole.BODY))
    S.set_pp(group, C.A_PH_ID, ph_def["id"])

    # Transparent hit/bounds rectangle.
    rect = Rectangle(x=str(x), y=str(y), width=str(w), height=str(h))
    rect.style = {
        "fill": "none",
        "stroke": "none",
        "pointer-events": "all",
    }
    rect.set(C.cn("ph-bounds"), "true")
    group.add(rect)

    # Prompt text.
    font = float(ph_def.get("font", 28))
    align = ph_def.get("align", "start")
    anchor = {"start": "start", "center": "middle", "end": "end"}.get(align, "start")
    tx = x + (w / 2 if anchor == "middle" else (w if anchor == "end" else 0))
    ty = y + font  # baseline near the top of the box
    prompt = ph_def.get("prompt", "Click to add text")
    text = S.make_text(
        tx, ty, [prompt], font, anchor=anchor,
        fill="#999999", family=font_family,
        bullets=bool(ph_def.get("bullets")),
    )
    text.set(C.cn("prompt"), "true")
    group.add(text)
    return group


def placeholder_text_el(group):
    """Return the text element inside a placeholder group, if any."""
    from inkex import TextElement

    for child in group:
        if isinstance(child, TextElement):
            return child
    return None


def is_prompt(group):
    """True if the placeholder still shows its prompt (no user content)."""
    text = placeholder_text_el(group)
    return text is not None and text.get(C.cn("prompt")) == "true"


def strip_prompts(root):
    """Remove unfilled placeholder prompt text from an export tree.

    Prompts ("Click to add title", etc.) are an authoring aid; like PowerPoint,
    empty placeholders should not appear in the rendered output.
    """
    key = C.cn("prompt")
    for el in list(root.iter()):
        if el.get(key) == "true":
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)


def is_user_edited(group):
    return S.get_pp(group, C.A_USER_EDITED) == "true"


def mark_user_edited(group):
    S.set_pp(group, C.A_USER_EDITED, "true")
    text = placeholder_text_el(group)
    if text is not None and text.get(C.cn("prompt")) is not None:
        del text.attrib[C.cn("prompt")]


def set_placeholder_text(group, lines, bullets=False):
    """Replace placeholder content with real lines and flag it user-edited."""
    text = placeholder_text_el(group)
    if text is None:
        return
    S.set_text_lines(text, lines, bullets=bullets)
    text.style["fill"] = "#000000"
    mark_user_edited(group)
