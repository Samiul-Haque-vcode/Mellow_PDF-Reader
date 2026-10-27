<p align="center">
  <img src="mellow/assets/logo.svg" alt="Mellow PDF Reader open-book logo" width="96">
</p>

<h1 align="center">Mellow PDF Reader</h1>
<p align="center"><strong>A softer way to read.</strong></p>
<p align="center">Version 0.0.5 · Windows 10/11 x64 · PDF only · Local-first</p>

Mellow is a compact desktop PDF reader designed for comfortable reading, studying, and comparing documents. It keeps the page central, with tabs and a slim toolbar instead of permanent side panels. Your PDFs remain in their original folders; no account or cloud service is required.

> **Distribution status:** This repository publishes **0.0.5 source code**. It does not provide a newly compiled 0.0.5 installer or executable. Windows build and release verification are described below.

## Highlights

- **Comfortable reading:** Light, Sepia, Dark, and Black appearances; Fit Width/Fit Page, zoom, rotation, customizable page layouts, and optional fullscreen controls.
- **Tabs and split view:** Read one PDF at a time, compare two documents, or open independent views of the same PDF in a resizable horizontal or vertical split.
- **Study tools:** Document outlines, PDF-specific bookmarks, global Favorites, reading ruler, Quick Jump, search, text selection, magnifier, auto-scroll, and local reference previews.
- **Pick up where you left off:** Restore tabs, positions, zoom, and split configuration; import/export Favorites and app metadata backups.
- **Small PDF utilities:** Extract pages, merge PDFs, and make a PDF from images, with previews before saving.
- **Offline reading:** No telemetry or account; dependency installation and some build-time steps may use the network.

[Explore the user guide](docs/user-guide.md) · [Project documentation](docs/README.md) · [Report a bug](../../issues/new/choose)

## Run from source

Requires **Python 3.12 x64** on Windows. From the repository root in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_mellow.py
```

Dependencies are downloaded during setup; ordinary PDF reading works offline. A source checkout is not a prebuilt app.

To build an installer, install **Inno Setup 6** and follow the [Windows packaging guide](docs/distribution.md). Unverified or unsigned installers can trigger Windows reputation warnings; see [SECURITY.md](SECURITY.md).

## Documentation

| I want to… | Go to |
| --- | --- |
| Learn the reading features and keyboard shortcuts | [User guide](docs/user-guide.md) |
| Understand the folders and application components | [Architecture](docs/architecture.md) |
| Set up development, tests, or the Windows workflow | [Development guide](docs/development.md) |
| Package or check a Windows build | [Distribution guide](docs/distribution.md) |
| See outstanding work before a public binary release | [Roadmap](docs/roadmap.md) |
| Check what has changed | [Changelog](CHANGELOG.md) |
| Review test evidence and current limitations | [VALIDATION.md](VALIDATION.md) |
| Report or investigate security concerns | [SECURITY.md](SECURITY.md) |
| Contribute code or documentation | [CONTRIBUTING.md](CONTRIBUTING.md) |

## Scope and limitations

Mellow is **PDF-only**. It does not offer OCR, PDF editing/annotation authoring, AI features, cloud syncing, or PDF-to-Markdown conversion. Searching and copying from an image-only PDF require a text layer that Mellow does not generate. Complex multi-column documents and unlinked references may produce imperfect text order or navigation.

## License and credits

Mellow's own code is [MIT licensed](LICENSE). Bundled dependencies retain their own licenses; review [THIRD_PARTY.md](THIRD_PARTY.md) before redistributing binaries. Version-specific Qt/PDFium attribution review remains outstanding.

Project by [Samiul-Haque-vcode](https://github.com/Samiul-Haque-vcode). Design, coding, and testing used ChatGPT (OpenAI); Mellow is an independent project.
