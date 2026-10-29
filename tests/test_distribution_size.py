"""Only the optional OpenGL fallback is removed; PDF and image tools stay intact."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('prepare_distribution',Path(__file__).resolve().parents[1]/'packaging/prepare_distribution.py')
prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)


def test_optional_renderer_removal_keeps_reader_and_required_libraries(tmp_path):
    app=tmp_path/'app';folder=app/'_internal/PySide6';folder.mkdir(parents=True)
    (app/'MellowPDFReader.exe').write_bytes(b'app')
    for name in ('opengl32sw.dll','Qt6Pdf.dll','Qt6Widgets.dll','Qt6Svg.dll'):(folder/name).write_bytes(b'native')
    assert prepare.prepare(app)==[dict(path='_internal/PySide6/opengl32sw.dll',bytes=6)]
    assert not (folder/'opengl32sw.dll').exists()
    assert all((folder/name).read_bytes()==b'native' for name in ('Qt6Pdf.dll','Qt6Widgets.dll','Qt6Svg.dll'))
    assert prepare.prepare(app)==[]


def test_distribution_cleanup_rejects_an_unrelated_directory(tmp_path):
    with pytest.raises(ValueError,match='application folder'):prepare.prepare(tmp_path)
