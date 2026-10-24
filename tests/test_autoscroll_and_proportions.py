"""Focused real-PDF scrolling, pause semantics, and anchor-safe split presets."""
import pytest
from PySide6.QtCore import Qt,QEvent,QPoint,QPointF
from PySide6.QtGui import QWheelEvent,QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialog
from test_reader import app,pdf,technical_pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.settings import SettingsDialog
from mellow.autoscroll import scroll_speed


def window(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'scroll.db'),restore=False);w.show()
    r=w.open_pdf(pdf);wait(app)
    r.setZoomMode(r.ZoomMode.Custom);r.setZoomFactor(1.5);r.jump(0);wait(app,40)
    return w,r


def advance(controller,seconds):
    # Same elapsed-time accumulator as the real timer, with no wall-clock wait.
    for _ in range(round(seconds/.1)):
        if not controller.running:break
        controller.tick(controller._last+.1)


@pytest.mark.parametrize('layout',['continuous','single','two','two_continuous'])
def test_auto_scroll_moves_real_pdf_and_preserves_zoom_history(app,pdf,tmp_path,layout):
    w,r=window(app,pdf,tmp_path)
    w.set_page_layout(layout);wait(app,50)
    before=r.state(include_history=True)
    bar=r.verticalScrollBar();start=bar.value()
    assert w.auto_scroll.start(r)
    advance(w.auto_scroll,2)
    assert w.auto_scroll.running and 44<=bar.value()-start<=50
    assert r.zoomFactor()==before['zoom'] and r._past==before['past'] and r._future==before['future']
    w.auto_scroll.pause();assert not w.auto_scroll.timer.isActive()
    w.close()


def test_real_timer_fractional_speed_no_idle_wakeups_and_stall_clamp(app,pdf,tmp_path):
    w,r=window(app,pdf,tmp_path)
    w.auto_scroll.speed=5
    start=r.verticalScrollBar().value()
    w.auto_scroll.start(r);wait(app,450)
    assert w.auto_scroll.running and 1<=r.verticalScrollBar().value()-start<=4
    before=r.verticalScrollBar().value()
    w.auto_scroll.tick(w.auto_scroll._last+20)
    assert r.verticalScrollBar().value()-before<=1  # no catch-up jump after a stall
    w.auto_scroll.pause();stopped=r.state()
    wait(app,100)
    assert r.state()==stopped and not w.auto_scroll.timer.isActive()
    w.close()


@pytest.mark.parametrize('layout',['single','two'])
def test_fitted_pages_dwell_turn_and_stop_at_final_spread(app,technical_pdf,tmp_path,layout):
    w,r=window(app,technical_pdf,tmp_path)
    w.set_page_layout(layout);r.setZoomMode(r.ZoomMode.FitInView);r.jump(0);wait(app,80)
    w.auto_scroll.speed=200
    assert w.auto_scroll.start(r)
    advance(w.auto_scroll,1)
    assert r.pageNavigator().currentPage()==0
    advance(w.auto_scroll,4)
    wait(app,50)
    assert r.pageNavigator().currentPage()>0 and w.auto_scroll.running
    # Single Page/Two Pages must reach the final visible unit without skipping.
    visited={r.pageNavigator().currentPage()}
    for _ in range(10):
        if not w.auto_scroll.running:break
        advance(w.auto_scroll,5);wait(app,20)
        visited.add(r.pageNavigator().currentPage())
    assert not w.auto_scroll.running and not w.auto_scroll.timer.isActive()
    assert r.pageNavigator().currentPage() in ((4,) if layout=='single' else (3,4))
    w.close()


def test_continuous_end_and_rotated_cropped_scrolling(app,technical_pdf,tmp_path):
    w,r=window(app,technical_pdf,tmp_path)
    w.apply_margins((5,5,5,5));r.rotate_by(90);wait(app,60)
    w.auto_scroll.start(r);start=r.verticalScrollBar().value();advance(w.auto_scroll,1)
    assert w.auto_scroll.running and r.verticalScrollBar().value()>start
    w.auto_scroll.pause()
    r.verticalScrollBar().setValue(r.verticalScrollBar().maximum())
    assert w.auto_scroll.start(r)
    advance(w.auto_scroll,.1)
    assert not w.auto_scroll.running
    w.close()


@pytest.mark.parametrize('input_kind',['wheel','key','click','search','dialog','home','tab','deactivate','jump'])
def test_manual_input_and_context_changes_pause_without_restarting(app,pdf,tmp_path,input_kind):
    w,r=window(app,pdf,tmp_path)
    assert w.auto_scroll.start(r)
    if input_kind=='wheel':
        point=QPointF(r.viewport().rect().center())
        event=QWheelEvent(point,QPointF(r.viewport().mapToGlobal(point.toPoint())),QPoint(),QPoint(0,-120),
            Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
        QApplication.sendEvent(r.viewport(),event)
    elif input_kind=='key':QTest.keyClick(r,Qt.Key.Key_Down)
    elif input_kind=='click':QTest.mouseClick(r.viewport(),Qt.MouseButton.LeftButton,pos=QPoint(12,12))
    elif input_kind=='search':w.search_dialog()
    elif input_kind=='dialog':
        d=SettingsDialog(w.store,w);d.show();wait(app,20);d.reject();d.deleteLater()
    elif input_kind=='home':w.show_home();w.resume_reading()
    elif input_kind=='tab':w.select(0)
    elif input_kind=='deactivate':QApplication.sendEvent(w,QEvent(QEvent.Type.WindowDeactivate))
    else:r.jump(2)
    wait(app,40)
    assert not w.auto_scroll.running and not w.auto_scroll.timer.isActive()
    assert not w.auto_scroll_action.isChecked()
    w.close()


@pytest.mark.parametrize('different',[False,True])
def test_split_focus_independence_toggle_shortcut_and_fullscreen(app,pdf,technical_pdf,tmp_path,different):
    w,first=window(app,pdf,tmp_path)
    if different:w.open_pdf(technical_pdf)
    w.split(0,1 if different else 0);wait(app)
    second=w.secondary;w.focus_reader(second)
    w.fullscreen();wait(app,100)
    w.apply_settings({'shortcuts':{'auto_scroll':'F8'}})
    before=first.state(include_history=True)
    second.setFocus();QTest.keyClick(second,Qt.Key.Key_F8);wait(app,100)
    assert w.auto_scroll.running and w.auto_scroll.reader is second and w.auto_scroll_action.isChecked()
    assert first.state(include_history=True)==before
    QTest.keyClick(second,Qt.Key.Key_F8)
    assert not w.auto_scroll.running
    w.auto_scroll.start(second);w.focus_reader(first)
    assert not w.auto_scroll.running
    first.setFocus();w.auto_scroll_action.trigger();assert w.auto_scroll.running
    w.exit_split();assert not w.auto_scroll.running
    w.close()


def test_speed_settings_cancel_reset_validation_and_never_restore_running(app,pdf,tmp_path):
    w,r=window(app,pdf,tmp_path)
    d=SettingsDialog(w.store,w);d.auto_scroll_speed.setValue(80);d.reject()
    assert w.auto_scroll.speed==24
    d=SettingsDialog(w.store,w);d.auto_scroll_speed.setValue(80);d.accept();w.apply_settings(d.values())
    assert w.auto_scroll.speed==80 and w.store.get('auto_scroll_speed')==80
    d.reset_navigation();assert d.auto_scroll_speed.value()==24
    w.auto_scroll.start(r);w.save_session();store=w.store;w.close()
    restored=Window(store,restore=False);restored.show();restored.restore_session();wait(app)
    assert restored.auto_scroll.speed==80 and not restored.auto_scroll.running and not restored.auto_scroll.timer.isActive()
    for bad in (None,True,'fast',float('nan'),float('inf')):assert scroll_speed(bad)==24
    assert scroll_speed(-1)==5 and scroll_speed(400)==200
    assert not restored.auto_scroll.start(None)
    restored.close()


@pytest.mark.parametrize('orientation',['horizontal','vertical'])
@pytest.mark.parametrize('portion',[50,60,70])
def test_split_presets_preserve_source_anchors_zoom_history_and_focus(app,pdf,tmp_path,orientation,portion):
    w,first=window(app,pdf,tmp_path);w.split(0,0)
    if orientation=='vertical':w.orientation()
    second=w.secondary
    for index,r in enumerate((first,second)):
        r.setZoomMode(r.ZoomMode.FitToWidth if index else r.ZoomMode.Custom)
        r.jump(2+index*2)
    wait(app,60);w.focus_reader(second)
    before=[r.state(include_history=True) for r in (first,second)]
    w.ratio_actions[portion].trigger();wait(app,80)
    sizes=w.splitter.sizes()
    assert abs(sizes[0]/sum(sizes)-portion/100)<.01
    assert w.active is second and w.ratio_actions[portion].isChecked()
    for r,old in zip((first,second),before):
        state=r.state(include_history=True)
        assert state['anchor_page']==old['anchor_page'] and abs(state['y']-old['y'])<3
        assert state['mode']==old['mode'] and state['zoom']==old['zoom']
        assert state['past']==old['past'] and state['future']==old['future']
    w.close()


def test_ratio_after_swap_maximize_double_click_drag_and_session(app,pdf,tmp_path):
    w,first=window(app,pdf,tmp_path)
    assert not w.proportions_menu.isEnabled()
    w.split(0,0);wait(app)
    second=w.secondary;second.jump(5);w.focus_reader(second);w.swap();wait(app,50)
    assert w.splitter.widget(0) is second
    w.maximize_pane();wait(app,30)
    assert not first.isVisible()
    w.set_split_proportion(70);wait(app,50)
    assert first.isVisible() and w.active is second and second.pageNavigator().currentPage()==5
    assert abs(w.splitter.sizes()[0]/sum(w.splitter.sizes())-.7)<.01
    QTest.mouseDClick(w.splitter.handle(1),Qt.MouseButton.LeftButton);wait(app,50)
    assert abs(w.splitter.sizes()[0]-w.splitter.sizes()[1])<=1
    assert w.ratio_actions[50].isChecked()
    w.splitter.moveSplitter(round(w.splitter.width()*.55),1)
    assert not any(action.isChecked() for action in w.ratio_actions.values())
    w.set_split_proportion(60);wait(app,50);w.save_session();store=w.store;w.close()
    restored=Window(store,restore=False);restored.show();restored.restore_session();wait(app)
    assert restored.active is restored.secondary and restored.splitter.widget(0) is restored.secondary
    assert abs(restored.splitter.sizes()[0]/sum(restored.splitter.sizes())-.6)<.01
    assert restored.ratio_actions[60].isChecked()
    restored.close()


def test_menu_start_and_pause_when_another_popup_opens(app,pdf,tmp_path):
    w,r=window(app,pdf,tmp_path)
    w.auto_scroll.start(r)
    w.reading_menu.aboutToShow.emit()
    assert not w.auto_scroll.running  # immediate, before the next timer tick
    w.resize(1600,850);wait(app,30)
    button=w.toolbar.widgetForAction(w.auto_scroll_action)
    QTest.mouseClick(button,Qt.MouseButton.LeftButton)
    wait(app,100)
    assert w.auto_scroll.running and w.auto_scroll_action.isChecked()
    w.more_menu.popup(w.more_button.mapToGlobal(QPoint(0,30)));wait(app,20)
    assert not w.auto_scroll.running
    w.more_menu.close();w.close()


def test_close_active_pane_releases_controller_and_no_session_run_flag(app,pdf,tmp_path):
    w,r=window(app,pdf,tmp_path)
    w.auto_scroll.start(r)
    w.close_tab(0)
    assert w.auto_scroll.reader is None and not w.auto_scroll.timer.isActive()
    w.open_pdf(pdf);wait(app,30)
    assert not w.auto_scroll.running
    w.auto_scroll.start(w.active);w.close()
    assert w.auto_scroll.reader is None and not w.auto_scroll.timer.isActive()
    session=w.store.get('session')
    assert 'auto_scroll' not in session and 'auto_scroll' not in session['documents'][0]


def test_modified_toggle_keys_and_other_action_shortcuts_pause(app,pdf,tmp_path):
    w,r=window(app,pdf,tmp_path)
    w.apply_settings({'shortcuts':{'auto_scroll':'Ctrl+Shift+J'}})
    r.setFocus()
    for expected in (True,False,True):
        QTest.keyClick(r,Qt.Key.Key_J,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier)
        assert w.auto_scroll.running is expected
    QTest.keyClick(r,Qt.Key.Key_R,Qt.KeyboardModifier.ControlModifier)
    assert r.ruler and not w.auto_scroll.running
    w.auto_scroll.start(r);w.escape()
    assert not w.auto_scroll.running
    w.close()


def test_escape_key_pauses_before_exiting_fullscreen(app,pdf,tmp_path):
    w,r=window(app,pdf,tmp_path)
    w.fullscreen();wait(app,100);r.setFocus()
    assert w.auto_scroll.start(r)
    QTest.keyClick(r,Qt.Key.Key_Escape)
    assert not w.auto_scroll.running and w.isFullScreen()
    QTest.keyClick(r,Qt.Key.Key_Escape);wait(app,50)
    assert not w.isFullScreen()
    w.close()
