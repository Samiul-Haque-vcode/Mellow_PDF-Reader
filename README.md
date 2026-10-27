<p align="center">
  <img src="mellow/assets/logo.svg" alt="Mellow PDF Reader open-book logo" width="96">
</p>

<h1 align="center">Mellow PDF Reader</h1>
<p align="center"><strong>A softer way to read.</strong></p>
<p align="center">
  Windows 10/11 (x64) · PDF only · Offline reading · Source version 0.0.5
</p>

<p align="center">
  <a href="#features">Features</a> ·
  <a href="#getting-started">Getting started</a> ·
  <a href="#documentation">Documentation</a> ·
  <a href="#project-status-and-limitations">Project status</a>
</p>

**Mellow** is a lightweight, reading-first PDF application for Windows. It is made for textbooks, long documents, and reading two PDFs side by side—without crowding the page with permanent tool panels.

Your PDFs remain in their original folders. Mellow does not require an account, sync service, or internet connection for ordinary reading.

## Features

### Read comfortably

- **Uncluttered workspace** — document tabs, a compact toolbar, optional fullscreen, and no permanently open sidebar.
- **Reading appearances** — Light, Sepia, Dark, and Black themes, with page-color tuning and optional figure-color preservation.
- **Flexible page views** — Fit Width, Fit Page, zoom, rotation, continuous or single-page layouts, and two-page spreads with an optional separate cover.
- **Side-by-side reading** — open two PDFs or two independent views of one PDF; choose horizontal or vertical split, resize the divider, or temporarily focus on one pane.

### Find information and keep your place

- **Navigation** — PDF outline, printed page labels, customizable numbering, Back/Forward history, and adaptive page previews.
- **Study aids** — reading ruler, magnifier, margin trimming, zoom lock, gentle auto-scroll, and local reference previews.
- **Search and copy** — find text, select across a scrolling document, and choose whether copied text preserves line breaks.
- **Saved locations** — document-specific bookmarks, global Favorites pointing to original files and pages, and temporary Quick Jump markers.
- **Session restore** — reopen tabs with saved reading positions, zoom, and split arrangement.

### Work with PDF files

Mellow includes three small utilities with output previews: **Extract Pages**, **Merge PDFs**, and **Images to PDF**. The original input files remain unchanged by default.

For details about each feature and the default keyboard shortcuts, see the [user guide](docs/user-guide.md).

## Getting started

> **Availability:** Version **0.0.5** is published here as **source code**. This repository does not include a newly compiled, verified 0.0.5 Windows installer or executable. Do not treat the source archive as an installable Windows app.

### Run from source

Install **Python 3.12 (64-bit)** on Windows, then open PowerShell in the repository folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_mellow.py
```

After Mellow opens, press **Ctrl+O** to choose a PDF. Open additional PDFs as tabs; use the split-view controls when you want to compare pages. Adjust reading colors and shortcuts in **Settings**.

Setup downloads dependencies, but normal reading runs locally and offline.

### Build for Windows

For a Windows installer, install **Inno Setup 6** and follow the [distribution guide](docs/distribution.md). It covers the build script, portable mode, verification outputs, and release-readiness checks. Unsigned development builds may prompt Windows reputation warnings; read the [security guidance](SECURITY.md).

## Documentation

| Audience | Guides |
| --- | --- |
| **Readers** | [User guide](docs/user-guide.md) · [Keyboard shortcuts](docs/user-guide.md#default-keyboard-shortcuts) |
| **Developers** | [Architecture](docs/architecture.md) · [Development and tests](docs/development.md) · [Contributing](CONTRIBUTING.md) |
| **Release maintainers** | [Windows packaging](docs/distribution.md) · [Windows validation checklist](docs/windows-validation.md) |
| **Project tracking** | [Roadmap](docs/roadmap.md) · [Changelog](CHANGELOG.md) |
| **Reviews and compliance** | [Validation record](VALIDATION.md) · [Security](SECURITY.md) · [Third-party licenses](THIRD_PARTY.md) |

Browse the complete [documentation index](docs/README.md). Bugs and feature suggestions can be filed through [GitHub Issues](../../issues/new/choose).

## Project status and limitations

Mellow is a **PDF reader**, not a full PDF editor. It does **not** provide OCR, annotation editing, cloud synchronization, AI features, EPUB/Markdown reading, or PDF-to-Markdown conversion. Search and text copying need an extractable text layer; complex document layouts can affect text order and reference matching.

The Windows build workflow runs **manually**, not on every push. Source tests and historical verification are documented in [VALIDATION.md](VALIDATION.md); these do not establish that a downloadable Windows installer has been built, signed, or tested on physical Windows devices. Third-party Qt/PDFium attribution review is also outstanding before binary redistribution.

## License and credits

Mellow's own source code is licensed under the [MIT License](LICENSE). Dependencies have separate licensing and distribution requirements; see [THIRD_PARTY.md](THIRD_PARTY.md).

Created by [Samiul-Haque-vcode](https://github.com/Samiul-Haque-vcode), with ChatGPT (OpenAI) used to assist design, implementation, and testing. Mellow is an independent project.
