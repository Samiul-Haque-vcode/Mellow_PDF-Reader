"""Imported positions and metadata export must not break the reader or source files."""
import json
import pytest
from PySide6.QtCore import QPointF
from test_reader import app,pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow import backup

@pytest.mark.parametrize('action',['restore','jump','anchor'])
def test_large_finite_source_positions_are_clamped_to_scrollbar_range(app,pdf,tmp_path,action):
    w=Window(Store(tmp_path/'state.db'),restore=False);w.show();r=w.open_pdf(pdf);wait(app,40)
    try:
        r.zoom_to(4);wait(app,30)
        state=dict(r.state(),x=1e9,y=1e9,viewport=None)
        if action=='restore':r.restore(state)
        elif action=='jump':r.jump(0,QPointF(1e9,1e9))
        else:r.restore_view_anchor(state)
        wait(app,20)
        assert r.horizontalScrollBar().value()==r.horizontalScrollBar().maximum()
        assert r.verticalScrollBar().value()==r.verticalScrollBar().maximum()
        r.jump(0,QPointF(40,100));wait(app,20)
        assert r.pageNavigator().currentPage()==0
    finally:w.close()

@pytest.mark.parametrize('kind',['favorites','backup'])
def test_metadata_export_cannot_overwrite_a_pdf(tmp_path,kind):
    store=Store(tmp_path/'data'/'state.db');path=tmp_path/'book.pdf';path.write_bytes(b'%PDF-original')
    try:
        operation=store.export_favorites if kind=='favorites' else lambda p:backup.write(store,p)
        with pytest.raises(ValueError,match='JSON'):operation(path)
        assert path.read_bytes()==b'%PDF-original'
    finally:store.db.close()

def test_failed_favorites_export_keeps_previous_json(tmp_path,monkeypatch):
    store=Store(tmp_path/'data'/'state.db');store.add('favorite','/book.pdf',0,'Keep')
    path=tmp_path/'favorites.json';path.write_bytes(b'previous data')
    def fail(*args):raise OSError('Disk failure')
    monkeypatch.setattr(backup.os,'replace',fail)
    try:
        with pytest.raises(OSError):store.export_favorites(path)
        assert path.read_bytes()==b'previous data'
        assert not list(tmp_path.glob('.mellow-backup-*'))
    finally:store.db.close()

def test_favorites_export_refuses_the_live_database(tmp_path):
    store=Store(tmp_path/'data'/'state.json')
    try:
        with pytest.raises(ValueError,match='outside'):store.export_favorites(tmp_path/'data'/'state.json')
        assert store.get('theme','Sepia')=='Sepia'
    finally:store.db.close()

@pytest.mark.parametrize('value',[float('inf'),float('-inf'),float('nan'),10**4000])
def test_scrollbar_conversion_never_receives_an_unbounded_number(app,pdf,tmp_path,value):
    w=Window(Store(tmp_path/'state.db'),restore=False);w.show();r=w.open_pdf(pdf);wait(app,30)
    try:
        bar=r.verticalScrollBar();r._set_scroll_position(bar,value)
        assert bar.minimum()<=bar.value()<=bar.maximum()
    finally:w.close()

@pytest.mark.parametrize('kind',['favorites','backup'])
def test_metadata_export_protects_pdf_content_with_json_extension(tmp_path,kind):
    store=Store(tmp_path/'data'/'state.db');path=tmp_path/'book.json';path.write_bytes(b'%PDF-1.7\noriginal PDF')
    try:
        operation=store.export_favorites if kind=='favorites' else lambda p:backup.write(store,p)
        with pytest.raises(ValueError,match='PDF'):operation(path)
        assert path.read_bytes()==b'%PDF-1.7\noriginal PDF'
    finally:store.db.close()
