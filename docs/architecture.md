# Architecture

Mellow is a Python desktop application using PySide6 Widgets and Qt PDF/PDFium.
NumPy applies reading colors to rendered pages; pypdf handles PDF transformations.
The reviewed Windows 1.0.0 build uses Python 3.14.10, Qt Essentials/PDF wheels,
and the pinned versions in `packaging/windows-release-constraints.txt`.

## Repository

```text
mellow/          Reader, document views, storage, controls and branding
mellow/assets/   Open-book logo and Windows application artwork
packaging/       Build, installer, signing, source and notice verification
tests/          Real-PDF regression coverage
docs/           Reading, development, distribution and validation guides
.github/         Issue/PR templates and guarded workflows
```

## Responsibilities

| Area | Modules |
| --- | --- |
| Window, tabs and split orchestration | `mellow/app.py`, `mellow/reader.py` |
| Page geometry, layouts and navigation | `geometry.py`, `pages.py`, `page_grid.py`, `rotation.py`, `page_preferences.py` |
| Search, selection and references | `search.py`, `search_model.py`, `selection.py`, `selection_controls.py`, `references.py`, `reference_choices.py` |
| Themes and reading aids | `theme.py`, `reading_aids.py`, `autoscroll.py`, `reading_options.py` |
| Home and saved metadata | `home.py`, `storage.py`, `saved_locations.py`, `locations.py`, `backup.py`, `config.py` |
| PDF tools, jobs and previews | `utilities.py`, `jobs.py`, `tool_dialog.py`, `preview.py`, `thumbnail.py` |
| Settings and Windows controls | `settings.py`, `shortcuts.py`, `toolbar.py`, `caption.py`, `display.py`, `window_effects.py` |

Modules in the table are under `mellow/`. `Window` is a `QMainWindow`; `Reader`
uses Qt's `QPdfView` with Mellow selection controls. Qt renders from the original
PDF, including mathematical content and source-PDF previews.

## Data boundaries

- Original PDFs remain at their file locations; Mellow does not create a library copy.
- SQLite stores small settings, saved locations and session metadata separately.
- Backups and Favorites exports contain metadata, not PDFs; PDF tools save new output files.
- Rendering caches are temporary, not a permanent collection of page images.
- Portable mode stores metadata beside the executable instead of the normal app-data folder.
- Qt libraries remain dynamically loaded and replaceable; corresponding source and notice evidence accompany distribution.

See [development](development.md), [distribution](distribution.md) and the
[user guide](user-guide.md) for commands and behavior. This map does not imply
that native PDF parsing is sandboxed or that arbitrary documents are safe.
