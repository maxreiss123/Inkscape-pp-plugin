"""Action handlers shared by the Presentation Panel (and quick commands).

Each function takes a :class:`pplib.model.Presentation`, performs one action by
reusing the existing library modules, and returns a short status string. Keeping
these here (separate from the GTK shell) makes them unit-testable headlessly.
"""

from . import anim, fields, pages, template, webcontent
from . import constants as C


def status(pres):
    n = pres.slide_count()
    return "%d slide%s" % (n, "" if n == 1 else "s")


def _active(pres):
    return pres.active_slide() or (pres.slides()[0] if pres.slides() else None)


def new_slide(pres, layout=C.LayoutKey.TITLE_CONTENT):
    slide = pages.add_slide(pres, layout)
    fields.update_all(pres)
    return "Added slide %d (%s)" % (slide.index + 1, layout)


def duplicate(pres):
    src = _active(pres)
    if src is None:
        return "No slide to duplicate"
    clone = pages.duplicate_slide(pres, src)
    fields.update_all(pres)
    return "Duplicated to slide %d" % (clone.index + 1)


def delete(pres):
    if pres.slide_count() <= 1:
        return "Cannot delete the last slide"
    target = _active(pres)
    if target is None:
        return "No slide to delete"
    pages.delete_slide(pres, target)
    fields.update_all(pres)
    return "Deleted; %s left" % status(pres)


def move(pres, delta):
    slide = _active(pres)
    if slide is None:
        return "No slide selected"
    pages.move_relative(pres, slide, delta)
    fields.update_all(pres)
    return "Moved to position %d" % (slide.index + 1)


def update_fields(pres):
    fields.update_all(pres)
    return "Numbers / footer / date updated"


def render_content(pres):
    n = webcontent.render_all(pres)
    return "Rendered %d content region%s" % (n, "" if n == 1 else "s")


def apply_master(pres):
    master = template.ensure_master(pres)
    template.apply_to_all(pres, master.definition)
    fields.update_all(pres)
    return "Master applied to all slides"


def toggle_badges(pres):
    has_any = any(anim.is_badge(e) for s in pres.slides() for e in s.layer)
    if has_any:
        for s in pres.slides():
            anim.clear_badges(s)
        return "Build badges hidden"
    total = sum(anim.refresh_badges(s) for s in pres.slides())
    return "Build badges shown (%d)" % total
