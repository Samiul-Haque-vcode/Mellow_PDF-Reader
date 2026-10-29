"""A refreshed release must verify its own commit and actual test report."""
import copy
import importlib.util
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_assets',ROOT/'packaging/release_assets.py')
assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)
sys.modules.setdefault('release_assets',assets)
spec=importlib.util.spec_from_file_location('verify_published',ROOT/'packaging/verify_published.py')
verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)


def evidence():
    commit='a'*40
    return dict(commit=commit,python='3.14.10'),dict(defender=dict(status='NoThreatsReported'),
        changed_or_missing_files=[],signatures=[dict(Status='NotSigned')]*2),dict(commit=commit,
        tests=724,errors=0,failures=0,skipped=0),'Build commit: '+commit


def test_updated_build_uses_its_actual_successful_test_count():
    assert verifier.check_evidence(*evidence(),expected_build='a'*40)=='a'*40


@pytest.mark.parametrize('change',['commit','report_commit','notes','no_tests','failed','skipped','invalid_count','no_scan','changed_files'])
def test_unrelated_or_incomplete_release_evidence_is_rejected(change):
    build,security,tests,body=copy.deepcopy(evidence())
    if change=='commit':build['commit']='b'*40
    elif change=='report_commit':tests['commit']='b'*40
    elif change=='notes':body='Another build'
    elif change=='no_tests':tests['tests']=0
    elif change=='failed':tests['failures']=1
    elif change=='skipped':tests['skipped']=1
    elif change=='invalid_count':tests['tests']='724'
    elif change=='no_scan':security['defender']['status']='NotRun'
    else:security['changed_or_missing_files']=['app.exe']
    with pytest.raises(ValueError):verifier.check_evidence(build,security,tests,body,expected_build='a'*40)
