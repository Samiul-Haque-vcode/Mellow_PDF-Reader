# Mellow documentation

Mellow 1.0.0 is available as a Windows installer and portable download. Start with
[the project README](../README.md) or [the release downloads](https://github.com/Samiul-Haque-vcode/Mellow_PDF-Reader/releases/tag/v1.0.0).

## Reading and settings

- [User guide](user-guide.md): layouts, split reading, saved places, themes, tools and data.
- [Keyboard shortcuts](user-guide.md#default-keyboard-shortcuts): default bindings and customization.

## Development

- [Architecture](architecture.md): modules and data boundaries.
- [Development setup](development.md): Python environment, tests and workflow behavior.
- [Contributing](../CONTRIBUTING.md): issues and pull requests.
- [Changelog](../CHANGELOG.md): notable changes, separated from test evidence.

## Packaging and verification

- [Windows distribution](distribution.md): installer, portable mode and build outputs.
- [Release checklist](release-checklist.md): dependency review, signing and physical checks.
- [Windows device checklist](windows-validation.md): DPI, touchpad, transitions and accessibility.
- [Validation record](../VALIDATION.md): measured results and remaining limitations.
- [Security](../SECURITY.md): reporting, file handling, signatures and scan limits.
- [Third-party terms](../THIRD_PARTY.md): licenses and the reviewed native inventory.
- [Corresponding sources](../packaging/notices/SOURCES.md): source archives and library replacement.

The published Windows build passed 723 tests. The later publishing-script fix
passed its own 16-test Windows verification. These are recorded results for their
respective commits, not a claim that every later change has rerun the full suite.
