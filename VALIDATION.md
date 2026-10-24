# Validation — 0.0.5

## Page-preview update in 0.0.5

The page-preview popup offers only **Small (three columns)** and **Large (two
columns)**. Cell sizes adapt to the viewport width. A stable scrollbar gutter
prevents reflow oscillation; a one-pixel width allowance avoids Qt wrapping the
last cell when row widths fit exactly. Resize updates are coalesced and stopped
when the popup closes. The arrangement workspace keeps its existing layout.

The final affected-feature suite passed **63 tests in 17.63 seconds**: page-preview
layout at 420/500/640 logical pixels, both sizes, selection/Current indication,
resize and activation, scrollbar popup routing, source closure, PDF-tool page
arrangement and supersampled thumbnail rendering. Tests retain the two-request
and 8 MiB cache limits. Both layouts were captured from the actual Qt app and
visually inspected; screenshots remain outside the repository.

App, executable resource and installer versions agree on **0.0.5**. No Actions,
release, native Windows build or new security scan was run for this UI update.
The full 0.0.4 regression/security results below are historical evidence for the
preceding source; they are not a new full-suite run for 0.0.5.

## Previous 0.0.4 validation

Checked on 25 October 2026: Linux x86_64, Python 3.12, PySide6/Qt 6.12, pypdf 6.21.2, offscreen Qt.

- Full suite: **660 passed, 1 Windows-only skip, 1 existing Qt enum deprecation warning in 357.64 seconds**.
- Focused metadata/reading/backup checks: **72 passed in 23.60 seconds**, overlapping the full suite.
- Source smoke exited zero, including real PDF rendering, PDF-tool previews and metadata backup restoration.
- App, executable version resource and installer are **0.0.4**. Workflow remains manual-only; source push uses `[skip ci]`.

## Reproduced defects and fixes

Seven regression cases failed before the fixes: large saved/source coordinates overflowed Qt scrollbar integer conversion; Favorites and backup exports could overwrite a selected PDF; Favorites export could damage an existing destination on failure; and Favorites export could target the live database.

Reader-controlled source/metadata positioning now clamps to each scrollbar's current limits before converting to Qt integers. New tests exercise restore, jump and resize anchors, then verify normal navigation still works. Further cases exercise infinities, NaN and an arbitrarily large integer at the conversion boundary.

Favorites and app backups share an atomic JSON writer. Exports require a .json destination, reject the live database and reject an existing leading PDF header even when the file is named .json. App backups retain their additional outside-data-folder rule. Failed replacement leaves the old file intact and removes temporary output. Existing valid JSON export/import and app-backup roundtrips remain covered.

Thirteen new regressions account for the suite change from 647 to 660 passing tests. The earlier link-handler, import validation, Explorer path, magnifier, Quick Jump and split-ratio protections remain in the suite.

## Security checks

A fresh pip-audit query of eight installed runtime packages reported **zero known advisories and zero skipped packages**. Bandit parsed application and packaging Python without errors and reported **5 medium / 91 low findings**, unchanged from the previous review. SQL warnings use constant/whitelisted identifiers and bound record values; low warnings concern diagnostic assertions and controlled argument-list subprocess calls. These are reviewed findings, not a claim of a clean static scan. See [SECURITY.md](SECURITY.md).

Audit tools and reports remain outside application dependencies/repository contents. No user PDFs were sent to an advisory service. These checks do not cover every native Qt/PDFium component or certify arbitrary PDFs as safe.

## Limits

No native Windows build, installed-app check, Defender scan, signing or release was performed for this source update. Rebuild the application to apply source fixes to an installed copy. Physical Windows validation remains separate; see [the checklist](docs/windows-validation.md). Dependency redistribution obligations remain in [THIRD_PARTY.md](THIRD_PARTY.md).
