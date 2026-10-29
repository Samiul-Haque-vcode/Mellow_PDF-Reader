# Development guide

## Environment

Use Windows 10/11 x64 and Python **3.14.10 or newer 3.14.x, 64-bit**, with Git
and PowerShell. Inno Setup 6 is needed only to build an installer. The reviewed
1.0.0 Windows distribution uses exactly Python 3.14.10; its attribution manifest
must be reviewed again when Python or bundled libraries change.

```powershell
git clone https://github.com/Samiul-Haque-vcode/Mellow_PDF-Reader.git
cd Mellow_PDF-Reader
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c packaging/windows-release-constraints.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe run_mellow.py
```

For reading from source without development tools, install `requirements.txt`
instead. Setup downloads dependencies; normal reading operates offline.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q tests/test_reader.py
```

Tests generate real PDFs and use Qt PDF rendering, including the offscreen
platform where appropriate. Linux offscreen results do not establish Linux
desktop support or replace physical Windows checks. Record commands, platform,
commit and actual results; see [VALIDATION.md](../VALIDATION.md).

Keep changes focused and preserve settings, saved positions and output-file
safety. Add regression coverage appropriate to a behavior change. Documentation
changes need link, accuracy and template checks rather than claiming new app tests.
See [architecture](architecture.md) and [contributing](../CONTRIBUTING.md).

## GitHub Actions

Ordinary documentation changes do not build the app. The workflows have explicit
path and commit-marker guards, plus manual dispatch where supported:

| Workflow | Purpose |
| --- | --- |
| `windows.yml` | Windows build diagnostics; optional artifact uploads are off by default. Its legacy source-publication option is separate from binary distribution. |
| `windows-release.yml` | Build/test/scan and publish the reviewed 1.0.0 downloads directly to Releases. |
| `distribution-audit.yml` | Inventory actual frozen libraries and their notices, without artifact uploads. |
| `release-verification.yml` | Read-only verification of published hashes, sources and build evidence. |

Read each workflow's trigger before changing it. The binary distribution workflow
publishes corresponding sources before executables. Its download storage is
separate from Actions artifact storage. Never represent missing scans, unsigned
builds or historical test results as newly verified results.
