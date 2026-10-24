"""Fullscreen controls must not change the PDF layout or reading position."""
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu
from test_reader import app, pdf, wait
from mellow.app import Window
from mellow.storage import Store


def move(widget,x,y):
    point=QPointF(x,y)
    event=QMouseEvent(QEvent.Type.MouseMove,point,
                     QPointF(widget.mapToGlobal(point.toPoint())),
                     Qt.MouseButton.NoButton,Qt.MouseButton.NoButton,
                     Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(widget,event)


@pytest.mark.parametrize('layout',['single','horizontal','vertical'])
@pytest.mark.parametrize('fit',['custom','width','page'])
def test_controls_overlay_preserves_every_pane(app,pdf,tmp_path,monkeypatch,layout,fit):
    w=Window(Store(tmp_path/'overlay.db'),restore=False)
    w.show()
    first=w.open_pdf(pdf)
    wait(app)
    if layout!='single':
        w.split(0,0)
        if layout=='vertical': w.orientation()
        wait(app)
    readers=[first]+([w.secondary] if w.secondary else [])
    for i,r in enumerate(readers):
        r.setZoomMode(r.ZoomMode.Custom)
        r.setZoomFactor(1.3+i*.2)
        if fit!='custom': r.setZoomMode(r.ZoomMode.FitToWidth if fit=='width' else r.ZoomMode.FitInView)
        r.jump(2+i*2)
    wait(app)
    for r in readers: r.verticalScrollBar().setValue(r.verticalScrollBar().value()+75)
    before=[r.state(include_history=True) for r in readers]
    w.fullscreen()
    wait(app,100)
    assert not w.toolbar.isVisible() and not w.tabstrip.isVisible()
    for r,old in zip(readers,before):
        now=r.state(include_history=True)
        assert now['anchor_page']==old['anchor_page']
        assert abs(now['y']-old['y'])<2
        assert now['past']==old['past'] and now['future']==old['future']
    snapshots=[r.state(include_history=True) for r in readers]
    sizes=[r.viewport().size() for r in readers]
    monkeypatch.setattr(w,'pointer_in_chrome',lambda:False)
    for _ in range(3):
        w.show_chrome()
        wait(app,25)
        assert w.toolbar.isVisible()
        assert w.toolbar.geometry().intersects(w.pages.geometry())
        w.hide_chrome()
        wait(app,25)
        assert not w.toolbar.isVisible()
        for r,state,size in zip(readers,snapshots,sizes):
            assert r.viewport().size()==size
            assert r.state(include_history=True)==state
    w.fullscreen()
    wait(app,100)
    assert w.toolbar.isVisible() and w.tabstrip.isVisible()
    assert not w._chrome_overlay
    for r,old in zip(readers,before):
        now=r.state(include_history=True)
        assert now['anchor_page']==old['anchor_page']
        assert abs(now['y']-old['y'])<2
        assert now['zoom']==old['zoom'] and now['mode']==old['mode']
    w.close()


def test_autohide_waits_for_fields_menus_and_pointer(app,pdf,tmp_path,monkeypatch):
    w=Window(Store(tmp_path/'timer.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    w.fullscreen()
    wait(app,100)
    # Holding the pointer at the reveal edge must not leave controls stuck
    # after auto-hide pauses, even over blank space outside tracked widgets.
    move(r.viewport(),r.viewport().width()-5,1)
    monkeypatch.setattr(w,'pointer_in_chrome',lambda:True)
    wait(app,700)
    assert w.toolbar.isVisible() and not w.chrome_timer.isActive()
    monkeypatch.setattr(w,'pointer_in_chrome',lambda:False)
    move(r.viewport(),200,200)
    assert w.chrome_timer.isActive()
    w.page.lineEdit().setFocus()
    wait(app,700)
    assert w.toolbar.isVisible()
    r.setFocus()
    move(w.toolbar,10,10)
    assert not w.chrome_timer.isActive()
    move(r.viewport(),200,200)
    assert w.chrome_timer.isActive()
    wait(app,700)
    assert not w.toolbar.isVisible()
    w.show_chrome()
    menu=QMenu(w)
    menu.addAction('Test menu')
    menu.popup(w.toolbar.mapToGlobal(w.toolbar.rect().center()))
    wait(app,700)
    assert w.toolbar.isVisible()
    menu.close()
    r.setFocus()
    w.schedule_chrome_hide()
    wait(app,700)
    assert not w.toolbar.isVisible()
    w.set_autohide(False)
    wait(app,700)
    assert w.toolbar.isVisible()
    assert not w._chrome_overlay
    assert w.pages.geometry().top()>w.toolbar.geometry().bottom()
    w.apply_settings({'fullscreen_autohide':True})
    wait(app,700)
    assert w._chrome_overlay
    assert not w.toolbar.isVisible()
    w.close()


def test_fullscreen_home_resume_and_maximized_exit(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'home.db'),restore=False)
    w.showMaximized()
    r=w.open_pdf(pdf)
    wait(app)
    w.fullscreen()
    wait(app,100)
    w.show_home()
    wait(app,100)
    assert not w._chrome_overlay
    assert w.tabstrip.isVisible() and not w.toolbar.isVisible()
    assert w.pages.geometry().top()>=w.tabstrip.geometry().bottom()
    w.resume_reading()
    wait(app,100)
    assert w._chrome_overlay
    assert not w.tabstrip.isVisible() and not w.toolbar.isVisible()
    w.fullscreen()
    wait(app,100)
    assert w.isMaximized() and not w.isFullScreen()
    assert w.toolbar.isVisible()
    w.close()


def test_late_native_fullscreen_resize_preserves_anchor(app,pdf,tmp_path,monkeypatch):
    w=Window(Store(tmp_path/'native-resize.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    r.setZoomMode(r.ZoomMode.FitInView)
    r.jump(3)
    wait(app)
    r.verticalScrollBar().setValue(r.verticalScrollBar().value()+75)
    old=r.state()
    old_size=w.size()
    # Model a platform reporting the old window size for the first few frames
    # after the fullscreen state has changed. Let Qt lay out the real PDF.
    native_size=w.size
    ready=[False]
    monkeypatch.setattr(w,'size',lambda:native_size() if ready[0] else old_size)
    w.fullscreen()
    wait(app,40)
    assert w._fullscreen_snapshots is not None
    ready[0]=True
    wait(app,40)
    assert w._fullscreen_snapshots is None
    now=r.state()
    assert now['anchor_page']==old['anchor_page']
    assert abs(now['y']-old['y'])<2
    w.close()


def test_plus_and_open_shortcut_each_open_once(app,pdf,tmp_path,monkeypatch):
    calls=[]
    monkeypatch.setattr(QFileDialog,'getOpenFileNames',lambda *args:(calls.append(1) or [],''))
    w=Window(Store(tmp_path/'open.db'),restore=False)
    w.show()
    w.open_pdf(pdf)
    wait(app)
    assert w.open_action not in w.toolbar.actions()
    QTest.mouseClick(w.add_tab_button,Qt.MouseButton.LeftButton)
    assert len(calls)==1
    QTest.keyClick(w,Qt.Key.Key_O,Qt.KeyboardModifier.ControlModifier)
    assert len(calls)==2
    w.apply_settings({'shortcuts':{'open':'Ctrl+Shift+O'}})
    assert 'Ctrl+Shift+O' in w.add_tab_button.toolTip()
    QTest.keyClick(w,Qt.Key.Key_O,Qt.KeyboardModifier.ControlModifier)
    assert len(calls)==2
    QTest.keyClick(w,Qt.Key.Key_O,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier)
    assert len(calls)==3
    w.close()
