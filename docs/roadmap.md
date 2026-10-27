# Project roadmap and readiness

This page records **outstanding work**, separate from what the repository currently implements. It is not a promise of release dates or a claim that proposed work is already shipped.

## Current baseline

- **Source version:** 0.0.5.
- **Target:** Windows 10/11 x64, local-first, PDF-only reader.
- **Core implementation:** tabs, optional split reading, themes, bookmarks/Favorites, PDF navigation/search, session restore, and three basic PDF utilities.
- **Release status:** the repository is currently a source publication, with no newly compiled 0.0.5 Windows installer or executable bundled.
- **Evidence:** 0.0.5-focused verification and earlier 0.0.4 full-suite results are documented separately in [VALIDATION.md](../VALIDATION.md).

## Next priorities

| Priority | Work | Definition of done |
| --- | --- | --- |
| 1 — Distribution compliance | Resolve version-specific Qt/PDFium notices and redistribution obligations. | Exact dependencies and corresponding required notices are reviewed and included. |
| 1 — Windows validation | Execute the [physical Windows validation checklist](windows-validation.md). | Results are recorded against actual devices, OS versions, and build hashes; remaining issues are tracked. |
| 1 — Build trust | Produce and check a Windows build with accurate signing/Defender records. | Artifact identity and any limitations are published without overstating safety. |
| 2 — Public release readiness | Prepare usable downloads only after the checks above. | Release notes, downloads, install/uninstall results and source revision match. |
| 2 — Ongoing quality | Keep documentation, regression tests, and accessibility findings aligned with code changes. | Each material change has appropriate review/tests and updated guidance. |

## Out of scope unless deliberately reconsidered

Mellow remains a focused **PDF reader**, not an EPUB/Markdown reader, OCR tool, cloud document manager, AI service, or full PDF editing suite.

For new proposals, use a [feature request](../.github/ISSUE_TEMPLATE/feature_request.yml) and explain how it preserves the simple reading experience. Track individual bugs/features in GitHub Issues rather than declaring them implemented here.
