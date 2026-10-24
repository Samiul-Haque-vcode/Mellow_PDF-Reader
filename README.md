<p align="center">
  <img src="mellow/assets/logo.svg" alt="Mellow open-book logo" width="88">
</p>
<h1 align="center">Mellow PDF Reader</h1>
<p align="center"><strong>A softer way to read.</strong></p>
<p align="center">Version 0.0.5 · Windows 10/11 x64 · Offline · PDF only</p>

Mellow is a compact desktop PDF reader for everyday reading, textbooks and comparing documents. Tabs and one slim toolbar leave most of the window for the page. Files stay in their original folders—there is no account, cloud service, telemetry or internal document library.

## Reading features

- **Real PDF rendering:** Qt PDF, powered by PDFium, with smooth scrolling, zoom, Fit Width, Fit Page, actual size and independent rotation.
- **Four reading themes:** Light, Sepia, Dark and Black. Sepia changes the actual page and surrounding canvas to a continuous warm paper shade. Theme tuning and figure-color preservation are in **Settings → Appearance**. Color preservation is a pixel heuristic; grayscale images may be tinted.
- **Tabs and split reading:** compare two PDFs or two independent views of one PDF, horizontally or vertically. Resize, swap books, choose proportions or temporarily maximize a pane. Swapping books preserves the divider ratio.
- **Page preview:** Small shows three pages per row; Large shows two. Thumbnail cells adapt to the popup width while keeping sharp source-PDF rendering.
- **Page layouts:** Continuous, Single Page, Two Pages and Two Pages Continuous, with an optional separate cover. Saved document preferences take priority over defaults for new PDFs.
- **Navigation:** printed PDF page labels, custom numbering, Back/Forward history, page previews and nested outline chapter navigation. Temporary **Quick Jump** markers return to a saved spot and participate in Back/Forward history; markers disappear when the app closes.
- **Search and selection:** search with next/previous results, text highlighting, ordinary text selection and copying. Select between two points by clicking the start, scrolling and clicking the end; then preserve line breaks or join paragraphs. Larger copies offer progress and cancellation.
- **Study aids:** a pointer-following magnifier, zoom lock, reversible reading-margin trimming, reading ruler, gentle auto-scroll and source-PDF reference previews. Native links are preferred; unlinked references use local matching with manual fallback.
- **Fullscreen:** optional auto-hiding controls, with the same focused-pane toolbar in split reading.

## Home, saved places and settings

**Home** keeps Recent PDFs, Favorites and the three PDF tools together. Favorites are global saved locations; bookmarks belong to the active PDF and include its internal outline plus personal entries. Missing files offer a Locate action.

**Settings** has four sections:

| Section | Options |
| --- | --- |
| General | Startup, history, app backup/restore, Favorites import/export |
| Reading | New-PDF layout/zoom defaults, gesture and auto-scroll speed, copy format, ruler height/opacity |
| Appearance | Theme and tuning, figure colors, toolbar labels, Windows caption tabs, fullscreen auto-hide |
| Shortcuts | Searchable commands, custom bindings, conflict checks and resets |

Reading sessions restore tabs, positions, zoom and split configuration. Backups contain metadata, not PDFs. Installing over an existing installation preserves data. Uninstalling removes that Windows user's Mellow metadata while preserving original PDFs and exported backups; keep a backup outside Mellow's folders before uninstalling.

## PDF tools

- **Split / Extract Pages:** choose page ranges and save a new PDF.
- **Merge PDFs:** order input documents, preview and combine them.
- **Images to PDF:** order images and choose basic page sizing.

Tools provide real output previews, page arrangement/rotation and cancellation. Source documents remain unchanged by default. They are available from Home and the main menu.

## Useful default shortcuts

| Keys | Action |
| --- | --- |
| Ctrl+O | Open PDF |
| Ctrl+F | Find text |
| Ctrl+A / Ctrl+Shift+A | Select current-page / whole-PDF text |
| Ctrl+C | Copy selected text |
| Ctrl+M / Ctrl+Shift+M | Set / return to Quick Jump |
| Space / Shift+Space | Forward / back one screen |
| Up / Down | Scroll by a line-sized step |
| Left / Right | Previous / next page |
| Alt+Left / Alt+Right | Back / Forward through visited locations |
| Ctrl+Tab / Ctrl+Shift+Tab | Switch document tabs |
| Ctrl+, | Settings |

Text fields keep their normal editing shortcuts. Bindings are customizable.

## Run from source

Install **Python 3.12, 64-bit**, then run from the repository folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_mellow.py
```

Dependencies are downloaded during setup; the installed reader works offline. Normal metadata is stored under `%LOCALAPPDATA%\Mellow\Mellow PDF Reader`. A portable distribution uses a `portable.ini` marker beside the executable and a `mellow-data` folder.

## Build for Windows

Install **Inno Setup 6**, then run:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows.ps1
```

The script creates its Python environment, runs tests, builds the executable with PyInstaller, collects dependency notices, checks packaged PDF rendering and builds an installer. Outputs:

- `dist/MellowPDFReader/MellowPDFReader.exe` — keep its adjacent dependencies together.
- `dist/MellowPDFReader-Setup.exe` — installer.
- `dist/build-verification/` — hashes, signature and available antivirus results.

See [security and signing](SECURITY.md) and [Windows validation](docs/windows-validation.md). Unsigned builds may show Windows reputation warnings. Version 0.0.5 is a source publication; no newly compiled Windows executable or installer is included here.

The GitHub workflow is **manual only**. Pushes and pull requests do not start it; artifact uploads are off by default. No release is published automatically.

## Develop and test

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

[Validation results and limitations](VALIDATION.md) distinguish source tests from native Windows and packaged-app checks.

```text
mellow/       Application, PDF views, storage, controls and branding
packaging/    Windows build, installer, signing and license collection
tests/       Real-PDF regression tests
docs/        Windows validation checklist
```

Tests and developer dependencies are not part of the installed app. This repository omits showcase videos, screenshots, old roadmaps, historical release records, caches and compiled binaries. Source stays readable rather than minified.

## Security

PDF links are limited to ordinary HTTP/HTTPS and email URLs. Local-file and custom
protocol handlers, URL credentials and email attachment parameters are blocked.
Favorites imports have a 32 MB limit and reject invalid pages, non-finite positions
and malformed paths before changing saved data. PDF utilities require pypdf 6.21.2
or newer to include fixes for three malformed-PDF denial-of-service advisories.
Saved and imported reading positions are clamped before conversion to Qt scrollbar
integers. Favorites and app backups use atomic JSON exports that reject live metadata
and PDF destinations; interrupted writes preserve the previous file.
See [the security review](SECURITY.md) for scan scope and remaining limitations.

## Scope and limitations

Mellow is a reader with small PDF utilities. It does not include OCR, AI services, annotation editing, cloud synchronization or PDF-to-Markdown conversion. Selection and search need an extractable text layer. Reference matching and text ordering in complex layouts can be imperfect. Reading colors are comfort preferences, not a medical claim. Physical touchpad, mixed-DPI and accessibility validation require separate device testing.

## License and credits

Mellow's source uses the [MIT license](LICENSE). Dependencies keep their own licenses; read [THIRD_PARTY.md](THIRD_PARTY.md), including the outstanding version-specific Qt/PDFium attribution review before distributing binaries.

Project owner: [Samiul-Haque-vcode](https://github.com/Samiul-Haque-vcode). Developed with ChatGPT (OpenAI) for AI-assisted design, coding and testing. Mellow is an independent project.
