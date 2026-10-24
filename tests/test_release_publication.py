"""Release assets must be the same bytes that passed Windows verification."""
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest

spec = importlib.util.spec_from_file_location('publish_release', Path(__file__).resolve().parents[1] / 'packaging/publish_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.fixture
def build(tmp_path):
    dist = tmp_path / 'dist'
    app = dist / 'MellowPDFReader'
    app.mkdir(parents=True)
    (app / 'MellowPDFReader.exe').write_bytes(b'verified application')
    (dist / 'MellowPDFReader-Setup.exe').write_bytes(b'verified installer')
    portable = dist / 'MellowPDFReader-Portable'
    portable.mkdir()
    (portable / 'MellowPDFReader.exe').write_bytes(b'verified application')
    (portable / 'portable.ini').write_text('marker')
    verification = dist / 'build-verification'
    verification.mkdir()
    (verification / 'SECURITY.json').write_text(json.dumps({'defender': {'status': 'NoThreatsReported'}}))
    files = [app / 'MellowPDFReader.exe', dist / 'MellowPDFReader-Setup.exe']
    (verification / 'BUILD.json').write_text(json.dumps({'commit': 'abc', 'files': [
        {'path': p.relative_to(dist).as_posix(), 'sha256': release.digest(p)} for p in files]}))
    (tmp_path / 'test-results.xml').write_text('<testsuites><testsuite tests="10" skipped="1" failures="0" errors="0"/></testsuites>')
    return tmp_path


def test_release_assets_include_scanned_bytes_and_matching_download_hashes(build):
    assets, notes = release.prepare(build, 'abc', '0.27.0')
    archive = next(p for p in assets if p.suffix == '.zip')
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.read('MellowPDFReader-Portable/MellowPDFReader.exe') == b'verified application'
        assert 'MellowPDFReader-Portable/portable.ini' in zipped.namelist()
    hashes = next(p for p in assets if p.name == 'SHA256SUMS.txt')
    for line in hashes.read_text().splitlines():
        checksum, name = line.split('  ')
        assert hashlib.sha256((hashes.parent / name).read_bytes()).hexdigest() == checksum
    assert '9 passed, 1 skipped' in notes.read_text()
    assert 'Unsigned prerelease' in notes.read_text()


@pytest.mark.parametrize('issue', ['tests', 'scan', 'commit', 'app', 'installer', 'portable', 'extra'])
def test_release_rejects_unverified_or_changed_builds(build, issue):
    dist = build / 'dist'
    if issue == 'tests':
        (build / 'test-results.xml').write_text('<testsuites><testsuite tests="10" failures="1"/></testsuites>')
    elif issue == 'scan':
        (dist / 'build-verification/SECURITY.json').write_text('{"defender":{"status":"NotRun"}}')
    elif issue == 'commit':
        with pytest.raises(ValueError, match='commit'):
            release.validate(build, 'different')
        return
    else:
        path = {'app': 'MellowPDFReader/MellowPDFReader.exe', 'installer': 'MellowPDFReader-Setup.exe',
                'portable': 'MellowPDFReader-Portable/MellowPDFReader.exe',
                'extra': 'MellowPDFReader-Portable/extra.exe'}[issue]
        (dist / path).write_bytes(b'changed')
    with pytest.raises(ValueError):
        release.validate(build, 'abc')
