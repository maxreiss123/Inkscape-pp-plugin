#!/usr/bin/env python3
"""Presentation Panel: a floating window of buttons for the common commands.

Inkscape extensions cannot add a *docked* side panel, but this opens a small
always-on-top window so you can click actions instead of hunting through the
Extensions menu. All edits are applied to the document when you close the panel.
While the panel is open the canvas is busy (the extension is running), so the
selection-based commands (Animate, Align, Add Content, Notes) stay on the menu;
this panel covers slide, master, build and export/preview actions.

The action logic lives in :mod:`pplib.panel_actions` (unit-tested); this file is
just the GTK shell and degrades gracefully when PyGObject is unavailable.
"""

import inkex
from pplib import constants as C
from pplib import panel_actions as A
from pplib.model import Presentation


class PresentationPanel(inkex.EffectExtension):
    def effect(self):
        pres = Presentation(self.svg)
        if not pres.is_initialized():
            inkex.errormsg("Run Presentation > Setup first.")
            return
        try:
            import gi
            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk
        except Exception:
            inkex.errormsg(
                "The Presentation Panel needs PyGObject (GTK 3), which this "
                "Inkscape build does not provide. Use the Extensions > "
                "Presentation menu, or assign keyboard shortcuts to the commands "
                "(Edit > Preferences > Interface > Keyboard).")
            return
        try:
            self._run(Gtk, pres)
        except Exception as exc:  # noqa: BLE001
            inkex.errormsg("Presentation Panel error: %s" % exc)

    # -- GUI -----------------------------------------------------------------
    def _run(self, Gtk, pres):
        win = Gtk.Window(title="Presentation")
        win.set_keep_above(True)
        win.set_default_size(300, -1)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        outer.set_border_width(8)

        status = Gtk.Label(label=A.status(pres))
        status.set_xalign(0.0)
        status.set_line_wrap(True)

        def do(fn, *args):
            def handler(_btn):
                try:
                    status.set_text(fn(pres, *args))
                except Exception as exc:  # noqa: BLE001
                    status.set_text("Error: %s" % exc)
            return handler

        def section(title, buttons):
            lbl = Gtk.Label()
            lbl.set_markup("<b>%s</b>" % title)
            lbl.set_xalign(0.0)
            outer.pack_start(lbl, False, False, 2)
            box = Gtk.FlowBox()
            box.set_selection_mode(Gtk.SelectionMode.NONE)
            box.set_max_children_per_line(2)
            box.set_min_children_per_line(2)
            for text, cb in buttons:
                btn = Gtk.Button(label=text)
                btn.connect("clicked", cb)
                box.add(btn)
            outer.pack_start(box, False, False, 0)

        section("Slides", [
            ("New Title", do(A.new_slide, C.LayoutKey.TITLE)),
            ("New Content", do(A.new_slide, C.LayoutKey.TITLE_CONTENT)),
            ("New Two-Col", do(A.new_slide, C.LayoutKey.TWO_CONTENT)),
            ("New Blank", do(A.new_slide, C.LayoutKey.BLANK)),
            ("Duplicate", do(A.duplicate)),
            ("Delete", do(A.delete)),
            ("◀ Move", do(A.move, -1)),
            ("Move ▶", do(A.move, 1)),
        ])
        section("Master & content", [
            ("Apply master", do(A.apply_master)),
            ("Update fields", do(A.update_fields)),
            ("Render content", do(A.render_content)),
            ("Toggle badges", do(A.toggle_badges)),
        ])
        section("Build", [
            ("Outline…", self._outline_handler(Gtk, pres, status)),
        ])
        section("Present & export", [
            ("Preview", self._preview_handler(pres, status)),
            ("Export HTML", self._export_handler(Gtk, pres, status, "html")),
            ("Export PPTX", self._export_handler(Gtk, pres, status, "pptx")),
        ])

        outer.pack_start(status, False, False, 6)
        close = Gtk.Button(label="Apply & Close")
        close.connect("clicked", lambda _b: win.close())
        outer.pack_start(close, False, False, 2)

        win.add(outer)
        win.connect("destroy", lambda *_a: Gtk.main_quit())
        win.show_all()
        Gtk.main()

    def _preview_handler(self, pres, status):
        def handler(_btn):
            try:
                from pplib import preview
                path = preview.build_temp(pres)
                preview.open_in_browser(path)
                status.set_text("Opened preview in browser")
            except Exception as exc:  # noqa: BLE001
                status.set_text("Error: %s" % exc)
        return handler

    def _export_handler(self, Gtk, pres, status, kind):
        def handler(_btn):
            dlg = Gtk.FileChooserDialog(title="Export %s" % kind.upper(),
                                        action=Gtk.FileChooserAction.SAVE)
            dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL,
                            "Save", Gtk.ResponseType.OK)
            dlg.set_current_name("presentation.%s" % kind)
            resp = dlg.run()
            path = dlg.get_filename()
            dlg.destroy()
            if resp != Gtk.ResponseType.OK or not path:
                return
            try:
                if kind == "html":
                    from pplib import htmlexport
                    htmlexport.write(pres, path, mode="vector")
                else:
                    from pplib import pptxexport
                    pptxexport.export(pres, path)
                status.set_text("Exported %s" % path)
            except Exception as exc:  # noqa: BLE001
                status.set_text("Error: %s" % exc)
        return handler

    def _outline_handler(self, Gtk, pres, status):
        def handler(_btn):
            dlg = Gtk.Dialog(title="Generate deck from outline")
            dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL,
                            "Generate", Gtk.ResponseType.OK)
            dlg.set_default_size(440, 360)
            tv = Gtk.TextView()
            tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            sw = Gtk.ScrolledWindow()
            sw.add(tv)
            sw.set_min_content_height(280)
            area = dlg.get_content_area()
            area.pack_start(sw, True, True, 0)
            chk = Gtk.CheckButton(label="Replace existing slides")
            area.pack_start(chk, False, False, 0)
            dlg.show_all()
            resp = dlg.run()
            if resp == Gtk.ResponseType.OK:
                buf = tv.get_buffer()
                text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
                try:
                    from pplib import outline
                    created, _ = outline.generate(pres, text,
                                                  replace=chk.get_active())
                    status.set_text("Generated %d slide(s)" % created)
                except Exception as exc:  # noqa: BLE001
                    status.set_text("Error: %s" % exc)
            dlg.destroy()
        return handler


if __name__ == "__main__":
    PresentationPanel().run()
