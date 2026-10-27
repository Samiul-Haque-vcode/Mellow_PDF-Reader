# Development guide

## Prerequisites

- Windows 10/11 x64 and **Python 3.12 x64** for the documented interactive development workflow.
- Git and PowerShell.
- Optional: **Inno Setup 6** for creating a Windows installer.

A number of Qt regression tests have also been run headlessly on Linux; this does **not** establish Linux desktop support or replace physical Windows tests.

## Setup and launch (PowerShell)

```powershell
git clone https://github.com/Samiul-Haque-vcode/Mellow_PDF-Reader.git
cd Mellow_PDF-Reader
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe run_mellow.py
```

`requirements-dev.txt` includes runtime packages plus pytest, reportlab, and PyInstaller. For reading-only execution, `requirements.txt` is sufficient.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests are in `tests/`; several generate real PDFs and exercise real Qt PDF rendering using the offscreen platform where appropriate. Relevant focused tests can be run by file:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_reader.py
```

For historical measured results and the precise platform/version used, refer to [VALIDATION.md](../VALIDATION.md). Do not report those historical results as new tests for a changed commit.

## Code and pull requests

1. Keep Mellow **PDF-only** and preserve reading-first interaction (no permanent panels by default).
2. Put functionality in the relevant `mellow/` module; avoid indiscriminate changes to `mellow/app.py`.
3. Add or update tests under `tests/` for behavioral fixes.
4. Review privacy, export safety, untrusted PDF input, file overwrite handling, and keyboard/navigation behavior for relevant changes.
5. If changes affect binaries, packaging, licensing, or security, update the applicable documentation and validation record.

See [architecture](architecture.md), [CONTRIBUTING.md](../CONTRIBUTING.md), and [security review](../SECURITY.md).

## GitHub Actions

The repository's `.github/workflows/windows.yml` is **workflow_dispatch only**. Pushes and pull requests do **not** automatically invoke it. The workflow can run Windows tests and build the executable, installer, and portable folder; artifact uploads are **disabled by default** and are enabled with the manual `upload_artifacts` input.

A successful source-level test does not mean an executable was signed, distributed, or validated on physical Windows hardware. See [distribution](distribution.md) and [Windows validation](windows-validation.md).
