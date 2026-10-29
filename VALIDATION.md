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

The original source-only release is being supplemented through the dedicated
Windows distribution workflow. The new package uses Python **3.14.10**, Essentials
and PDF wheels without unused Qt Addons/WebEngine, and guarded removal of Mesa
and the duplicate Qt OpenSSL backend. The existing public source tag is preserved;
the matching source ZIP identifies the updated packaging commit.

Physical-device checks for touchpad gestures, mixed DPI, Snap Layouts, transitions, accessibility and diverse real-world documents remain in [the Windows checklist](docs/windows-validation.md). Source tests and automated runner checks do not replace them.

## Distribution and attribution follow-up — 30 October 2026

- Clean minimal-dependency Linux environment: **694 passed, 1 skipped, 1 warning**
  in 360.85 seconds. The skipped test requires native Windows Authenticode. No
  reader feature code changed in this packaging follow-up.
- [Windows inventory 40929960790](https://github.com/Samiul-Haque-vcode/Mellow_PDF-Reader/actions/runs/40929960790):
  **51 focused tests passed**, frozen real-PDF and PDF-tool rendering passed.
  Attribution review matched all **132 native files**, **64 hashed evidence files**
  and **seven package versions**, with zero collection issues. No Actions artifacts
  were uploaded.
- Windows package removal: Mesa 20,639,544 bytes; optional Qt OpenSSL plugin
  317,752 bytes; its unused SSL/crypto DLLs 8,459,032 bytes. These removals total
  **29,416,328 bytes** before compression. The build checks other import tables
  before removing the optional TLS dependencies; Python SSL and Windows Schannel
  remain. Packaged rendering also passed with QT_OPENGL=software.
- Fresh advisory lookup on the seven pinned Windows runtime/build distributions:
  **0 known advisories, 0 skipped distributions**. This is not a native-component
  vulnerability scan or a guarantee against undisclosed vulnerabilities.
- Added release-source integrity/publication guards and packaging checks:
  **47 passed, 1 Windows-only skip** on Linux. Cases reject changed native files,
  unregistered native notices, bad source download hashes/sizes/paths, failing test
  reports and publication from another repository or branch.
- Qt source matching is supported by verified archives and the public maintainer
  clarification in [PYSIDE-3485](https://qt-project.atlassian.net/browse/PYSIDE-3485).
  Complete notices, per-native mappings and replacement instructions are in
  packaging/notices. The strict gate does not complete a legal review by itself.

The dedicated release job must pass the full Windows suite, native caption/aids,
freeze/installer/portable checks, notice gate, Defender scan and source-archive
hash verification before uploading executables. Its Verification ZIP records the
actual final build's test totals and security results. A publisher certificate
and physical-device validation remain separate limitations.
