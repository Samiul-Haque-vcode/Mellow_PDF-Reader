"""Fullscreen key-repeat protection and chrome leaving the active monitor."""
import pytest
from PySide6.QtCore import Qt,QEvent,QTimer,QObject
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from test_reader import app,pdf,wait
from test_fullscreen_transitions import settled
from mellow.app import Window
from mellow.storage import Store


@pytest.mark.parametrize('remapped',[False,True])
def test_holding_fullscreen_key_does_not_repeat_transitions(app,pdf,tmp_path,remapped):
    w=Window(Store(tmp_path/'repeat-fullscreen.db'),restore=False);w.show();reader=w.open_pdf(pdf);wait(app,40)
    if remapped:w.apply_settings({'shortcuts':{'fullscreen':'F8'}})
    key=Qt.Key.Key_F8 if remapped else Qt.Key.Key_F11
    w.activateWindow();reader.setFocus();wait(app,20)
    QTest.keyClick(reader,key);settled(app,w);assert w.isFullScreen()
    for _ in range(7):
        QApplication.sendEvent(reader,QKeyEvent(QEvent.Type.KeyPress,key,Qt.KeyboardModifier.NoModifier,'',True,1))
    assert w.isFullScreen() and w._fullscreen_snapshots is None
    QTest.keyClick(reader,key);settled(app,w);assert not w.isFullScreen()
    w.close()


def test_holding_controls_shortcut_does_not_flicker_chrome(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'repeat-chrome.db'),restore=False);w.show();r=w.open_pdf(pdf);wait(app,40)
    w.fullscreen();settled(app,w);w.show_chrome();w.activateWindow();r.setFocus();wait(app,20)
    mods=Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier
    QTest.keyClick(r,Qt.Key.Key_H,mods);assert not w.toolbar.isVisible()
    for _ in range(5):QApplication.sendEvent(r,QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_H,mods,'H',True,1))
    assert not w.toolbar.isVisible()
    QTest.keyClick(r,Qt.Key.Key_H,mods);assert w.toolbar.isVisible()
    w.close()


@pytest.mark.parametrize('target',['window','toolbar','tabs'])
def test_leaving_chrome_to_another_monitor_resumes_hide_delay_without_page_jump(app,pdf,tmp_path,monkeypatch,target):
    store=Store(tmp_path/'leave-monitor.db');store.set('fullscreen_hide_delay',200)
    w=Window(store,restore=False);w.show();reader=w.open_pdf(pdf);wait(app,40);w.fullscreen();settled(app,w)
    w.show_chrome();reader.setFocus();w.chrome_timer.stop();w._chrome_pointer_inside=True
    before=reader.state(include_history=True)
    monkeypatch.setattr(w,'pointer_in_chrome',lambda:False)
    obj=w if target=='window' else w.toolbar if target=='toolbar' else w.tabstrip
    QApplication.sendEvent(obj,QEvent(QEvent.Type.Leave))
    assert w.chrome_timer.isActive() and not w._chrome_pointer_inside
    wait(app,250)
    assert not w.toolbar.isVisible() and not w.tabstrip.isVisible()
    assert reader.state(include_history=True)==before
    w.close()


def test_child_leave_inside_chrome_keeps_controls_visible(app,pdf,tmp_path,monkeypatch):
    w=Window(Store(tmp_path/'inside-chrome.db'),restore=False);w.show();w.open_pdf(pdf);wait(app,40)
    w.fullscreen();settled(app,w);w.show_chrome();w.chrome_timer.stop();w._chrome_pointer_inside=True
    monkeypatch.setattr(w,'pointer_in_chrome',lambda:True)
    QApplication.sendEvent(w.toolbar,QEvent(QEvent.Type.Leave))
    assert not w.chrome_timer.isActive() and w.toolbar.isVisible()
    w.close()


def test_delayed_native_entry_preserves_anchor_and_paints_only_after_final_size(app,pdf,tmp_path,monkeypatch):
    w=Window(Store(tmp_path/'delayed-entry.db'),restore=False);w.show();reader=w.open_pdf(pdf);wait(app,40)
    reader.jump(4);wait(app,40);before=reader.state(include_history=True);paints=[]
    class Probe(QObject):
        def eventFilter(self,obj,event):
            if event.type()==QEvent.Type.Paint and w._fullscreen_snapshots is not None:paints.append(1)
            return False
    probe=Probe();reader.viewport().installEventFilter(probe)
    original=w.showFullScreen
    monkeypatch.setattr(w,'showFullScreen',lambda:QTimer.singleShot(25,original))
    w.fullscreen();assert not w.updatesEnabled()
    settled(app,w)
    assert w.isFullScreen() and not paints
    state=reader.state(include_history=True)
    assert state['anchor_page']==before['anchor_page'] and abs(state['y']-before['y'])<2
    assert state['past']==before['past'] and state['future']==before['future']
    reader.viewport().removeEventFilter(probe);w.close()
