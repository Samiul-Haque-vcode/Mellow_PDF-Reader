# Windows binary distribution checklist

The 1.0.0 source release is published. Its Windows build passed 679 tests,
packaged rendering, install/uninstall checks and the available Defender scan.
That binary was unsigned and was not published because attribution review
was incomplete. The source release tag is unchanged by this follow-up work.

## Dependency notices — remaining work

Nine Qt PDF 6.140.0 license-text snapshots are now stored in
`packaging/notices/qt-pdf-6.140.0/`. The adjacent manifest records provenance,
versions and SHA-256 hashes. This covers collected upstream text, not proof
of the exact wheel build's source provenance or the whole app's dependencies.

Complete these four checks against the actual Windows onedir build:

| Check key | Evidence to collect |
| --- | --- |
| `qt_pdf_source_match` | Exact Qt PDF/PDFium/Chromium source revisions and build configuration corresponding to the shipped wheel, including third-party notices. Current documentation version alone is insufficient. |
| `qt_runtime_notices` | Qt/PySide/Shiboken copyright and license materials, plus third-party terms for the Qt modules actually shipped. |
| `native_library_notices` | Notices for every bundled native dependency, including Python, NumPy's bundled libraries, image/font/compression libraries and the PyInstaller bootloader. |
| `lgpl_source_access` | Corresponding source access and required build/install information for LGPL components under the chosen distribution method. Preserve compatible library replacement and permitted reverse engineering. General upstream links alone do not establish this check. |

Run `python packaging/collect_notices.py dist/MellowPDFReader`. Its
`licenses/DEPENDENCIES.json` lists package versions, missing notices and actual
bundled native library/helper-file hashes. The main Mellow executable is excluded
from this mapping because signing changes its bytes; the build verification
manifest fingerprints it separately. This is an inventory, not a completed review.

After doing the review, store `packaging/notices/REVIEW.json` with:

- `format`: integer `1`.
- `python`, `platform`, `architecture`: the build's exact Python version,
  `sys.platform` and `platform.machine()`.
- `package_versions`: every inventory package name mapped to its exact version.
- `native_files`: the inventory's full relative-file-to-SHA-256 mapping.
- `files`: relative license/evidence paths mapped to SHA-256, including required
  source-access documentation. Keep extra reviewed evidence in `packaging/notices/`.
- `checks`: each of the four keys above mapped to an object with `complete: true`
  and a nonempty `evidence` list naming hashed entries in `files`.
- `package_notices`: every inventory package mapped to a nonempty list of its
  notice paths, also registered in `files`.

Do not create a record just to bypass the check. It records completed maintainer
work; matching hashes do not independently establish license compliance.
Any changed native file, package version, platform or evidence invalidates it.
Do not reuse a Linux review for Windows.

For a distribution candidate, run:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows.ps1 -DistributionReady
```

This rejects incomplete notice/review evidence and requires a successful Defender
scan. Requested GitHub binary artifact uploads also run the strict notice check.
Ordinary local builds remain available for testing. Pushes with `[skip ci]` do
not run Actions. No binary release is enabled by adding the notice snapshots.

## Publisher signing — optional identity step

A trusted signing identity is not required to build an unsigned application.
It helps Windows identify the publisher; unsigned binaries can show reputation
warnings. A newly signed binary can still receive SmartScreen warnings.

Obtain a publicly trusted code-signing identity from a suitable certificate
provider or signing service, complete its identity verification and retain the
private key in its supported secure store. Do not upload private keys, tokens,
PFX files or recovery secrets to this repository or chat.

The existing build script supports Windows certificate-store signing:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows.ps1 -DistributionReady -CertificateThumbprint YOUR_CERTIFICATE_THUMBPRINT
```

It signs and timestamps the executable and installer, verifies both signatures,
and stops on failures. A signing service with a different interface requires a
separate integration. No publisher identity has been configured here.

## Physical Windows checks

Use [windows-validation.md](windows-validation.md) on Windows 10/11, including
100%, 125%, 150% and 200% scaling, a touchpad and mixed-DPI monitors where available.
Record the build commit, hardware, OS/display setup and steps for any glitch.
Fix reproduced failures and rerun those cases. Automated runner tests are useful
evidence but do not substitute for this device matrix.

## Reader limitations

Scanned pages require OCR for text search/selection; OCR remains outside Mellow's
scope. Complex-layout extraction and heuristic reference matching use the existing
manual fallbacks. Keep these limitations visible rather than promising lossless
extraction or adding cloud/AI dependencies to the reader.
