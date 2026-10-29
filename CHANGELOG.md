# Changelog

Notable changes are listed here. Exact test results, build commits and review
limits are recorded in [VALIDATION.md](VALIDATION.md).

## 1.0.0

- Refreshed the app, Windows icon, installer and README with the approved curved
  open-book artwork and transparent corners.

- Published Windows x64 installer and portable downloads, matching source,
  verification reports and separate corresponding library sources.
- Fixed numeric/scroll boundary handling and unsafe oversized/non-finite metadata inputs.
- Updated the PDF dependency baseline and Windows Python runtime.
- Completed version-specific Qt/PDFium and native-library notice review.
- Removed unused packaged components and added guards against unreviewed native files.
- Fixed legacy-Windows-encoding cases in release-file reading and GitHub CLI responses.
- Consolidated the documentation guides and contribution templates on main.

The refreshed logo build passed **734 Windows tests**, packaged/installed/portable
checks and the available Defender scan. Published hashes and embedded Windows
icons were verified. Earlier build results and their exact commits remain in
[VALIDATION.md](VALIDATION.md). Builds remain unsigned; physical-device validation
has documented gaps.

## Earlier source updates

### 0.0.5

Page previews changed to two adaptive sizes: Small (three columns) and Large
(two columns), with popup resizing and scrolling improvements.

### 0.0.4

Strengthened PDF-link handling, metadata import validation, saved-position bounds
and atomic metadata exports, and updated pypdf in response to disclosed advisories.

See [repository history](https://github.com/Samiul-Haque-vcode/Mellow_PDF-Reader/commits/main)
for individual changes. Older source-only publications do not describe the
availability or verification of the later 1.0.0 Windows downloads.
