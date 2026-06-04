# Inkscape Presentation Plugin

Author PowerPoint-style presentations directly in **Inkscape 1.2+** (best on
1.3+). Each slide is a native Inkscape *page*, so you present by exporting to
PDF — and you can also export a self-contained, browser-playable SVG with
transitions, or preview the deck in your browser without leaving Inkscape.

All commands live under **Extensions → Presentation**.

## Features

- **Setup presentation** — pick a slide size (16:9 / 4:3 / custom), footer, date
  mode and author; creates a default master and the first slide.
- **Slide templates / master** — a reusable background, logo, footer and slide
  number applied across every slide. Edit it once; refresh all slides.
- **Layouts with placeholders** — Title, Title + Content, Two Content and Blank.
  Placeholders ("Click to add title") are positioned automatically and scale to
  any slide size.
- **Auto numbering / footers / date** — slide numbers, total count, footer text
  and date are filled in and re-flow automatically when you add, duplicate or
  reorder slides.
- **Slide management** — new slide from a layout, duplicate, and reorder
  (up / down / to front / to back / to a position).
- **Position helpers** — align/distribute selected objects to the page, page
  margins or each other, and drop margin / center / title-safe guides.
- **Export to PDF** — one PDF page per slide (uses Inkscape's own exporter).
- **Export interactive SVG** — a single self-contained `.svg` that plays in any
  modern browser (keyboard / click navigation, fade / slide transitions).
- **Preview in browser** — opens the interactive build in your default browser
  as a quick presentation mode.

## Install

Requirements: Inkscape 1.2 or newer (the native multi-page Page API is required).

```bash
# Copy into your Inkscape user extensions directory
make install

# …or, for development, symlink it (edits take effect on next run)
make symlink
```

Override the destination if Inkscape stores extensions elsewhere:

```bash
make install INKSCAPE_EXT="$HOME/.config/inkscape/extensions"
```

Typical extension directories:

| OS | Path |
|----|------|
| Linux | `~/.config/inkscape/extensions` |
| macOS | `~/Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions` |
| Windows | `%APPDATA%\inkscape\extensions` |

Restart Inkscape; the commands appear under **Extensions → Presentation**.

You can also build a zip for manual installation:

```bash
make package   # -> dist/inkscape-pp-plugin.zip
```

## Quick start

1. **Extensions → Presentation → Setup Presentation** — choose 16:9, set a footer.
2. **New Slide** — pick *Title and Content*; fill in the placeholders.
3. Repeat; use **Duplicate Slide** / **Reorder Slide** as needed.
4. **Edit Master** to change colors / logo, then **Apply / Refresh Master**.
5. **Update Numbers / Footer** if you want to force a refresh.
6. **Preview in Browser** to rehearse, then **Export to PDF** or
   **Export Interactive SVG** to share.

### Interactive playback keys

`→` / `Space` / `PageDown` next · `←` / `PageUp` previous · `Home` / `End`
first / last · `F` fullscreen · `Esc` exit fullscreen · click left third =
previous, elsewhere = next.

## How it works

Each slide is stored as **both** a native `inkscape:page` (which drives PDF
export and the page boundary on canvas) **and** an Inkscape *layer* that owns the
slide's content. The layer is the authoritative container; the page is its
export/viewport projection, and the two are kept in sync. All plugin metadata
lives in a private XML namespace inside the SVG, so it round-trips through
save/reload and stays invisible to the renderer.

## Development

```bash
pip install -e ".[dev]"   # pytest + ruff (inkex is provided by Inkscape)
make test                 # run the suite
make lint                 # ruff
```

The handlers in `src/pp/*.py` are thin wrappers; the logic lives in
`src/pp/pplib/` (`model`, `pages`, `template`, `layouts`, `fields`, `align`,
`jsexport`). Layouts and the default master are data-driven JSON under
`src/pp/data/`; the browser player is `src/pp/assets/player.js`.

## License

GPL-2.0-or-later, matching the Inkscape / `inkex` ecosystem. See `LICENSE`.
