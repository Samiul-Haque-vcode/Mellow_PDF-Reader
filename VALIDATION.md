# Validation — 0.0.1

Checked on 25 October 2026 using Linux x86_64, Python 3.12 and PySide6/Qt 6.12 with Qt's offscreen platform.

## Results

- Full regression suite: **625 passed, 1 Windows-only skip, 1 existing Qt enum deprecation warning in 354.33 seconds**.
- After the final magnifier cache correction: **13 affected-feature tests passed in 3.64 seconds**. This group overlaps the full suite; it is not 13 additional unique tests.
- Source smoke exited successfully, exercising actual PDF rendering, PDF-tool previews and metadata backup restoration.
- Application, Windows version resource and installer version are all **0.0.1**.

The full suite preceded the final cache-reentry correction; the subsequent affected-feature run exercises the final magnifier implementation. No new native Windows build, installer or antivirus scan was run for this source publication. The GitHub workflow is manual-only and the source push uses `[skip ci]`.

## Debug fixes included

- Quick Jump return records the departure in Back/Forward history. Both keyboard and context-menu routes preserve the marker and maintain independent pane histories.
- Swapping books preserves arbitrary divider ratios and presets in horizontal/vertical splits, while retaining reading positions and keeping temporarily maximized panes usable.
- Failed magnifier-region renders show an unavailable message and wait for a different region or changed input rather than continuously retrying at zero delay. Changing the region allows recovery.
- Leaving and returning to the same magnifier source region preserves its cached image or failure state, avoiding a blank Loading display.

Tests use real generated PDFs: text, outlines, native links, images, diagrams, varied page dimensions, rotations, crop, split views, selections, copying, previews, sessions and utilities. Source PDFs remain unchanged.

## Repository cleanup

The previous tracked tree was 7,402,704 bytes across 134 files. The initial cleaned tree was 1,024,860 bytes across 115 files, before this validation note and final small fixes—approximately **86% less source payload**, before Git/ZIP compression. This is a repository-size comparison, not an installed-app memory or executable-size measurement.

Removed showcase videos/images, narration files, old queue and test-history documents, historical release documents and optional benchmark scripts. Kept the working app, branding, regression tests, dependency declarations, installer/build tools, security guidance and license notices. No caches, sample PDFs, user metadata or compiled binaries are committed. Code remains readable rather than minified.

## Limits

Search and copying require extractable text; no OCR is included. Complex text ordering, unlinked reference detection and image-color preservation remain heuristic. Text extraction and some native operations cannot be interrupted mid-call. Reading themes are preferences rather than medical guarantees.

Physical Windows touchpad, mixed-DPI, GPU/fullscreen timing, Snap and accessibility testing remain separate; see [the checklist](docs/windows-validation.md). Source publication does not certify those results. No certificate-signed executable is supplied. Review the exact Qt/PDFium attribution bundle and other dependency obligations before distributing binaries; see [THIRD_PARTY.md](THIRD_PARTY.md).
