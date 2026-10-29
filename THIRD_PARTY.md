# Dependencies and redistribution

Mellow PDF Reader's own code is [MIT-licensed](LICENSE). Dependencies retain
their respective licenses; the app's MIT grant does not relicense those libraries.

| Component | Terms and included materials |
| --- | --- |
| Qt / PySide / Shiboken | LGPL 3 option for the dynamically loaded components, with LGPL 3/GPL 3 texts, source copyright headers and Qt module attribution files. |
| Qt PDF / embedded PDFium | Qt PDF LGPL 3 plus PDFium/Chromium and incorporated third-party licenses. Nine Qt PDF notice snapshots and supplemental source notices are included. |
| Python 3.14.10 | PSF license and incorporated-software notices, including its native parsing, compression and SSL libraries. |
| NumPy | BSD-3-Clause plus the Windows wheel's BLAS, LAPACK and compiler-runtime notices. |
| pypdf | BSD-3-Clause. |
| charset-normalizer | MIT; included when its optional native extensions are bundled. |
| PyInstaller bootloader | GPL with its bootloader exception, allowing the reader to retain its own license. |
| Microsoft Windows / Visual C++ runtimes | Separate Microsoft terms and redistribution conditions; not MIT/LGPL components. |

## Notices and corresponding sources

The installed `licenses/` folder contains the complete collected texts, provenance,
exact package inventory and recorded native-file review. Source copies live in
[packaging/notices](packaging/notices). Original upstream notice text is preserved,
including its line endings; commercial-license reference files alone are not
counted as LGPL notices.

The corresponding Qt, PySide and Shiboken source archives are pinned by URL,
size and SHA-256 in [SOURCE-ARCHIVES.json](packaging/notices/SOURCE-ARCHIVES.json).
The release workflow publishes these archives as separate optional assets before
publishing executables. They are not embedded in the installer or committed as
large archives to this repository. See [SOURCES.md](packaging/notices/SOURCES.md)
for exact versions, the Qt maintainer's binding-source confirmation, build
instructions and compatible-library replacement.

Qt/PySide/Shiboken remain separate shared libraries in the onedir package. Users
may modify or replace compatible LGPL libraries and reverse engineer as needed to
debug those modifications. Mellow imposes no replacement-library signature check.
The PDF source is the Qt SDK 6.140.0 extension archive for Qt 6.12.0, not an assumed
match based solely on documentation version numbers.

## Distribution checks

`python packaging/collect_notices.py dist/MellowPDFReader --require-complete`
checks the actual package versions, Windows/Python architecture, every native-file
hash and all recorded evidence hashes against `REVIEW.json`. Each bundled native
library must have a nonempty mapping to hashed license evidence. Missing, changed
or unreviewed components block release. A manifest records the review work; it
does not perform legal analysis or establish compliance merely by existing.

The package excludes unused Qt Addons/WebEngine Python wheels, Pillow, reportlab,
pytest and the optional Mesa renderer. An unused Qt OpenSSL plugin and its second
SSL build are removed only after import-table checks. Windows Schannel and
Python's current SSL libraries remain. The reader uses CPU PDF raster rendering.

Build verification separately fingerprints the main executable, installer and
all other distributed files. The release workflow requires passing Windows tests,
packaged-PDF checks, install/uninstall checks and an available successful Defender
scan. Publisher signing is optional and distinct from dependency attribution.
See the [release checklist](docs/release-checklist.md).

## Acknowledgments

This software is based in part on the work of the Independent JPEG Group.

Portions of this software are copyright © 2026 The FreeType Project
(www.freetype.org). All rights reserved.

Complete copyright notices and applicable conditions accompany their respective
components in `licenses/`; these acknowledgments do not replace those texts.
