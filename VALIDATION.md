# Validation — 1.0.0

Review date: 29 October 2026. These results describe source checks on Linux with Python 3.12 and Qt 6.12. They do not establish behavior on physical Windows hardware.

## Functional checks

- New release-boundary regressions reproduced **8 failures before fixes**. The final 11 cases check scrolling at Qt's integer limits, unusually large/non-finite numeric inputs and rejected backup imports preserving existing metadata.
- Focused boundary, backup, position and auto-scroll coverage: **76 passed** before the pypdf update. The complete suite below is the verification against pypdf 6.21.4.
- Full regression suite against pypdf 6.21.4: **678 passed, 1 skipped, 1 warning in 356.59 seconds**. The skipped case requires native Windows Authenticode; the existing warning concerns a deprecated Qt caption enum.
- Source-mode real-PDF smoke check: **exit 0**.
- Python compilation, local documentation links and workflow structure/permission/upload gates: passed.

The suite uses generated real PDFs, including text, outlines, hyperlinks, figures and unusual page dimensions. It exercises navigation, search/copy, themes, previews, independent splits, saved locations, session restoration, tools, cancellation and metadata safety. It is not a comprehensive corpus of hostile or commercial PDFs.

## Security review

- Runtime dependency advisory lookup: **8 installed Python distributions, 0 known advisories, 0 skipped packages**, including pypdf 6.21.4. This does not cover every native component inside Qt/PDFium.
- Bandit on application and packaging Python: **5 medium and 91 low findings; 0 parse errors**. The medium SQL findings use constant/whitelisted identifiers and bound record values. Low findings include smoke-test assertions and argument-list subprocess calls in OS/build helpers. Warnings were reviewed, not suppressed or represented as a clean scan.
- Pattern check for private keys, common API-token formats and credential-bearing URLs in tracked source: no real credentials identified. Two matches are explicitly fake URLs used to test credential rejection. This is a limited heuristic check of the current source tree, not a guarantee about all possible secrets or Git history.
- No private PDF, local database, environment file, rendering cache, demo media or compiled binary is intentionally included in the source tree. Tests use generated fixtures.

## Windows and release status

The 1.0.0 [Windows run](https://github.com/Samiul-Haque-vcode/Mellow_PDF-Reader/actions/runs/40888717597)
completed successfully: **679 tests passed**, native caption/reading-aid checks,
packaged rendering and installer/uninstaller checks passed. Defender reported
**NoThreatsReported**; executable and installer were **NotSigned**. No artifacts
were uploaded. These results describe that commit/build, not a newly compiled
follow-up binary.

Binary redistribution remains blocked by the incomplete version-specific Qt/PDFium attribution review described in [THIRD_PARTY.md](THIRD_PARTY.md). No trusted signing identity is configured. 1.0.0 publishes source only, without an installer or portable binary and without claiming a binary malware scan.

Physical-device checks for touchpad gestures, mixed DPI, Snap Layouts, transitions, accessibility and diverse real-world documents remain in [the Windows checklist](docs/windows-validation.md). Source tests and automated runner checks do not replace them.

## Attribution-check follow-up

This packaging-only follow-up collected nine upstream Qt PDF 6.140.0 notices
(about 70 KB), with original-page and extracted-text hashes. Source-version
matching, other native-library review and LGPL source-access work remain pending.
The collector now inventories actual bundled native files and validates a recorded
review against versions, platform/Python and evidence hashes. Binary artifact
uploads and DistributionReady builds reject incomplete records.

Focused notice-gate, build-verification and release-preparation tests: **36 passed,
1 Windows-only skip** on Linux. Cases include changed/added native binaries,
updated dependency versions, corrupted notices, missing review checks, stale output
reviews and evidence paths escaping the license folder. No reader code changed,
so the prior full-suite results remain the functional baseline; this follow-up
has not run a new native Windows build or published binaries.
