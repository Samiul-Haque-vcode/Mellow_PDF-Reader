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


@pytest.mark.parametrize('other_importer',[False,True])
def test_optional_tls_backend_is_removed_only_without_other_importers(tmp_path,monkeypatch,other_importer):
    import sys
    from types import SimpleNamespace
    root=tmp_path/'app';(root/'_internal/PySide6/plugins/tls').mkdir(parents=True)
    (root/'MellowPDFReader.exe').write_bytes(b'app')
    relatives=('_internal/PySide6/plugins/tls/qopensslbackend.dll','_internal/libssl-3-x64.dll',
        '_internal/libcrypto-3-x64.dll','_internal/_ssl.pyd','_internal/libssl-3.dll','_internal/libcrypto-3.dll')
    for relative in relatives:(root/relative).write_bytes(b'native')
    class PE:
        def __init__(self,path,**kw):
            self.DIRECTORY_ENTRY_IMPORT=([SimpleNamespace(dll=b'libssl-3-x64.dll')]
                if other_importer and Path(path).name=='_ssl.pyd' else [])
        def parse_data_directories(self,**kw):pass
        def close(self):pass
    monkeypatch.setitem(sys.modules,'pefile',SimpleNamespace(PE=PE,DIRECTORY_ENTRY={
        'IMAGE_DIRECTORY_ENTRY_IMPORT':1,'IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT':13}))
    if other_importer:
        with pytest.raises(ValueError,match='another bundled binary'):prepare.prepare(root)
        assert all((root/name).is_file() for name in relatives)
    else:
        assert {r['path'] for r in prepare.prepare(root)}==set(relatives[:3])
        assert all((root/name).is_file() for name in relatives[3:])
