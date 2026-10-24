# Validation — 0.0.2

Checked on 25 October 2026: Linux x86_64, Python 3.12, PySide6/Qt 6.12, offscreen Qt platform.

## Results

- Full suite: **618 passed, 1 Windows-only skip, 1 existing Qt enum deprecation warning in 353.06 seconds**.
- Focused magnifier/reading-aid preflight: **14 passed in 3.83 seconds**, included in the full suite rather than additional unique tests.
- Source smoke exited zero: actual PDF rendering, tool previews and metadata backup restoration.
- App, Windows version resource and installer version agree on **0.0.2**.
- No native Windows build, installer verification, new antivirus scan or release was performed for this source update. Workflow remains manual-only; push uses `[skip ci]`.

## Debugging

Rapidly pointing at region A, moving to B and returning to A while B was still rendering could leave the magnifier blank. Clearing the displayed image now invalidates its render descriptor too. A stale completion schedules the requested region correctly. A real-PDF regression simulates this sequence and confirms recovery; failure/retry and leave/reentry tests also remain.

The earlier Quick Jump Back/Forward, fixed split proportions, magnifier failure-loop and cache-reentry fixes remain covered. Tests exercise generated real PDFs, text selection/copying, search, outlines, links, diagrams, rotations/crops, split views, sessions, saved places and utilities. Source PDFs remain unchanged.

## Excess removed

Removed the unused automatic-release publishing helper and its eight publishing-only tests, plus the unused icon-generation utility. No reader or PDF utility feature was removed. Runtime branding assets, installer/build verification, signing support, notice collection and application regressions remain. The suite count changes from 625 to 618 passing tests: eight retired publishing tests and one new magnifier race regression.

Source remains readable. No videos, demo screenshots, compiled binaries, caches, user metadata or sample PDFs are committed.

## Limits

Search/copying require an extractable text layer; no OCR is included. Complex text ordering, reference matching and image-color preservation are heuristic. Native text extraction and some PDF operations cannot be interrupted mid-call. Themes are comfort preferences, not medical claims.

Physical touchpad, mixed-DPI, GPU/fullscreen, Snap and accessibility testing remain separate; see [Windows validation](docs/windows-validation.md). No signed executable is supplied. Review the exact Qt/PDFium attribution bundle and other binary-distribution obligations in [THIRD_PARTY.md](THIRD_PARTY.md).
