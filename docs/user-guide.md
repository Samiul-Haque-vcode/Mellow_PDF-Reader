# User guide

Mellow PDF Reader is a **local-first, PDF-only Windows application**. It opens PDF files from their existing paths and stores reading metadata separately.

## Open, read, and arrange documents

- Open a PDF through the application or **Ctrl+O**. Multiple files open as tabs.
- Work in a single tab by default. Use a horizontal or vertical **split** to compare two PDFs, or two independent views of one PDF.
- Resize the divider, swap sides, adjust proportions, or temporarily maximize one pane. A split has independently navigable page locations.
- Choose **Continuous**, **Single Page**, **Two Pages**, or **Two Pages Continuous**; use a separate cover when appropriate.
- Use **Fit Width**, **Fit Page**, actual-size/zoom controls, and independent page rotation.
- Page previews offer **Small (three columns)** or **Large (two columns)** sizes. Printed PDF page labels and custom numbering help navigate books with roman-numeral front matter.
- Use fullscreen with optional auto-hiding controls; in split view, controls follow the focused pane.

## Make pages comfortable

**Light**, **Sepia**, **Dark**, and **Black** appearances change the reading presentation. Sepia warms both page and surrounding canvas; appearance settings offer tuning and optional figure-color preservation. Figure preservation uses heuristics and may tint grayscale illustrations.

Mellow also offers a reading ruler, pointer-following magnifier, zoom lock, reversible reading-margin trim, gentle auto-scroll, and temporary Quick Jump markers. Quick Jump markers are not permanent bookmarks and vanish after closing the app.

## Find text and references

Search results can be stepped through in either direction. Select and copy text normally, or choose a start point and end point across scrolling; you may preserve line breaks or join paragraph lines. Large selections may have progress and cancellation.

PDF links and source-PDF reference previews assist navigation. Linked references are preferred; unlinked text is matched locally with a manual fallback. Neither search nor selection performs OCR; scanned PDFs need a text layer. Complex equations, columns, and references can be imperfect.

## Home, Favorites, bookmarks, and history

**Home** combines recent PDFs, global Favorites, and PDF utilities:

| Item | Where it applies | Behavior |
| --- | --- | --- |
| PDF outline | Current PDF | Uses that document's internal chapters/bookmark tree. |
| Personal bookmarks | Current PDF | Saves page locations for that file. |
| Favorites | Across PDFs | Global shortcuts to original file paths and specific pages; a missing path can be located again. |
| Quick Jump | Current reading session | Temporary return point; not saved between launches. |
| Back/Forward | Reading navigation | Moves through previously visited locations. |

Mellow restores tabs, positions, zoom, and split arrangement between sessions. It saves **metadata**, not the source PDF content, in its application data store.

## PDF utilities

| Tool | Operation |
| --- | --- |
| Split / Extract Pages | Choose page numbers or ranges and save them as a new PDF. |
| Merge PDFs | Reorder input documents, preview, and combine into a new PDF. |
| Images to PDF | Order selected images and choose basic output page sizing. |

Utility workflows include output preview and page arrangement/rotation. Cancellable operations should leave original source files intact. Review output destinations before saving.

## Settings

| Area | Typical controls |
| --- | --- |
| General | Startup and history preferences, backup/restore, Favorites import/export. |
| Reading | New-document layout and zoom, navigation/gesture speed, copy format, ruler controls. |
| Appearance | Themes, page color tuning, figure colors, toolbar labels, Windows caption tabs, fullscreen behavior. |
| Shortcuts | Search, change, reset, and check conflicts between bindings. |

Document-specific preferences can take priority over defaults when a PDF is reopened.

## Default keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+O` | Open PDF |
| `Ctrl+F` | Find text |
| `Ctrl+A` / `Ctrl+Shift+A` | Select current-page / whole-PDF text |
| `Ctrl+C` | Copy selected text |
| `Ctrl+M` / `Ctrl+Shift+M` | Place / return to Quick Jump |
| `Space` / `Shift+Space` | Scroll forward / backward one screen |
| `Up` / `Down` | Scroll one line-sized step |
| `Left` / `Right` | Previous / next page |
| `Alt+Left` / `Alt+Right` | Back / Forward |
| `Ctrl+Tab` / `Ctrl+Shift+Tab` | Switch tabs |
| `Ctrl+,` | Open Settings |

Text inputs retain normal editing shortcuts. Bindings can be changed in Settings.

## Where data is kept and how removal works

A normal Windows installation stores metadata under `%LOCALAPPDATA%\Mellow\Mellow PDF Reader`. The portable build uses a `portable.ini` marker beside the executable and a nearby `mellow-data` folder.

Import/export and app backup/restore work with **metadata**, not PDF files. Save exported backups outside Mellow's application folders. Installing over an existing installation preserves metadata; uninstalling the installed app removes the current Windows user's Mellow metadata while leaving original PDFs and external backups intact.

## Limitations

Mellow does not provide OCR, AI, annotations editing, cloud synchronization, ebooks, or Markdown conversion. A physical Windows-device accessibility/touchpad/mixed-DPI validation pass is still required. For evidence and known verification gaps see [VALIDATION.md](../VALIDATION.md) and [Windows validation](windows-validation.md).
