# Changelog

Notable **source changes** are summarized here. This file is not a list of downloadable installers; see [distribution status](README.md#run-from-source) and [validation](VALIDATION.md) before assuming a Windows binary has been built.

## 0.0.5 — 2026-10

- Changed the page preview to two adaptive sizes: **Small (three columns)** and **Large (two columns)**.
- Stabilized popup resizing and scrolling layout.
- Added related preview regressions; the recorded focused 0.0.5 suite passed **63 tests**.
- **No new compiled Windows installer, signed binary, GitHub Release, or full-suite rerun is claimed for 0.0.5.** See [VALIDATION.md](VALIDATION.md).

## 0.0.4 — 2026-10

- Strengthened PDF-link handling and Favorites import validation.
- Improved saved-position safety around Qt scrollbar integer bounds.
- Added atomic metadata exports and protections against unsafe export destinations.
- Updated the minimum pypdf version in response to disclosed denial-of-service advisories.
- The historical full Linux offscreen regression run and its limits are recorded in [VALIDATION.md](VALIDATION.md); review [SECURITY.md](SECURITY.md) for the point-in-time security analysis.

For commit-level detail and earlier work, use the [repository history](../../commits/main). Do not substitute historical test results for a new release's verification.
