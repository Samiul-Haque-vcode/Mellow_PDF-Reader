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
