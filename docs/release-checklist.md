# Windows binary distribution checklist

The 1.0.0 source release is published. Its Windows build passed 679 tests,
packaged rendering, install/uninstall checks and the available Defender scan.
That binary was unsigned and was not published because attribution review
was incomplete. The source release tag is unchanged by this follow-up work.

## Dependency notices — completed review

The [Windows inventory run](https://github.com/Samiul-Haque-vcode/Mellow_PDF-Reader/actions/runs/40929960790)
passed **51 focused checks**, frozen real-PDF/tool rendering and the exact-version
attribution gate. It matched **132 native files**, **64 hashed evidence files**
and **seven packages**, with no collection issues. This is a recorded maintainer
review with reproducible checks, not legal or security certification.

| Check | Evidence |
| --- | --- |
| Qt PDF source match | Verified Qt SDK PDF/WebEngine 6.140.0 source archive for Qt 6.12.0, binding source tag confirmed by Qt maintainers in PYSIDE-3485. |
| Qt runtime notices | Source copyright headers, module attribution metadata and complete referenced licenses, alongside LGPL 3/GPL 3 texts. |
| Native-library notices | Individual DLL/Python-extension mappings to hashed Python, NumPy, charset-normalizer, Qt and Microsoft notice materials. |
| Corresponding source access | Pinned complete source archives, directly published as optional release assets before executables; build/replacement instructions in SOURCES.md. |

`packaging/notices/REVIEW.json` records exact package versions, Python, platform,
architecture, native hashes, evidence hashes, four review checks, package-notice
mappings and **native_licenses** mappings for every native file. Any missing or
changed library, source evidence or dependency version blocks the strict gate.
No cross-platform or automatically regenerated review is accepted as equivalent.

For the reviewed Windows candidate, run:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows.ps1 -DistributionReady
```

The script pins reviewed dependency versions, rejects incomplete notices and
requires a successful available Defender scan. The dedicated Windows distribution
workflow also runs the full regression suite, native GUI checks, frozen and
portable rendering, installer/registry/uninstaller checks and personal-data cleanup.
It uploads directly to the existing 1.0.0 release, without Actions artifacts.

The public source tag remains unchanged. The explicitly named Source ZIP matches
the build commit in BUILD.json; GitHub's automatic tag archives retain the original
source-release commit. Separate library sources have verified SHA-256 checksums.

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
