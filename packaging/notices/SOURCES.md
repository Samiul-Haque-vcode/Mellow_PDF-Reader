# Corresponding sources and replacement libraries — Windows 1.0.0

Mellow uses dynamically loaded LGPL 3 Qt, PySide and Shiboken libraries. Mellow's
MIT terms do not restrict studying, modifying or replacing these libraries, or
reverse engineering needed to debug such modifications. The complete LGPL 3
and GPL 3 texts accompany this file. No activation key, device authorization or
signature check is imposed on replacement libraries.

## Exact source versions

`SOURCE-ARCHIVES.json` records the original source URLs, byte counts and verified
SHA-256 hashes. The matching archives are provided separately with the Windows
release at:

https://github.com/Samiul-Haque-vcode/Mellow_PDF-Reader/releases/tag/v1.0.0

These optional source downloads are separate from the installer and portable
reader. The public release keeps its original source tag; the explicitly named
MellowPDFReader-1.0.0-Source.zip contains the matching packaging commit for these
Windows packages. BUILD.json records that commit. Original upstream archive URLs
remain in SOURCE-ARCHIVES.json as additional access paths.

| Distributed component | Corresponding source |
| --- | --- |
| Qt Core, GUI, Widgets, Network, Windows platform/style/TLS plugins | qtbase 6.12.0 |
| Qt SVG and SVG icon/image plugins | qtsvg 6.12.0 |
| Additional Qt image plugins | qtimageformats 6.12.0 |
| Qt PDF / PDF Widgets, embedded PDFium and Chromium support code | Qt SDK qtwebengine source 6.140.0 for Qt 6.12.0; PDF sources and all embedded source trees are included |
| PySide6 Essentials 6.12.0, PySide6 PDF 6.12.0.140, Shiboken6 6.12.0 | pyside-setup v6.12.0 |

The Qt maintainers explicitly confirmed the binding source tag and compatible
limited-API rebuild approach in PYSIDE-3485 (26–27 October 2026):
https://qt-project.atlassian.net/browse/PYSIDE-3485

The PDF source archive is from the Qt SDK extension repository, not the older
Qt 6.12 submodule release directory. Its SDK package is
`extensions.qtwebengine.6120.61400.src`, version `6.12.0-0-202609281005`.
The wheel's PDF version suffix `.140` corresponds to this separate 6.140.0
PDF/WebEngine source release. PDFium sources and third-party notices are in
`src/3rdparty/chromium/third_party/pdfium/` in that archive.

## Build and install compatible replacements

Use Windows x64, MSVC 2022's x64 toolchain, CMake and Ninja, with Qt's documented
build prerequisites. The observed wheel runtime identifies itself as:

```
Qt 6.12.0 (x86_64-little_endian-llp64 shared (dynamic) release build; by MSVC 2022)
Python limited API run time: 3.14.10 built: 3.14.3
```

A compatible rebuild need not be byte-identical. Preserve the architecture,
Qt 6.12 ABI, module names and Python limited ABI. Unpack the verified archives
into separate source directories. Build/install qtbase in a separate build
folder using its `configure.bat -prefix C:\Qt\mellow -release -shared
-opensource -confirm-license -nomake tests -nomake examples`, then
`cmake --build . --parallel` and `cmake --install .`.

For qtsvg and qtimageformats, configure their sources from separate build folders
with `C:\Qt\mellow\bin\qt-configure-module.bat <source-folder>`, then build and
install with CMake. Configure the Qt PDF/WebEngine source with the same Qt prefix
and enable PDF/PDF Widgets. WebEngine/browser modules are not used by Mellow and
need not be distributed. Follow the source archive's configuration checks and
install all prerequisites reported by the Qt PDF build. See:

- https://doc.qt.io/qt-6/windows-building.html
- https://doc.qt.io/qt-6/qtwebengine-platform-notes.html
- https://doc.qt.io/qt-6/qtpdf-index.html

Build PySide/Shiboken from pyside-setup v6.12.0 using that Qt SDK, Python 3.14 x64,
and `--limited-api=yes`. Include Core, Gui, Widgets, Network, Svg, Pdf and
PdfWidgets in the module subset. Follow the upstream build instructions for
Shiboken/Clang and the supported `setup.py bdist_wheel` or CMake route:
https://doc.qt.io/qtforpython-6/building_from_source/index.html

To test modifications, make a copy of the portable reader, close it, and replace
the compatible Qt DLLs, plugins, PySide bindings and Shiboken runtime under
`_internal/PySide6` and `_internal/shiboken6` as appropriate. Preserve plugin
subdirectories and dependent DLLs. Restart that copy and check PDF rendering,
search, selection, splits and image conversion. Keep the original portable copy
for recovery. Alternatively rebuild Mellow with your replacement wheels and
`packaging/windows.ps1`. Source and build scripts are included in the matching
Mellow source ZIP. Mellow uses PyInstaller onedir, not static Qt linking.

The supplied application does not use Mesa/OpenGL software rendering, Qt Quick or
WebEngine. Its Windows package keeps native Schannel TLS and Python's SSL runtime;
the unused Qt OpenSSL backend and its separate libraries are removed only after
checking imports. No source modifications were made to Qt/PySide/Shiboken.

## Other native components

Python 3.14.10 source: https://www.python.org/ftp/python/3.14.10/Python-3.14.10.tar.xz
Its PSF license and incorporated third-party terms are in `upstream/`.
The installed wheel notices cover NumPy and its bundled BLAS/runtime libraries,
pypdf, charset-normalizer and the PyInstaller bootloader exception. See
DEPENDENCIES.json for the actual versions and REVIEW.json for per-library notice
mappings. Windows system/Visual C++ runtimes retain Microsoft's separate terms;
they are not offered under Mellow's MIT or Qt's LGPL licenses.
