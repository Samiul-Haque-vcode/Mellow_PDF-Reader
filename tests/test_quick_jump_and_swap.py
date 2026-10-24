"""Quick Jump must participate in history; swapping books must retain pane sizes."""
import pytest
from PySide6.QtCore import Qt,QPointF
from PySide6.QtTest import QTest
from test_reader import app,pdf,technical_pdf,wait
from mellow.app import Window
from mellow.storage import Store


def opened(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'navigation.db'),restore=False)
    w.resize(1400,900);w.show();r=w.open_pdf(pdf);wait(app,60)
    r.zoom_to(1.6);wait(app,30)
    return w,r


def assert_location(reader,saved):
    current=reader.state()
    assert current['anchor_page']==saved['anchor_page']
    assert abs(current['y']-saved['y'])<3
    assert current['zoom']==saved['zoom'] and current['mode']==saved['mode']


@pytest.mark.parametrize('route',['keyboard','context'])
def test_quick_jump_return_records_departure_and_retraces_all_visits(app,pdf,tmp_path,route):
    w,r=opened(app,pdf,tmp_path)
    try:
        r.jump(1,QPointF(40,160));wait(app,30);r.setFocus()
        if route=='keyboard':QTest.keyClick(r,Qt.Key.Key_M,Qt.KeyboardModifier.ControlModifier)
        else:r.set_quick_jump((1,QPointF(40,160)))
        marker=dict(r.marker)
        r.jump(3,QPointF(40,200));wait(app,30);third=r.state()
        r.jump(5,QPointF(40,240));wait(app,30);fifth=r.state()
        count=len(r._past)
        if route=='keyboard':QTest.keyClick(r,Qt.Key.Key_M,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier)
        else:
            menu=r.page_context_menu(r.viewport().rect().center())
            next(a for a in menu.actions() if a.text()=='Return to Quick Jump').trigger()
            menu.deleteLater()
        wait(app,30);returned=r.state()
        assert returned['anchor_page']==1 and len(r._past)==count+1 and r.marker==marker
        w.update_controls();assert w.back_action.isEnabled()
        for saved in (fifth,third):
            QTest.keyClick(r,Qt.Key.Key_Left,Qt.KeyboardModifier.AltModifier);wait(app,30)
            assert_location(r,saved)
        for saved in (fifth,returned):
            QTest.keyClick(r,Qt.Key.Key_Right,Qt.KeyboardModifier.AltModifier);wait(app,30)
            assert_location(r,saved)
        assert r.marker==marker
    finally:w.close()


def test_quick_jump_branches_history_without_leaking_to_other_pane(app,pdf,tmp_path):
    w,first=opened(app,pdf,tmp_path)
    try:
        w.split(0,0);wait(app,40);second=w.secondary
        first.set_quick_jump();first.jump(2);first.jump(4);wait(app,30)
        first.back();wait(app,30);assert first._future
        second_before=second.state(include_history=True)
        w.focus_reader(first);w.return_marker();wait(app,30)
        assert not first._future and first.pageNavigator().currentPage()==0
        first.back();wait(app,30);assert first.pageNavigator().currentPage()==2
        assert second.state(include_history=True)==second_before
        first.marker=None;before=first.state(include_history=True)
        w.return_marker();assert first.state(include_history=True)==before
    finally:w.close()


@pytest.mark.parametrize('vertical',[False,True])
@pytest.mark.parametrize('same_pdf',[False,True])
def test_swapping_books_preserves_arbitrary_slot_ratio_and_reader_states(app,pdf,technical_pdf,tmp_path,vertical,same_pdf):
    w,first=opened(app,pdf,tmp_path)
    try:
        if not same_pdf:w.open_pdf(technical_pdf)
        w.split(0,0 if same_pdf else 1);wait(app,40)
        if vertical:w.orientation();wait(app,40)
        second=w.secondary
        first.zoom_to(1.6);second.zoom_to(1.8)
        first.jump(2,QPointF(40,160));second.jump(3,QPointF(50,180));wait(app,40)
        w.splitter.setSizes([617,383]);wait(app,40)
        w.focus_reader(second)
        before={r:r.state(include_history=True) for r in (first,second)}
        sizes=w.splitter.sizes()
        for order in ((second,first),(first,second)):
            w.swap();wait(app,50)
            assert tuple(w.splitter.widget(i) for i in range(2))==order
            assert all(abs(a-b)<=1 for a,b in zip(w.splitter.sizes(),sizes))
            assert w.active is second
            for r in (first,second):
                assert_location(r,before[r])
                assert r._past==before[r]['past'] and r._future==before[r]['future']
        w.set_split_proportion(70);wait(app,30);sizes=w.splitter.sizes()
        w.swap();wait(app,40)
        assert w.ratio_actions[70].isChecked()
        assert all(abs(a-b)<=1 for a,b in zip(w.splitter.sizes(),sizes))
    finally:w.close()


@pytest.mark.parametrize('vertical',[False,True])
def test_swap_with_one_maximized_pane_keeps_visible_book_usable(app,pdf,tmp_path,vertical):
    w,first=opened(app,pdf,tmp_path)
    try:
        w.split(0,0);wait(app,40)
        if vertical:w.orientation();wait(app,30)
        second=w.secondary;first.jump(2);second.jump(5);wait(app,30)
        w.focus_reader(second);w.maximize_pane();wait(app,30)
        assert second.isVisible() and not first.isVisible()
        before=second.state(include_history=True)
        for _ in range(2):
            w.swap();wait(app,40)
            assert second.isVisible() and not first.isVisible() and w.active is second
            assert second.width()>100 and second.height()>100
            assert_location(second,before)
        w.set_split_proportion(70);wait(app,30);sizes=w.splitter.sizes()
        assert first.isVisible() and second.isVisible()
        w.swap();wait(app,30)
        assert all(abs(a-b)<=1 for a,b in zip(w.splitter.sizes(),sizes))
    finally:w.close()
