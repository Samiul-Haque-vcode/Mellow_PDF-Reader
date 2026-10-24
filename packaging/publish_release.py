"""Publish a tested Windows preview; keep downloads outside Actions storage."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate(root, commit):
    """Refuse failed tests, absent scans, or bytes changed since verification."""
    tree = ET.parse(root / 'test-results.xml')
    suites = list(tree.iter('testsuite'))
    if not suites or sum(int(s.get('tests', 0)) for s in suites) == 0:
        raise ValueError('No test results')
    if any(int(s.get(key, 0)) for s in suites for key in ('failures', 'errors')):
        raise ValueError('Windows tests failed')
    security = json.loads((root / 'dist/build-verification/SECURITY.json').read_text())
    if security.get('defender', {}).get('status') != 'NoThreatsReported':
        raise ValueError('A completed Defender scan is required')
    if security.get('changed_or_missing_files') or security.get('signature_error'):
        raise ValueError('Build verification failed')
    manifest = json.loads((root / 'dist/build-verification/BUILD.json').read_text())
    if manifest.get('commit') != commit or not manifest.get('files'):
        raise ValueError('Verification must match this commit')
    for row in manifest['files']:
        path = root / 'dist' / row['path']
        if not path.is_file() or digest(path) != row['sha256']:
            raise ValueError('Build changed after verification: ' + row['path'])
    # The portable package is a copy of the verified app plus one metadata marker.
    app = root / 'dist/MellowPDFReader'
    portable = root / 'dist/MellowPDFReader-Portable'
    source_files = {p.relative_to(app): p for p in app.rglob('*') if p.is_file()}
    copied = {p.relative_to(portable): p for p in portable.rglob('*') if p.is_file()}
    if set(copied) != set(source_files) | {Path('portable.ini')}:
        raise ValueError('Portable package is incomplete')
    for name, path in source_files.items():
        if digest(path) != digest(copied[name]):
            raise ValueError('Portable package differs from the scanned app')
    return sum(int(s.get('tests', 0)) for s in suites), sum(int(s.get('skipped', 0)) for s in suites)


def prepare(root, commit, version):
    tests, skipped = validate(root, commit)
    output = root / 'dist/release'
    output.mkdir(parents=True, exist_ok=True)
    installer = output / f'MellowPDFReader-{version}-Setup.exe'
    shutil.copy2(root / 'dist/MellowPDFReader-Setup.exe', installer)
    portable = output / f'MellowPDFReader-{version}-Portable-x64.zip'
    source = root / 'dist/MellowPDFReader-Portable'
    with zipfile.ZipFile(portable, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob('*')):
            if path.is_file():
                archive.write(path, Path('MellowPDFReader-Portable') / path.relative_to(source))
    assets = [installer, portable]
    for name in ('SECURITY.json', 'BUILD.json'):
        target = output / name
        shutil.copy2(root / 'dist/build-verification' / name, target)
        assets.append(target)
    results = output / 'test-results.xml'
    shutil.copy2(root / 'test-results.xml', results)
    assets.append(results)
    hashes = output / 'SHA256SUMS.txt'
    hashes.write_text(''.join(f'{digest(p)}  {p.name}\n' for p in assets), encoding='utf8')
    assets.append(hashes)
    notes = output / 'release-notes.md'
    notes.write_text(f'''Mellow PDF Reader {version} — Windows 10/11 x64 preview

Download **Setup.exe** for installation, or extract **Portable-x64.zip** and run MellowPDFReader.exe.

Settings is organized into **General, Reading, Appearance and Shortcuts**. Theme selection and tuning are only in **Settings → Appearance**; **Reading Ruler** is in **☰ → Reading**. General holds startup, history, app backups and Favorites import/export. Reading holds new-document layout/zoom defaults, gesture and auto-scroll speed, copy format and ruler appearance. Existing document/session preferences and custom shortcuts are preserved.

**☰ → Reading** adds a pointer-following **Magnifying Lens** (Esc closes), pane-local **Lock Zoom** that blocks every zoom change until unlocked, and **Previous/Next Chapter** using existing outlines, including nested sections. The lens renders a bounded source-PDF region without changing the current reading position. Chapter navigation is disabled when no usable outline exists.

Right-click the PDF page for **Set Quick Jump Here / Return to Quick Jump**, **Select Between Two Points…**, contextual Find Selected Text, Trim Reading Margins and applicable reference previews/navigation. Quick Jump is a temporary reading marker; it is not saved across restarts. For two-point selection, click the starting text, scroll, then click the ending text; choose Copy — Preserve Line Breaks or Copy — Join Paragraphs. Esc cancels selection. No OCR is included.

**Ctrl+A** selects the current page, **Ctrl+Shift+A** selects text across the PDF, and **Ctrl+C** copies using the format chosen in Settings → Reading. The two-point popup always offers both formats. Shortcuts remain configurable and text fields retain normal editing behavior. Larger copies prepare one page at a time with cancellation and publish to the clipboard only when complete; cancelled or superseded jobs cannot overwrite a newer copy.

The main menu keeps Document, Reading, Page Layout, existing PDF Tools, Settings and Credits. Daily controls remain in the compact toolbar; collapsed controls remain available under **More reading controls** at narrow widths. PDF tools also retain their Home launchers. Saving margins or cover preferences preserves the document layout when the global default has changed.

**Settings → General → Backup and restore** remains available. Save preference changes, then create an app backup before uninstalling; restore after reinstalling. PDFs are not included in metadata backups and must be kept separately.

**Uninstall now removes personal data** for the Windows account running the uninstaller: sessions, settings, history, Favorites and personal bookmarks. PDFs and exported backups are preserved, including files in the metadata folder. Installing an update over the existing version preserves saved data. Other Windows profiles and separate portable data are untouched; if elevation uses another account, cleanup targets that account. The installer update/uninstall/reinstall cycle is checked automatically.

Since 0.21.1: clearer Home/settings and saved-location controls; safer moved-file handling; previews that preserve compatible page/zoom positions; improved search excerpts and paragraph copy; clearer reference candidates; keyboard focus and dark-text contrast refinements; coalesced gesture updates, fullscreen shortcut fixes and smaller hidden-view caches.

Windows automation: {tests - skipped} passed, {skipped} skipped; native caption/reading-aid probes, metadata backup roundtrip, frozen-app and installed-app smoke checks, and update/uninstall/reinstall verification passed. Defender reported NoThreatsReported for this build. SHA256SUMS.txt identifies the downloads; detailed build/security reports and test results are attached.

**Unsigned prerelease:** Windows may show SmartScreen warnings. Physical touchpad, mixed-DPI/multi-monitor, accessibility and fullscreen timing validation remain pending. Fullscreen behavior fixes do not establish a Windows latency improvement. Qt/PDFium attribution review remains outstanding; bundled dependency notices describe this limitation. Mellow source uses MIT; dependencies retain their own licenses. This preview retains the repository's existing visibility.

Source commit: {commit}
''', encoding='utf8')
    return assets, notes


def main():
    root = Path(__file__).resolve().parents[1]
    commit = os.environ['GITHUB_SHA']
    repo = os.environ['GITHUB_REPOSITORY']
    version = re.search(r"__version__ = '([^']+)'", (root / 'mellow/__init__.py').read_text())[1]
    assets, notes = prepare(root, commit, version)
    tag = 'v' + version
    # Never replace an existing release or publish before every asset uploads.
    subprocess.run(['gh', 'release', 'create', tag, '--repo', repo, '--target', commit,
                    '--title', f'Mellow PDF Reader {version} (Windows preview)',
                    '--draft', '--prerelease', '--notes-file', str(notes),
                    *map(str, assets)], check=True)
    subprocess.run(['gh', 'release', 'edit', tag, '--repo', repo, '--draft=false'], check=True)


if __name__ == '__main__':
    main()
