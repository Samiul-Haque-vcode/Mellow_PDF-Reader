"""An older cached Windows interpreter must not silently enter a release."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('runtime_policy',Path(__file__).resolve().parents[1]/'packaging/runtime_policy.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)

@pytest.mark.parametrize('version',[(3,12,10),(3,14,0),(3,14,9),(3,15,0)])
def test_unsupported_or_unpatched_runtime_is_rejected(version):
    with pytest.raises(ValueError,match='3.14.10'):policy.check(version)

@pytest.mark.parametrize('version',[(3,14,10),(3,14,11)])
def test_supported_patches_are_accepted(version):policy.check(version)
