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
  number applied across every slide. Edit it once; refresh all slides. The
  master commands live under **Extensions → Presentation → Slide Master**:
  *Edit Slide Master* (a tabbed dialog for background colour/image, logo +
  position/size, fonts, sizes, title/body/accent colours, and footer/number/date),
  *Apply / Refresh*, and *Import Master*. Images are embedded so they survive
  save/reload and export.
- **Layouts with placeholders** — Title, Title + Content, Two Content and Blank.
  Placeholders ("Click to add title") are positioned automatically and scale to
  any slide size.
- **Auto numbering / footers / date** — slide numbers, total count, footer text
  and date are filled in and re-flow automatically when you add, duplicate or
  reorder slides.
- **Slide management** — new slide from a layout, duplicate, delete, and reorder
  (up / down / to front / to back / to a position). You can assign a keyboard
  shortcut (e.g. Delete) to *Delete Slide* via
  Edit → Preferences → Interface → Keyboard.
- **Web content regions** — draw a rectangle, then *Add Web Content* to embed a
  live web page (iframe) or inline HTML/JS there. It renders in the interactive
  SVG export / browser preview; on the canvas it appears as a labelled box.
- **Rich content regions** — *Add Content* renders **Markdown**, a
  syntax-highlighted **source-code** snippet, or a **Mermaid** diagram into
  native SVG inside a region you draw, so it shows on the slide itself and in PDF
  export (no internet needed). Paste the source into the dialog's multi-line
  text box, load it from a file, or select a text object on the canvas to use as
  the source. *Markdown* supports headings, lists, block-quotes,
  rules, tables, fenced code and inline bold/italic/code; *code* is highlighted
  with Pygments when available. *Mermaid* `flowchart`/`graph` diagrams render to
  native SVG (boxes, decisions, arrows and labels) with no external tools; if the
  `mmdc` (mermaid-cli) tool is installed it is used for full fidelity and other
  diagram types, otherwise unsupported types fall back to a code block.
  Inline **HTML** and **web page (URL)** regions still render only in the
  interactive browser export (as a `<foreignObject>` / iframe).
  After editing a region's source, run *Render / Refresh Content* to update it.
- **Build animations** — *Add Animation* reveals objects on click during
  playback: select objects to appear one after another, a multi-line text box to
  reveal its bullets one per click, or several objects together; effects are
  Appear / Fade / Fly in / Grow. In the browser preview / interactive export each
  click advances one build step before moving to the next slide; Inkscape and PDF
  show everything. Numbered orange **badges** mark the build order on the canvas
  (stripped from the PDF and interactive exports); toggle them with *Add
  Animation → Show / Hide build-order badges*. Use *Add Animation → Remove* to
  clear an object's animation.
- **Import a master** — *Import Master* reads a PowerPoint presentation or
  template (`.pptx` / `.potx`) or a LibreOffice file (`.odp` / `.otp`) and
  applies its theme: slide size/aspect, the slide master's background (solid
  colour, background **picture**, or `bgRef`), fonts, accent, and title/body
  sizes & colours. The master's **decorative vector shapes** (colour bands,
  rules, accent blocks, logos) are translated to SVG and reproduced behind every
  slide. Existing slides are restyled (content preserved) so the import is
  immediately visible, and a summary dialog lists everything that was imported.
- **Generate deck from outline** — *Generate Deck from Outline* turns a Markdown
  outline into slides: `# Title` → a title slide, `## Heading` → a content slide,
  `- bullet` → body bullets, fenced code / ```` ```mermaid ```` blocks → rendered
  content regions, `---` → a slide break. Paste it or load a file; optionally
  replace the existing slides.
- **Speaker notes + presenter view** — *Speaker Notes* sets per-slide notes
  (paste, or from a selected text object). In the browser preview / interactive
  export press **P** to open a **presenter window** (current + next slide, notes,
  elapsed timer and clock; the two windows stay in sync); the audience window never
  shows notes. Press **S** for a single-screen notes+timer overlay. Notes never
  appear on the slide.
- **Position helpers** — align/distribute selected objects to the page, page
  margins or each other, and drop margin / center / title-safe guides.
- **Export to PDF** — one PDF page per slide (uses Inkscape's own exporter).
- **Export interactive SVG** — a single self-contained `.svg` that plays in any
  modern browser (keyboard / click navigation, build animations, presenter view).
- **Export to HTML** — a self-contained `.html`: *vector* (selectable text,
  interactive, optional font embedding via fontTools) or *raster* (one image per
  slide for pixel-identical display anywhere; needs cairosvg).
- **Export to PowerPoint (.pptx)** — each slide as a full-slide image plus speaker
  notes, so it opens with full fidelity in PowerPoint / LibreOffice (needs cairosvg).
- **Preview in browser** — opens the interactive build in your default browser
  as a quick presentation mode.

## Install

Requirements: Inkscape 1.2 or newer (the native multi-page Page API is required).

### Windows (handy installer)

Download/clone the project, then in the `install\` folder:

- **Double-click `install-windows.bat`** — copies the plugin into
  `%APPDATA%\inkscape\extensions\pp`. Restart Inkscape.
- To also enable PowerPoint / HTML export and font embedding, run in PowerShell
  from the same folder:

  ```powershell
  powershell -ExecutionPolicy Bypass -File Install-Windows.ps1 -WithExtras
  ```

  (installs `cairosvg` + `fonttools` into Inkscape's Python). Uninstall with
  `uninstall-windows.bat` or `Install-Windows.ps1 -Uninstall`.

### Linux / macOS

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
first / last · `F` fullscreen · `P` presenter window · `S` notes overlay ·
`Esc` exit fullscreen · click left third = previous, elsewhere = next.

## Quick access (one-click commands & shortcuts)

Inkscape extensions run as a blocking subprocess, so a *persistent* panel isn't
possible (it would freeze Inkscape) and a *docked* panel is built into Inkscape's
core. Instead, the most-used actions have **one-click "Quick" commands** under
**Extensions → Presentation → Quick** — New Slide, Duplicate, Delete, Move
earlier/later, Update fields, Render content, Toggle badges, Apply master, and
Preview. They run instantly with **no dialog**.

For zero menu-digging, assign each a **keyboard shortcut**: Edit → Preferences →
Interface → Keyboard, search "Quick" (or the command name), and bind a key — then
e.g. one keypress adds a slide, another previews. You can also run any command
from Inkscape's command palette (`?`).

## How it works

Each slide is stored as **both** a native `inkscape:page` (which drives PDF
export and the page boundary on canvas) **and** an Inkscape *layer* that owns the
slide's content. The layer is the authoritative container; the page is its
export/viewport projection, and the two are kept in sync. All plugin metadata
lives in a private XML namespace inside the SVG, so it round-trips through
save/reload and stays invisible to the renderer.

## Development

```bash
pip install -e ".[dev]"      # pytest + ruff (inkex is provided by Inkscape)
pip install -e ".[export]"   # optional: cairosvg (PPTX / raster HTML), fonttools
make test                 # run the suite
make lint                 # ruff
```

The handlers in `src/pp/*.py` are thin wrappers; the logic lives in
`src/pp/pplib/` (`model`, `pages`, `template`, `layouts`, `fields`, `align`,
`jsexport`). Layouts and the default master are data-driven JSON under
`src/pp/data/`; the browser player is `src/pp/assets/player.js`.

## License

GPL-2.0-or-later, matching the Inkscape / `inkex` ecosystem. See `LICENSE`.
