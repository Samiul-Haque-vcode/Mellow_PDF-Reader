# Validation — 0.0.3

Checked on 25 October 2026: Linux x86_64, Python 3.12, PySide6/Qt 6.12, offscreen Qt, pypdf 6.21.2.

- Full final suite: **647 passed, 1 Windows-only skip, 1 existing Qt enum deprecation warning in 352.96 seconds**.
- Security/reading/backup preflight: **66 passed in 19.25 seconds**, overlapping the full suite.
- Source smoke exited zero: actual PDF rendering, tool previews and metadata backup restoration.
- App, Windows version resource and installer version are **0.0.3**. Workflow remains manual-only and source push uses `[skip ci]`.

## Security results

Runtime dependency auditing initially found three known denial-of-service advisories in pypdf 6.21.1. Minimum requirements, the tested Linux lock and the test environment were upgraded to **6.21.2**. A repeat pip-audit query of eight installed runtime packages reported **zero known advisories, zero skips**. Native Qt/PDFium components are not fully covered by a Python package advisory lookup.

Bandit parsed all application/packaging Python files without errors and reported **5 medium / 91 low findings**. Reviewed SQL findings use constant/whitelisted identifiers and bound values. Remaining low warnings concern assertions in diagnostic checks and argument-list subprocess/build helpers. These are reviewed warnings, not a scanner clean bill; see [SECURITY.md](SECURITY.md) for scope and details.

New regressions cover blocked URL schemes, email attachments/control characters, URL credentials, actual safe/blocked PDF link clicks, malformed/oversized Favorites, atomic import rejection and fail-closed Windows directory lookup. Existing reader, selection, split, history, rendering, tool, backup and session tests remain.

A preliminary regression run was stopped when the vulnerable dependency was discovered. Only the completed run against pypdf 6.21.2 is counted above. Audit tools and temporary reports were kept outside application dependencies and repository contents.

## Limits

No new native Windows build, installed-app test, Defender scan, certificate signature or release was performed. The Windows API launch path has unit coverage; actual native verification remains separate. Rebuild the application to apply these source/dependency fixes to an installed copy.

Text extraction, reference matching and color preservation retain their documented limitations. Physical touchpad, mixed-DPI, GPU/fullscreen, Snap and accessibility validation remain separate; see [Windows validation](docs/windows-validation.md). Review binary-distribution obligations in [THIRD_PARTY.md](THIRD_PARTY.md).
