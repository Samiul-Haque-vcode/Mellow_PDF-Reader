# Architecture and repository layout

This guide describes the **current source organization**, not a future rewrite. The implementation uses **Python 3.12**, **PySide6 / Qt PDF**, **NumPy**, and **pypdf**. Core desktop UI and PDF rendering are Qt-based; supporting PDF transformations use pypdf.

## Repository map

```text
Mellow_PDF-Reader/
├── README.md                  # Short public entry point
├── CHANGELOG.md               # Version summaries
├── CONTRIBUTING.md            # Contributor workflow
├── LICENSE                    # License for Mellow's own code
├── SECURITY.md                # Security reviews and signing guidance
├── THIRD_PARTY.md             # Dependency redistribution obligations
├── VALIDATION.md              # Version-specific validation evidence
├── .github/
│   ├── ISSUE_TEMPLATE/        # Bug and feature forms
│   ├── pull_request_template.md
│   └── workflows/windows.yml  # Manual Windows build workflow
├── docs/                      # Reading, architecture, development, release
├── mellow/                    # Python application package and UI assets
│   └── assets/                # Logos and Windows artwork
├── packaging/                 # PyInstaller/Inno Setup and verification scripts
├── tests/                     # Qt/PDF regression tests
├── requirements.txt           # Runtime dependencies
├── requirements-dev.txt       # Development/build/test dependencies
├── pytest.ini                 # Test configuration
└── run_mellow.py              # Source launcher
```

## Application components

| Responsibility | Main modules |
| --- | --- |
| App entry and window/tab/split orchestration | `mellow/app.py`, `mellow/__main__.py`, `run_mellow.py` |
| PDF view and coordinate/layout behavior | `mellow/reader.py`, `mellow/geometry.py`, `mellow/pages.py`, `mellow/page_grid.py`, `mellow/rotation.py` |
| Search, selection, and references | `mellow/search.py`, `mellow/search_model.py`, `mellow/selection.py`, `mellow/selection_controls.py`, `mellow/references.py`, `mellow/reference_choices.py` |
| Reading aids and page presentation | `mellow/reading_aids.py`, `mellow/autoscroll.py`, `mellow/page_preferences.py`, `mellow/reading_options.py`, `mellow/theme.py` |
| Home, saved locations, and metadata | `mellow/home.py`, `mellow/locations.py`, `mellow/storage.py`, `mellow/saved_locations.py`, `mellow/backup.py`, `mellow/config.py` |
| PDF operations, preview, and file jobs | `mellow/utility*.py` (where present), `mellow/utilities.py`, `mellow/tool_dialog.py`, `mellow/jobs.py`, `mellow/preview.py`, `mellow/thumbnail.py` |
| UI controls, preferences, and platform behavior | `mellow/settings.py`, `mellow/shortcuts.py`, `mellow/toolbar.py`, `mellow/caption.py`, `mellow/style.py`, `mellow/icons.py`, `mellow/window_effects.py`, `mellow/display.py` |

Mellow uses a `QMainWindow` controller in `mellow/app.py`; a `Reader` subclasses Qt's PDF view. PDF files are rendered using `QPdfDocument` / `QPdfView`. Metadata is kept separately in a local SQLite database via `Store` rather than copying PDFs into an internal library.

## Data boundaries

- **Original PDFs:** Stay at the user's file paths.
- **Local metadata:** Recent documents, settings, document options, saved locations and session state are managed by the store.
- **Exports:** Favorites and app backup output are JSON metadata; PDF tools create separately saved PDF outputs.
- **Portable mode:** `portable.ini` tells the app to use a `mellow-data` folder beside its executable.
- **Distribution:** Windows packaging uses PyInstaller and Inno Setup, with license notices and build verification artifacts.

For exact behavior, refer to source and tests; this file is a map, not a substitute for implementation. Keep it current when responsibilities shift. See [development](development.md) and [distribution](distribution.md).
