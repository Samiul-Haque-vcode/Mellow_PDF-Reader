"""Release downloads fail closed on bad sources, tests or repository identity."""
import hashlib
import importlib.util
import io
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('release_assets',Path(__file__).resolve().parents[1]/'packaging/release_assets.py')
assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)


def source_row(body):
    return dict(name='qtbase-6.12.0',url='https://download.qt.io/source.tar.xz',bytes=len(body),sha256=hashlib.sha256(body).hexdigest())


def test_source_download_checks_bytes_hash_and_can_reuse_verified_archive(tmp_path):
    body=b'original corresponding source archive';row=source_row(body)
    path=assets.download_source(row,tmp_path,lambda *a,**k:io.BytesIO(body))
    assert path.read_bytes()==body and not list(tmp_path.glob('*.part'))
    def no_network(*a,**k):pytest.fail('Verified source unexpectedly downloaded twice')
    assert assets.download_source(row,tmp_path,no_network)==path


@pytest.mark.parametrize('received',[b'truncated',b'longer than the expected source archive',b'xxxxxxxxxxxxxxxxxxxxxxxxxxxx'])
def test_bad_source_download_is_not_left_as_publishable_asset(tmp_path,received):
    row=source_row(b'expected source archive data')
    with pytest.raises(ValueError):assets.download_source(row,tmp_path,lambda *a,**k:io.BytesIO(received))
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('field,value',[('name','../outside'),('url','http://download.qt.io/a'),('url','https://example.com/a'),('bytes',True),('sha256','unverified')])
def test_invalid_source_manifest_is_rejected_before_network(tmp_path,field,value):
    row=source_row(b'archive');row[field]=value
    def no_network(*a,**k):pytest.fail('Invalid manifest reached the network')
    with pytest.raises(ValueError):assets.download_source(row,tmp_path,no_network)


@pytest.mark.parametrize('attributes',['tests="0"','tests="2" failures="1"','tests="2" errors="1"'])
def test_failed_or_empty_test_report_cannot_prepare_release(tmp_path,attributes):
    report=tmp_path/'tests.xml';report.write_text('<testsuites><testsuite '+attributes+'/></testsuites>')
    with pytest.raises(ValueError):assets.test_totals(report)


def test_passing_test_report_counts_skipped_separately(tmp_path):
    report=tmp_path/'tests.xml';report.write_text('<testsuites><testsuite tests="12" skipped="1" failures="0" errors="0"/></testsuites>')
    assert assets.test_totals(report)==dict(tests=12,skipped=1,failures=0,errors=0)


def test_publication_rejects_other_repository_or_branch(monkeypatch):
    monkeypatch.setenv('GITHUB_REF','refs/heads/main');monkeypatch.setenv('GITHUB_REPOSITORY','other/repository')
    with pytest.raises(ValueError,match='restricted'):assets.publish()
    monkeypatch.setenv('GITHUB_REPOSITORY',assets.REPOSITORY);monkeypatch.setenv('GITHUB_REF','refs/heads/other')
    with pytest.raises(ValueError,match='restricted'):assets.publish()


def test_preparation_handles_unicode_under_non_utf8_system_locale(tmp_path):
    import json,os,shutil,subprocess,sys
    root=tmp_path/'release';root.mkdir()
    (root/'README.md').write_text('Mellow test fixture',encoding='utf8')
    notes=root/'docs/releases/1.0.0.md';notes.parent.mkdir(parents=True)
    notes.write_text('A softer way to read. “Mellow” — {{BUILD_COMMIT}} / {{PASSED_TESTS}}',encoding='utf8')
    sources=root/'packaging/notices/SOURCE-ARCHIVES.json';sources.parent.mkdir(parents=True)
    sources.write_text('{"archives":[]}',encoding='utf8')
    def git(*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
    git('init','-b','main');git('add','README.md','docs','packaging')
    git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','Release fixture')
    commit=git('rev-parse','HEAD')
    dist=root/'dist';app=dist/'MellowPDFReader';(app/'licenses').mkdir(parents=True)
    (app/'MellowPDFReader.exe').write_bytes(b'app fixture')
    (app/'licenses/DEPENDENCIES.json').write_text('{"complete_attribution_review":true}',encoding='utf8')
    installer=dist/'MellowPDFReader-Setup.exe';installer.write_bytes(b'installer fixture')
    portable=dist/'MellowPDFReader-Portable';shutil.copytree(app,portable)
    (portable/'portable.ini').write_text('portable fixture',encoding='utf8')
    verification=dist/'build-verification';verification.mkdir()
    files=[dict(path=p.relative_to(dist).as_posix(),sha256=assets.digest(p)) for p in [*app.rglob('*'),installer] if p.is_file()]
    (verification/'BUILD.json').write_text(json.dumps(dict(commit=commit,files=files)),encoding='utf8')
    (verification/'SECURITY.json').write_text(json.dumps(dict(defender=dict(status='NoThreatsReported'),signatures=[dict(Path='app.exe',Status='NotSigned')])),encoding='utf8')
    (verification/'SHA256SUMS.txt').write_text('fixture',encoding='utf8')
    (root/'test-results.xml').write_text('<testsuites><testsuite tests="1"/></testsuites>',encoding='utf8')
    module=str(Path(assets.__file__).resolve())
    code=f'import importlib.util;from pathlib import Path;s=importlib.util.spec_from_file_location("assets",{module!r});m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.ROOT=Path({str(root)!r});m.prepare()'
    env=os.environ.copy();env.update(GITHUB_SHA=commit,PYTHONUTF8='0',PYTHONCOERCECLOCALE='0',LC_ALL='C')
    result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert '“Mellow”' in (dist/'release/release-notes.md').read_text(encoding='utf8')
    manifest=json.loads((dist/'release/assets.json').read_text(encoding='utf8'))
    assert len(manifest['files'])==5 and all((dist/'release'/r['name']).is_file() for r in manifest['files'])


def test_github_response_decodes_utf8_under_non_utf8_system_locale(tmp_path):
    import json,os,subprocess,sys
    module=str(Path(assets.__file__).resolve())
    response=json.dumps({'body':'“Mellow” — A softer way to read.'},ensure_ascii=False).encode('utf8')
    child='import sys;sys.stdout.buffer.write('+repr(response)+')'
    code=(f'import importlib.util,json,sys;from pathlib import Path;s=importlib.util.spec_from_file_location("assets",{module!r});'
          f'm=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.ROOT=Path({str(tmp_path)!r});original=m.subprocess.run;'
          f'm.subprocess.run=lambda command,**kwargs:original([sys.executable,"-c",{child!r}],**kwargs);'
          'print(json.dumps(json.loads(m.github_cli("api","fixture"))))')
    env=os.environ.copy();env.update(PYTHONUTF8='0',PYTHONCOERCECLOCALE='0',LC_ALL='C')
    result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)==json.loads(response)
