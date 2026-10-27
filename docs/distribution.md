# Windows packaging and release checks

This is the documented **build process**, not an announcement that a tested public installer exists. Source version **0.0.5** has no newly compiled installer or executable included in the repository.

## Local Windows build

Install Python **3.12 x64** and **Inno Setup 6**, then run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows.ps1
```

The build script creates its environment, installs developer dependencies, runs tests, bundles Mellow using PyInstaller, collects notices, smoke-tests the result, creates an Inno Setup installer, and writes build-verification records.

Expected local output paths:

- `dist/MellowPDFReader/MellowPDFReader.exe` — executable inside its dependency folder.
- `dist/MellowPDFReader-Setup.exe` — Windows installer.
- `dist/build-verification/` — available hashes, signature details, and scan observations.

**Do not separate** the executable from the adjacent bundled dependency files.

## Portable mode

The GitHub Windows workflow also creates a portable folder and adds `portable.ini` beside the executable. With that marker, metadata is kept in a sibling `mellow-data` directory.

## Signing and verification

Without a signing certificate, local builds are **unsigned**. Windows SmartScreen warnings about publisher reputation are not the same as a named antivirus detection; do not ask users to disable protection.

If you already have a trusted code-signing identity in the current user's Windows certificate store and appropriate signing tools, the packaging script accepts `-CertificateThumbprint`. Details, signature checks, and scanner limitations are in [SECURITY.md](../SECURITY.md). A reported hash establishes identity of bytes, not safety.

## Before distributing binaries

- [ ] Review the **exact bundled Qt/PDFium third-party attribution** and license obligations described in [THIRD_PARTY.md](../THIRD_PARTY.md). This review is currently outstanding.
- [ ] Build from the intended commit and record the app version and artifact hashes.
- [ ] Run relevant automated tests and packaged smoke checks; record new results with correct version/platform in [VALIDATION.md](../VALIDATION.md).
- [ ] Perform the manual [Windows validation matrix](windows-validation.md) on the targeted devices, including install/uninstall, DPI, input and accessibility.
- [ ] Assess Windows security checks and signing status without presenting an unsigned build as trusted.
- [ ] Only then publish release artifacts and release notes, with limitations clearly stated.

## GitHub workflow

`.github/workflows/windows.yml` runs **on manual dispatch only**; it does not publish a GitHub Release. Artifact upload is opt-in and artifacts have short retention. To distribute a real version, treat manual release creation and the checks above as separate steps.

Further reading: [source development](development.md), [validation history](../VALIDATION.md), [security](../SECURITY.md), [third-party terms](../THIRD_PARTY.md).
