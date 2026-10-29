<p align="center">
  <img src="mellow/assets/logo.svg" alt="Mellow open-book logo" width="88">
</p>
<h1 align="center">Mellow PDF Reader</h1>
<p align="center"><strong>A softer way to read.</strong></p>
<p align="center">Windows 10/11 · 64-bit · Offline · MIT-licensed source</p>

Mellow is a comfortable PDF reader for everyday reading, studying and comparing documents. Compact tabs and one toolbar leave room for your pages. Your PDFs stay in their own folders, without accounts, telemetry, cloud services or library imports.

[Getting started](#getting-started) · [Features](#features) · [PDF tools](#pdf-tools) · [Settings](#settings-and-data) · [Build](#building-on-windows) · [License](#license-and-credits)

## Getting started

Windows downloads are on [Releases](https://github.com/Samiul-Haque-vcode/Mellow_PDF-Reader/releases/tag/v1.0.0) once their release checks complete. Choose **Setup x64** for installation, or extract the entire **Portable x64** ZIP and run `MellowPDFReader.exe`. Keep its adjacent folders. Packages are unsigned; see [security and signing](SECURITY.md).

For source builds, use the explicitly named **MellowPDFReader-1.0.0-Source.zip** matching the Windows downloads. Separate Qt/PySide source archives are for rebuilding those libraries and are not needed to run Mellow.

Install **Python 3.14.10 or newer 3.14.x, 64-bit**. In the repository folder, open PowerShell and run:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_mellow.py
```

Setup downloads dependencies. Reading and PDF tools work offline afterward.

Choose **Open PDF** on Home, use **Ctrl+O**, or use **+** beside document tabs. The toolbar follows the focused pane when reading two documents. Find themes in **Settings → Appearance** and reading aids in **☰ → Reading**.

## Features

### Comfortable reading

- **Light, Sepia, Dark and Black:** recolor PDF pages as well as the surrounding canvas. Sepia uses a continuous cream field with warm ink. Light preserves the original page colors.
- **Theme tuning:** adjust warmth and contrast, with optional figure-color preservation. The toolbar keeps a consistent neutral appearance across themes.
- **Layouts:** Continuous, Single Page, Two Pages and Two Pages Continuous, with an optional separate cover.
- **Zoom and rotation:** Fit Width, Fit Page, Actual Size, mouse/touchpad zoom and independent rotation. Lock Zoom blocks zoom changes until unlocked.
- **Fullscreen:** optionally hide controls and reveal them at the top edge.

### Navigation and study

- **Independent split reading:** read different PDFs or two locations in one PDF, side by side or top to bottom. Resize, swap books or temporarily maximize a pane; swapping preserves the divider ratio.
- **Sharp page previews:** Small shows **three pages per row**; Large shows **two**. Thumbnails adapt to the popup width.
- **Find text:** highlight results and move between matches without leaving your document.
- **PDF navigation:** printed page labels, custom numbering, nested outline chapters and Back/Forward history.
- **Quick Jump:** save a temporary reading marker and return after exploring. Returning preserves the departure location in Back/Forward history. Markers last for the current app session.
- **Text selection:** select normally, select a page or the whole PDF, or choose two endpoints across pages. Copy with original line breaks or joined paragraphs; larger copies support cancellation.
- **Reading aids:** pointer-following magnifier, adjustable ruler, gentle auto-scroll and reversible reading-margin trimming.
- **Reference previews:** inspect native PDF links and locally matched references in a floating source-PDF preview; pin it or open the destination in the opposite pane.

### Saved places

**Home** brings together Recent PDFs, Favorites and PDF tools. **Favorites** save locations across documents; **Bookmarks** show the active PDF's outline and personal saved pages. Rename and remove personal entries, search saved places and locate missing files.

Sessions restore open tabs, reading positions, zoom and split configuration. PDFs are opened directly and are never copied into an internal library.

## PDF tools

| Tool | What it does |
| --- | --- |
| Split / Extract Pages | Save selected pages or ranges to a new PDF. |
| Merge PDFs | Order multiple PDFs and combine them into one file. |
| Images to PDF | Arrange images and choose basic page sizing. |

Tools offer output previews, page arrangement, rotation and cancellation. Original documents remain unchanged by default. Access tools from Home or **☰**.

## Settings and data

| Section | Main options |
| --- | --- |
| General | Startup, recent history, app backup/restore, Favorites import/export |
| Reading | Default layout/fit, zoom gestures, auto-scroll speed, copy format, ruler |
| Appearance | Reading themes, figure colors, toolbar labels, caption tabs, fullscreen controls |
| Shortcuts | Search commands, change bindings, check conflicts and reset defaults |

Metadata is normally stored in `%LOCALAPPDATA%\Mellow\Mellow PDF Reader`. Portable mode uses a `portable.ini` marker beside the executable and stores metadata in `mellow-data` beside it. No rendered-page images are permanently stored.

**Before uninstalling**, use Settings to save a backup outside Mellow's folders. Backups contain settings and saved locations, **not PDFs**. Installing over an existing installation preserves metadata; uninstalling removes that Windows user's Mellow metadata. Original PDFs and separately exported backups are preserved. Restore a backup after reinstalling; the referenced PDFs must still be available.

## Default shortcuts

| Keys | Action |
| --- | --- |
| Ctrl+O | Open PDF |
| Ctrl+F | Find text |
| Ctrl+A / Ctrl+Shift+A | Select current-page / whole-PDF text |
| Ctrl+C | Copy selected text |
| Ctrl+M / Ctrl+Shift+M | Set / return to Quick Jump |
| Space / Shift+Space | Forward / back one screen |
| Up / Down | Scroll a line-sized step |
| Left / Right | Previous / next page |
| Alt+Left / Alt+Right | Back / Forward |
| Ctrl+Tab / Ctrl+Shift+Tab | Next / previous tab |
| Ctrl+, | Settings |

Shortcuts are customizable. Text fields keep their normal editing shortcuts.

## Building on Windows

Install Python 3.14.10 or newer 3.14.x x64 and **Inno Setup 6**, then run:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows.ps1
```

The script creates an environment, runs tests, builds with PyInstaller, collects notices, checks packaged rendering and compiles an installer. Local outputs:

| Path | Contents |
| --- | --- |
| `dist/MellowPDFReader/` | Executable and required adjacent libraries |
| `dist/MellowPDFReader-Setup.exe` | Installer |
| `dist/build-verification/` | Hashes, package inventory, signature and available Defender results |

Keep the executable with its adjacent dependencies. Dependency upgrades require updating the exact-version notice review described in [THIRD_PARTY.md](THIRD_PARTY.md). Use `packaging/windows.ps1 -DistributionReady` to require the recorded notice review and a successful Defender scan; see the [release checklist](docs/release-checklist.md). Builds are unsigned unless you provide a trusted signing identity; see [security and signing](SECURITY.md). Mellow does not install a certificate or alter Windows protection settings.

Ordinary source pushes do not start Windows builds. Explicit inventory/release commits and manual workflows run checks. The distribution workflow uploads directly to Releases after verification; it does not upload Actions artifacts. Corresponding library sources are separate optional release assets.

## Development and verification

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

```text
mellow/       Reader, PDF views, storage, controls and branding
packaging/    Windows build, installer, signing and notice collection
tests/        Real-PDF regression tests
docs/         Release notes and Windows validation checklist
```

Tests and development tools are excluded from installed app packages. See [validation evidence](VALIDATION.md) and the [Windows device checklist](docs/windows-validation.md). Report reproducible bugs through [Issues](https://github.com/Samiul-Haque-vcode/Mellow_PDF-Reader/issues), including the version and steps. Avoid uploading private documents or personal backup files.

## Limitations

Search and selection require an extractable text layer; OCR is not included. Complex layouts can affect text order and automatic reference matching. Figure preservation uses pixel-based heuristics: grayscale images may be tinted, and low-contrast colored ink may be adjusted in dark modes. Themes do not modify the source PDF.

Mellow has no annotation editor, cloud synchronization, AI service or PDF-to-Markdown conversion. Physical touchpad behavior, mixed-DPI displays and accessibility need device testing. Tests do not certify that arbitrary PDFs are safe; keep dependencies current and follow [security guidance](SECURITY.md).

## License and credits

Mellow's source uses the [MIT license](LICENSE). Dependencies retain their own terms; see [THIRD_PARTY.md](THIRD_PARTY.md). MIT licensing of the app does not replace Qt/PDFium redistribution requirements.

Project owner: [Samiul-Haque-vcode](https://github.com/Samiul-Haque-vcode). Developed with ChatGPT (OpenAI) for AI-assisted design, coding and testing. Mellow is an independent project.
