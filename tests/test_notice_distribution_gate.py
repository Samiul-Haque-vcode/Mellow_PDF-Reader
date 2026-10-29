"""A binary distribution needs matching, unmodified attribution evidence."""
import importlib.util
import json
import platform
import shutil
import sys
from email.message import Message
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('notice_gate',ROOT/'packaging/collect_notices.py')
notices=importlib.util.module_from_spec(spec);spec.loader.exec_module(notices)


@pytest.fixture
def bundle(tmp_path,monkeypatch):
    source=tmp_path/'source';source.mkdir()
    for name in ('README.md','LICENSE','THIRD_PARTY.md'):shutil.copy2(ROOT/name,source/name)
    shutil.copytree(ROOT/'packaging/notices',source/'packaging/notices')
    (source/'packaging/notices/REVIEW.json').unlink(missing_ok=True)
    installation=tmp_path/'python';installation.mkdir();(installation/'LICENSE.txt').write_text('Python fixture license')
    monkeypatch.setattr(sys,'base_prefix',str(installation))
    distributions={}
    class Distribution:
        def __init__(self,name):
            self.version='6.12.0.140' if name=='PySide6_Pdf' else '1.0'
            self.metadata=Message();self.metadata['License']='Fixture license'
            self.files=['LICENSE.txt'];self.directory=tmp_path/'packages'/name;self.directory.mkdir(parents=True)
            (self.directory/'LICENSE.txt').write_text('Fixture copyright and redistribution terms for '+name)
        def locate_file(self,path):return self.directory/path
    for name in notices.PACKAGES:distributions[name]=Distribution(name)
    monkeypatch.setattr(notices.metadata,'distribution',lambda name:distributions[name])
    app=tmp_path/'distribution';app.mkdir();(app/'Qt6Pdf.dll').write_bytes(b'fixture native binary')
    report=notices.collect(app,source)
    return source,app,distributions,report


def record_fixture_review(source,app,report):
    # Simulated maintainer evidence for testing the gate, not a real legal review.
    evidence={'LGPL-3.0.txt':notices.digest(app/'licenses/LGPL-3.0.txt')}
    for row in report['packages']:
        for name in row['notices']:evidence[name]=notices.digest(app/'licenses'/name)
    review=dict(format=1,package_versions={r['name']:r['version'] for r in report['packages']},
        python=sys.version.split()[0],platform=sys.platform,architecture=platform.machine(),
        native_files=report['native_files'],files=evidence,
        native_licenses={name:['LGPL-3.0.txt'] for name in report['native_files']},
        checks={name:dict(complete=True,evidence=['LGPL-3.0.txt']) for name in notices.REVIEW_CHECKS},
        package_notices={r['name']:r['notices'] for r in report['packages']})
    (source/'packaging/notices/REVIEW.json').write_text(json.dumps(review))
    return review


def test_upstream_pdf_notices_are_copied_and_review_stays_pending(bundle):
    source,app,distributions,report=bundle
    assert report['qt_pdf_notices']==dict(valid=True,version='6.140.0',documents=9)
    assert len(list((app/'licenses/qt-pdf-6.140.0').glob('*.txt')))==9
    assert not report['complete_attribution_review']
    with pytest.raises(ValueError,match='REVIEW.json'):notices.require_complete(report)


def test_distribution_accepts_matching_recorded_review(bundle):
    source,app,distributions,report=bundle;record_fixture_review(source,app,report)
    report=notices.collect(app,source);notices.require_complete(report)
    assert report['complete_attribution_review'] and not report['collection_issues']


@pytest.mark.parametrize('change',['native_changed','native_added','helper_added','version','notice','missing_check','missing_source_review','platform','missing_native_notice'])
def test_stale_or_incomplete_review_blocks_distribution(bundle,change):
    source,app,distributions,report=bundle;review=record_fixture_review(source,app,report)
    review_path=source/'packaging/notices/REVIEW.json'
    if change=='native_changed':(app/'Qt6Pdf.dll').write_bytes(b'changed binary')
    elif change=='native_added':(app/'unreviewed.dll').write_bytes(b'new binary')
    elif change=='helper_added':(app/'new-helper.exe').write_bytes(b'unreviewed helper')
    elif change=='version':distributions['PySide6_Pdf'].version='6.12.1.140'
    elif change=='notice':(source/'packaging/notices/qt-pdf-6.140.0/pdfium.txt').write_text('truncated license')
    elif change=='missing_check':
        review['checks'].pop('lgpl_source_access');review_path.write_text(json.dumps(review))
    elif change=='platform':
        review['platform']='another-platform';review_path.write_text(json.dumps(review))
    elif change=='missing_native_notice':
        review['native_licenses']={};review_path.write_text(json.dumps(review))
    else:
        notices.collect(app,source) # Leave a previously valid review in output.
        review_path.unlink()
    with pytest.raises(ValueError,match='not ready'):notices.require_complete(notices.collect(app,source))


@pytest.mark.parametrize('path',['../outside.txt','/absolute.txt','sub\\outside.txt'])
def test_review_cannot_read_evidence_outside_licenses(bundle,path):
    source,app,distributions,report=bundle;review=record_fixture_review(source,app,report)
    review['files'][path]='0'*64
    (source/'packaging/notices/REVIEW.json').write_text(json.dumps(review))
    report=notices.collect(app,source)
    assert not report['recorded_review']['valid']
    with pytest.raises(ValueError):notices.require_complete(report)


def test_missing_installed_dependency_is_reported(bundle,monkeypatch):
    source,app,distributions,report=bundle
    def distribution(name):
        if name=='pypdf':raise notices.metadata.PackageNotFoundError(name)
        return distributions[name]
    monkeypatch.setattr(notices.metadata,'distribution',distribution)
    report=notices.collect(app,source)
    assert report['missing_required_packages']==['pypdf']
    with pytest.raises(ValueError,match='pypdf'):notices.require_complete(report)


def test_strict_command_exits_nonzero_and_writes_actionable_inventory(tmp_path):
    import subprocess
    distribution=tmp_path/'app'
    result=subprocess.run([sys.executable,str(ROOT/'packaging/collect_notices.py'),
        str(distribution),'--require-complete'],capture_output=True,text=True,timeout=30)
    assert result.returncode==2 and 'not ready' in result.stderr
    report=json.loads((distribution/'licenses/DEPENDENCIES.json').read_text())
    assert report['qt_pdf_notices']['documents']==9
    assert not report['complete_attribution_review']
    assert 'REVIEW.json' in result.stdout


def test_git_windows_line_endings_preserve_upstream_notice_hashes(tmp_path):
    import subprocess
    repository=tmp_path/'checkout';repository.mkdir()
    def git(*args):
        return subprocess.run(['git','-C',str(repository),*args],check=True,capture_output=True)
    git('init');git('config','core.autocrlf','true')
    shutil.copy2(ROOT/'.gitattributes',repository/'.gitattributes')
    relative=Path('packaging/notices/qt-pdf-6.140.0/abseil.txt')
    path=repository/relative;path.parent.mkdir(parents=True)
    original=(ROOT/relative).read_bytes();path.write_bytes(original)
    git('add','.gitattributes',relative.as_posix());path.unlink()
    git('checkout-index','--force','--',relative.as_posix())
    assert path.read_bytes()==original


def test_actual_optional_native_package_is_included_in_notice_inventory(bundle):
    source,app,distributions,report=bundle
    distributions['charset-normalizer']=type(distributions['numpy'])('charset-normalizer')
    directory=app/'_internal/charset_normalizer';directory.mkdir(parents=True)
    (directory/'md.pyd').write_bytes(b'native')
    result=notices.collect(app,source)
    row=next(r for r in result['packages'] if r['name']=='charset-normalizer')
    assert row['notices'] and not result['missing_required_packages']


def test_commercial_reference_is_not_counted_as_an_open_source_notice(bundle):
    source,app,distributions,report=bundle
    d=distributions['PySide6_Essentials'];d.files=['LicenseRef-Qt-Commercial.txt']
    (d.directory/d.files[0]).write_text('Commercial licensing reference')
    result=notices.collect(app,source)
    row=next(r for r in result['packages'] if r['name']=='PySide6_Essentials')
    assert row['commercial_reference_files']==d.files and not row['notices']
    assert 'PySide6_Essentials' in result['missing_package_notice_files']
