"""Small/Large page previews retain exact columns across popup resizes."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from test_reader import app,pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.pages import PagesPanel
from test_page_thumbnails_and_arrangement import thumbnails_ready

@pytest.mark.parametrize('width',[420,500,640])
@pytest.mark.parametrize('mode,columns',[('Small',3),('Large',2)])
def test_preview_grid_has_requested_columns_at_each_width(app,pdf,tmp_path,width,mode,columns):
    w=Window(Store(tmp_path/'state.db'),restore=False);w.show();r=w.open_pdf(pdf);wait(app,30)
    d=PagesPanel(r,w);d.resize(width,540);d.show();d.thumbnail_size.setCurrentText(mode);wait(app,60)
    try:
        assert [d.thumbnail_size.itemText(i) for i in range(d.thumbnail_size.count())]==['Small','Large']
        rects=[d.grid.visualRect(d.grid.pages.index(i,0)) for i in range(columns+1)]
        assert len({x.y() for x in rects[:columns]})==1
        assert rects[columns].y()>rects[0].y()
        assert rects[columns-1].right()<d.grid.viewport().width()
        thumbnails_ready(app,d.grid)
        assert d.grid.cache and len(d.grid.pending)<=2
    finally:d.reject();w.close()


def test_switch_and_resize_keep_selection_and_reader_until_activation(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'state.db'),restore=False);w.show();r=w.open_pdf(pdf);r.jump(3);wait(app,40)
    before=r.state(include_history=True);d=PagesPanel(r,w);d.show();wait(app,40)
    try:
        d.page_number.setValue(7);wait(app,20)
        for mode,width in [('Large',560),('Small',450),('Large',500)]:
            d.thumbnail_size.setCurrentText(mode);d.resize(width,560);wait(app,50)
            assert d.grid.currentIndex().row()==6 and d.page_number.value()==7
            assert r.state(include_history=True)==before
            assert 'Current' in d.grid.pages.index(3,0).data()
        QTest.keyClick(d.grid,Qt.Key.Key_Return);wait(app,30)
        assert r.pageNavigator().currentPage()==6 and d.grid.released and not d.layout_timer.isActive()
    finally:
        if not d._finished:d.reject()
        w.close()
