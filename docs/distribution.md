# Windows distribution

The [1.0.0 release](https://github.com/Samiul-Haque-vcode/Mellow_PDF-Reader/releases/tag/v1.0.0)
contains a Windows x64 installer, portable ZIP, matching Mellow source ZIP,
verification ZIP and SHA-256 checksums. The separate Qt/PySide archives are
corresponding library sources; normal installation does not require them.

## Local build

Install Python **3.14.10 x64** for the reviewed release and **Inno Setup 6**.
From the repository root, run:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows.ps1
```

The script creates its environment, installs pinned dependencies, runs tests,
builds with PyInstaller, prunes unused components, collects notices, tests the
frozen reader, compiles the installer and records verification evidence.

| Output | Contents |
| --- | --- |
| `dist/MellowPDFReader/` | Executable with its required adjacent libraries and notices. |
| `dist/MellowPDFReader-Setup.exe` | Windows installer. |
| `dist/build-verification/` | File hashes, build versions, signature status and available Defender results. |

Keep the application folder intact. The reviewed attribution record is specific
to Python, architecture, package versions and native-file hashes. Changing those
requires a new review; a local build alone does not authorize redistributing
unreviewed dependency binaries.

## Distribution gate and signing

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows.ps1 -DistributionReady
```

This requires complete recorded notice evidence and a successful available Defender
scan. The exact native-library review for the published build is complete; see
[THIRD_PARTY.md](../THIRD_PARTY.md) and [the source/build guide](../packaging/notices/SOURCES.md).
Future dependency upgrades must update that evidence rather than bypass its checks.

Builds are unsigned unless an existing trusted signing identity is supplied with
`-CertificateThumbprint`. Version-resource publisher text is not a certificate.
See [SECURITY.md](../SECURITY.md); never disable Windows protections to install.

## Portable mode and saved data

A portable package includes `portable.ini` beside the executable and stores small
metadata in `mellow-data` beside it. Keep that marker in the portable folder.
The installed app normally uses `%LOCALAPPDATA%\Mellow\Mellow PDF Reader`.
Back up metadata to a separate location before uninstalling. Updating an existing
installation preserves it; uninstalling removes that Windows user's Mellow data,
while original PDFs and external backups are preserved.

## Release process

The dedicated `windows-release.yml` workflow requires the full Windows suite,
native controls, frozen/installed/portable rendering, notice checks, installer
registration and uninstall checks, Defender scan and verified source archives.
It uploads directly to Releases without Actions artifacts. Diagnostic artifact
uploads in `windows.yml` are opt-in and consume Actions storage.

The original public `v1.0.0` source tag is retained. Use the explicitly named
`MellowPDFReader-1.0.0-Source.zip` for packaging materials matching the published
Windows build. GitHub's automatic tag archives refer to the earlier source-only
commit. BUILD.json identifies the actual binary build commit; the current main
branch also contains later publishing-script fixes and documentation updates.

The [validation record](../VALIDATION.md) distinguishes the 723-test build,
publishing-script follow-up, signatures and physical-device limits. Consult the
[release checklist](release-checklist.md) before another distribution.
