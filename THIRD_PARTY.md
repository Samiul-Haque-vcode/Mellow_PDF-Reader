# Dependency and distribution notes

Mellow PDF Reader's own source is licensed under [MIT](LICENSE). This grant does
not replace the licenses of Qt, PySide6, PDFium, Python or other dependencies.

| Component | Terms / distribution approach |
| --- | --- |
| Python | PSF license and included third-party terms; collect the installed interpreter's LICENSE.txt. |
| Qt / PySide6 / Shiboken | LGPL/GPL/commercial choices vary by component. Mellow uses the LGPL option for its dynamically loaded Qt components and includes LGPL 3 and GPL 3 texts. |
| PDFium / Chromium components in Qt PDF | BSD-family and additional third-party terms. Review the notices for the exact Qt PDF build. |
| NumPy | BSD-3-Clause plus bundled native-library notices included by its wheel. |
| pypdf | BSD-3-Clause. |
| PyInstaller bootloader | GPL with its bootloader exception; the exception permits distributing an application under its own license. Include its actual installed notices. |

`python packaging/collect_notices.py dist/MellowPDFReader` copies the source MIT
license, this document, available installed-package notices and the Python
license beside the app. `licenses/DEPENDENCIES.json` records exact versions,
source URLs, copied notice paths and gaps, including a missing Python notice.
The build verification manifest independently records installed package versions
and hashes every bundled file. The collector runs at build time, without network
access; the reader does not download licenses or depend on a server.

Keep Qt DLLs/shared libraries separate from the executable. Do not prohibit
reverse engineering needed to debug modifications to LGPL libraries. Users may
replace the dynamically loaded libraries with compatible builds. Source and build
instructions are at [Qt for Python](https://doc.qt.io/qtforpython-6/building_from_source/index.html)
and [Qt PDF licensing](https://doc.qt.io/qt-6/qtpdf-licensing.html).
Include the corresponding library source or a license-compliant source offer
when the chosen distribution method requires it; general upstream links alone
are not represented as fulfilling every LGPL redistribution obligation.

The development wheels lack the complete attribution materials. Nine upstream Qt
PDF 6.140.0 notices have now been collected in `packaging/notices/qt-pdf-6.140.0/`.
`qt-pdf-manifest.json` records their documentation URLs, versions and hashes. The
collector checks the snapshot against the installed PySide6_Pdf version and
verifies file integrity. A documentation-version match does not establish the
wheel's exact source revisions.

Binary redistribution still needs four completed checks: exact Qt PDF source
matching, Qt runtime notices, all bundled native-library notices, and LGPL
corresponding-source access. See [the release checklist](docs/release-checklist.md)
for evidence requirements and the REVIEW.json format. The collector verifies the
recorded package versions, platform, Python, native-file inventory and evidence
hashes, then reports specific gaps. It does not perform the legal review itself.

Use `python packaging/collect_notices.py dist/MellowPDFReader --require-complete`
or `packaging/windows.ps1 -DistributionReady` to reject incomplete evidence.
GitHub binary artifact uploads also require this check. The 1.0.0 release remains
source-only; no installer is published by this follow-up change. Application MIT
licensing, matching evidence and passed malware checks do not independently
resolve redistribution obligations. Trusted publisher signing is a separate,
optional identity step and is not the attribution blocker.
