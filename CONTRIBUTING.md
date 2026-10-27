# Contributing to Mellow PDF Reader

Thanks for helping improve Mellow. The project aims to be **small, local-first, PDF-only, and comfortable to read in**. Please keep those constraints in mind when suggesting features or changing interfaces.

## Before opening an issue

Search existing issues and pull requests first. Use the issue forms for **bugs** or **feature requests** and include only information needed to reproduce or understand the problem. When reporting a bug, provide app/source version, Windows version, expected behavior, actual behavior, and reproduction steps. Attach a non-sensitive sample PDF only if you have permission to share it.

**Security-sensitive concerns:** Do not publish exploit details, suspicious PDFs, or private data in a public issue. Read [SECURITY.md](SECURITY.md) first and request a private contact route without posting sensitive specifics if no private reporting channel is offered.

## Development and pull requests

1. Start from the current default branch and work on a descriptive feature branch.
2. Read [architecture](docs/architecture.md) and [development setup](docs/development.md).
3. Make focused changes; keep existing shortcuts, reading preferences, and data compatibility in mind.
4. Add or update regression tests for code behavior changes.
5. Run the relevant tests and describe what **you actually ran**. If Windows hardware or installer validation was not performed, say so.
6. Open a pull request explaining why the change is useful, what files it changes, and any compatibility/security implications.

Documentation-only changes do not need to claim a full application test run. For changes to installation, signing, metadata handling, or third-party dependencies, review [distribution](docs/distribution.md), [security](SECURITY.md), and [third-party notes](THIRD_PARTY.md).

## Style and scope

Prefer clear module responsibilities, predictable interactions, and simple controls over accumulating menus or permanent panels. Avoid adding cloud services, OCR, Markdown/ebook support, AI features, or annotation authoring without an explicit product-scope decision.

The source is [MIT licensed](LICENSE), but dependencies retain their own terms.
