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

The release workflow is configured to run native Windows caption/reading-aid checks, regression tests, a packaged real-PDF smoke check, installer/uninstaller checks and available Defender verification before publishing the source release. These are pending until the corresponding Actions run completes; workflow configuration alone is not evidence of a pass.

Binary redistribution remains blocked by the incomplete version-specific Qt/PDFium attribution review described in [THIRD_PARTY.md](THIRD_PARTY.md). No trusted signing identity is configured. 1.0.0 publishes source only, without an installer or portable binary and without claiming a binary malware scan.

Physical-device checks for touchpad gestures, mixed DPI, Snap Layouts, transitions, accessibility and diverse real-world documents remain in [the Windows checklist](docs/windows-validation.md). Source tests and automated runner checks do not replace them.
