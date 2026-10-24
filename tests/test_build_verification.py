"""The published fingerprints must describe the actual binaries, not placeholders."""
import importlib.util
import json
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('verify_windows',Path(__file__).resolve().parents[1]/'packaging/verify_windows.py')
verify=importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


def test_manifest_hashes_every_bundled_file_and_installer(tmp_path):
    app=tmp_path/'app'
    app.mkdir()
    (app/'reader.exe').write_bytes(b'original exe')
    (app/'lib.dll').write_bytes(b'original lib')
    installer=tmp_path/'setup.exe'
    installer.write_bytes(b'installer')
    output=tmp_path/'reports'
    manifest=verify.build_manifest(app,installer,output)
    assert {row['path'] for row in manifest['files']}=={'app/reader.exe','app/lib.dll','setup.exe'}
    for row in manifest['files']: assert row['sha256']==verify.sha256(tmp_path/row['path'])
    old=manifest['files'][1]['sha256']
    (app/'reader.exe').write_bytes(b'changed exe')
    assert verify.sha256(app/'reader.exe')!=old
    assert len((output/'SHA256SUMS.txt').read_text().splitlines())==3
    assert json.loads((output/'BUILD.json').read_text())['files']==manifest['files']
    with pytest.raises(ValueError): verify.build_manifest(app,installer,app/'reports')


def test_unavailable_scanner_does_not_claim_a_successful_scan(tmp_path,monkeypatch):
    # A failed status lookup on Windows must remain explicit, too.
    monkeypatch.setattr(verify,'IS_WINDOWS',True)
    monkeypatch.setattr(verify,'powershell_json',lambda script: (_ for _ in ()).throw(OSError('Unavailable')))
    report,failed=verify.windows_report(tmp_path,tmp_path/'setup.exe',tmp_path)
    assert report['defender']['status']=='NotRun'
    assert 'Cannot read Defender status' in report['defender']['reason']
    assert report['signatures']==[] and not failed


@pytest.mark.parametrize('code,expected',[(0,'NoThreatsReported'),(2,'DetectionOrScanError')])
def test_defender_result_is_recorded_and_nonzero_blocks_publication(tmp_path,monkeypatch,code,expected):
    from types import SimpleNamespace
    monkeypatch.setattr(verify,'IS_WINDOWS',True)
    monkeypatch.setenv('ProgramData',str(tmp_path))
    scanner=tmp_path/'Microsoft/Windows Defender/Platform/1/MpCmdRun.exe'
    scanner.parent.mkdir(parents=True)
    scanner.write_bytes(b'test scanner path')
    def status(script):
        if 'Get-AuthenticodeSignature' in script: return [{'Status':'NotSigned'}]
        return dict(AMServiceEnabled=True,AntivirusEnabled=True)
    monkeypatch.setattr(verify,'powershell_json',status)
    commands=[]
    def run(command,**kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=code,stdout='Scanner output',stderr='')
    monkeypatch.setattr(verify.subprocess,'run',run)
    report,failed=verify.windows_report(tmp_path,tmp_path/'setup.exe',tmp_path)
    assert report['defender']['status']==expected and failed==(code!=0)
    assert report['signatures'][0]['Status']=='NotSigned'
    assert len(commands)==2 and all('-DisableRemediation' in command for command in commands)
    assert (tmp_path/'defender-installer.log').read_text()=='Scanner output\n'


@pytest.mark.skipif(not verify.IS_WINDOWS,reason='Authenticode requires Windows')
def test_real_windows_authenticode_query():
    import sys
    result=verify.authenticode([Path(sys.executable).resolve()])
    assert isinstance(result,list) and len(result)==1
    assert result[0]['Status']
    assert Path(result[0]['Path']).resolve()==Path(sys.executable).resolve()
