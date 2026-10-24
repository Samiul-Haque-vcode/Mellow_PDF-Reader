"""Fullscreen paints only the final layout and accepts actual frame geometry."""
import time
import pytest
from PySide6.QtCore import Qt,QSize,QEvent,QObject
from test_reader import app,pdf,wait
from mellow.app import Window
from mellow.storage import Store


def settled(app,window):
    deadline=time.monotonic()+2
    while window._fullscreen_snapshots is not None and time.monotonic()<deadline:wait(app,5)
    assert window._fullscreen_snapshots is None
    assert window.updatesEnabled() and window._root_layout.isEnabled()
    assert window.window_effects._restore is None


def test_changed_native_size_does_not_wait_for_an_exact_predicted_size(app,pdf,tmp_path,monkeypatch):
    w=Window(Store(tmp_path/'mismatch.db'),restore=False);w.show();r=w.open_pdf(pdf);wait(app)
    r.jump(3);wait(app);original=r.state()
    w.fullscreen();settled(app,w)
    w.fullscreen()
    w._fullscreen_target_size=w.size()+QSize(1,1)
    # A permanently unexpired deadline makes timeout-based restoration fail.
    monkeypatch.setattr(w,'_fullscreen_deadline',float('inf'))
    wait(app,40)
    assert w._fullscreen_snapshots is None
    assert r.state()['anchor_page']==original['anchor_page']
    assert abs(r.state()['y']-original['y'])<2
    w.close()


@pytest.mark.parametrize('caption',[False,True])
@pytest.mark.parametrize('maximized',[False,True])
def test_transitions_batch_caption_controls_and_restore_geometry(app,pdf,tmp_path,monkeypatch,caption,maximized):
    from mellow import caption as module
    if caption and not hasattr(Qt.WindowType,'ExpandedClientAreaHint'):pytest.skip('Qt 6.9 API')
    monkeypatch.setattr(module,'supported',lambda:caption)
    store=Store(tmp_path/'batch.db');store.set('caption_tabs',caption)
    w=Window(store,restore=False);w.resize(760,620)
    if maximized:w.showMaximized()
    else:w.show()
    first=w.open_pdf(pdf);wait(app);w.split(0,0);wait(app)
    second=w.secondary;first.jump(2);second.jump(4);w.focus_reader(second);wait(app)
    before=[r.state(include_history=True) for r in (first,second)]
    geometry=w.geometry();calls=[];paints=[]
    for reader in (first,second):
        original=reader.restore_view_anchor
        def restore(state,reader=reader,original=original):
            calls.append((reader,w.updatesEnabled(),w.toolbar.isVisible(),w._chrome_overlay))
            return original(state)
        monkeypatch.setattr(reader,'restore_view_anchor',restore)
    class Probe(QObject):
        def eventFilter(self,obj,event):
            if event.type()==QEvent.Type.Paint and w._fullscreen_snapshots is not None:paints.append(1)
            return False
    probe=Probe();first.viewport().installEventFilter(probe);second.viewport().installEventFilter(probe)
    for _ in range(3):
        calls.clear();w.fullscreen();settled(app,w)
        assert len(calls)==2 and all(not update and overlay and not visible for _,update,visible,overlay in calls)
        calls.clear();w.fullscreen();settled(app,w)
        assert len(calls)==2 and all(not update and visible and not overlay for _,update,visible,overlay in calls)
        assert w.isMaximized()==maximized and w.active is second
        if not maximized:assert w.geometry()==geometry
    assert not paints
    for reader,old in zip((first,second),before):
        now=reader.state(include_history=True)
        assert now['anchor_page']==old['anchor_page'] and abs(now['y']-old['y'])<2
        assert now['past']==old['past'] and now['future']==old['future']
    first.viewport().removeEventFilter(probe);second.viewport().removeEventFilter(probe)
    w.close()


def test_failed_native_switch_restores_updates_layout_and_caption(app,pdf,tmp_path,monkeypatch):
    w=Window(Store(tmp_path/'error.db'),restore=False);w.show();w.open_pdf(pdf);wait(app)
    monkeypatch.setattr(w,'showFullScreen',lambda:(_ for _ in ()).throw(RuntimeError('native switch failed')))
    with pytest.raises(RuntimeError,match='native switch failed'):w.fullscreen()
    assert w.updatesEnabled() and w._root_layout.isEnabled()
    assert w._fullscreen_snapshots is None and w.window_effects._restore is None
    assert not w._chrome_overlay and w.toolbar.isVisible()
    w.close()


def test_final_caption_frame_adjustment_restores_saved_bounds_before_paint(app,pdf,tmp_path,monkeypatch):
    w=Window(Store(tmp_path/'frame.db'),restore=False);w.resize(760,620);w.show();w.open_pdf(pdf);wait(app)
    normal=w.geometry()
    w.fullscreen();settled(app,w)
    finish=w.caption_tabs.finish_transition
    observed=[]
    restores=[]
    monkeypatch.setattr(w,'restore_visible',lambda states:restores.append(states))
    def change_frame():
        finish()
        if not w.isFullScreen():
            observed.append(w.updatesEnabled())
            w.setGeometry(normal.adjusted(6,8,6,8))
    monkeypatch.setattr(w.caption_tabs,'finish_transition',change_frame)
    w.fullscreen();settled(app,w)
    assert observed==[False] and w.geometry()==normal and not restores
    w.close()


def test_rapid_roundtrip_and_new_navigation_do_not_reapply_old_location(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'rapid.db'),restore=False);w.show();r=w.open_pdf(pdf);wait(app)
    r.jump(3);wait(app);before=r.state()
    w.fullscreen();w.fullscreen();settled(app,w)
    assert r.state()['anchor_page']==before['anchor_page']
    w.fullscreen();w.finish_fullscreen_transition(force=True);r.jump(6);wait(app,180)
    assert r.pageNavigator().currentPage()==6 and w.updatesEnabled()
    w.fullscreen();settled(app,w);w.close()


def test_window_effects_restore_the_original_value_on_finish_and_reentry(app,monkeypatch):
    from mellow import window_effects as module
    import ctypes
    monkeypatch.setattr(module.sys,'platform','win32')
    monkeypatch.setattr(module.QApplication,'platformName',lambda:'windows')
    calls=[]
    class Function:
        def __init__(self,callback):self.callback=callback
        def __call__(self,*args):return self.callback(*args)
    class API:
        def __init__(self):
            self.value=0
            def get(hwnd,key,pointer,size):
                ctypes.cast(pointer,ctypes.POINTER(ctypes.c_long))[0]=self.value;return 0
            def set_(hwnd,key,pointer,size):
                self.value=int(ctypes.cast(pointer,ctypes.POINTER(ctypes.c_long))[0]);calls.append(self.value);return 0
            self.DwmGetWindowAttribute=Function(get);self.DwmSetWindowAttribute=Function(set_)
    api=API();monkeypatch.setattr(module.ctypes,'WinDLL',lambda _:api,raising=False)
    class Window:
        def winId(self):return 42
    effect=module.WindowEffects(Window())
    effect.begin();assert api.value==1
    effect.begin();effect.finish();assert api.value==0 and calls==[1,0,1,0]
    api.value=1;effect.begin();effect.finish();assert api.value==1


def test_unavailable_dwm_leaves_the_standard_transition_usable(app,monkeypatch):
    from mellow import window_effects as module
    monkeypatch.setattr(module.sys,'platform','win32')
    monkeypatch.setattr(module.QApplication,'platformName',lambda:'windows')
    def unavailable(_):raise OSError('DWM unavailable')
    monkeypatch.setattr(module.ctypes,'WinDLL',unavailable,raising=False)
    class Window:
        def winId(self):return 42
    effect=module.WindowEffects(Window());effect.begin();effect.finish()
    assert effect._restore is None


def test_native_outer_bounds_roundtrip_avoids_frame_margin_drift(app,monkeypatch):
    from mellow import window_effects as module
    from ctypes import wintypes
    import ctypes
    monkeypatch.setattr(module.sys,'platform','win32')
    monkeypatch.setattr(module.QApplication,'platformName',lambda:'windows')
    class Function:
        def __init__(self,callback):self.callback=callback
        def __call__(self,*args):return self.callback(*args)
    class API:
        bounds=(-1200,40,900,700)
        calls=[]
        def __init__(self):
            def get(hwnd,pointer):
                x,y,width,height=self.bounds
                rect=ctypes.cast(pointer,ctypes.POINTER(wintypes.RECT)).contents
                rect.left,rect.top,rect.right,rect.bottom=x,y,x+width,y+height
                return 1
            def set_(hwnd,after,x,y,width,height,flags):
                self.calls.append((hwnd,after,flags));self.bounds=(x,y,width,height);return 1
            self.GetWindowRect=Function(get);self.SetWindowPos=Function(set_)
            # Native API initialization also binds placement functions. Bounds
            # capture/restoration must not call those or change restore state.
            self.GetWindowPlacement=Function(lambda *_:pytest.fail('Bounds capture queried restore placement'))
            self.SetWindowPlacement=Function(lambda *_:pytest.fail('Bounds restore changed restore placement'))
    api=API();monkeypatch.setattr(module.ctypes,'WinDLL',lambda _:api,raising=False)
    class Window:
        def winId(self):return 42
    effect=module.WindowEffects(Window());saved=effect.capture_bounds()
    api.bounds=(0,0,1920,1080)
    assert effect.restore_bounds(saved) and effect.capture_bounds()==(-1200,40,900,700)
    assert api.calls==[(42,None,0x14)]
    assert effect.restore_bounds(saved) and len(api.calls)==1
    assert not effect.restore_bounds(None)
