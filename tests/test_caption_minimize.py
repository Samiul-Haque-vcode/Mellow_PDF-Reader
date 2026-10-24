"""Native-caption state ordering and protected system-button space."""
import pytest
import ctypes
from PySide6.QtCore import Qt,QPoint,QEvent
from PySide6.QtGui import QExposeEvent,QRegion,QWindowStateChangeEvent
from PySide6.QtWidgets import QToolButton
from test_reader import app,pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.window_effects import WindowEffects,WindowPlacement


@pytest.fixture
def window(app,tmp_path,monkeypatch):
    from mellow import caption
    monkeypatch.setattr(caption,'supported',lambda:True)
    w=Window(Store(tmp_path/'caption.db'),restore=False)
    w.showMaximized();wait(app,40)
    yield w
    w.close();wait(app,10)


def test_system_button_region_cannot_be_claimed_by_overlapping_child(window):
    w=window
    overlap=QToolButton(w.tabstrip)
    overlap.setGeometry(w.tabstrip.width()-145,0,140,30)
    overlap.show();overlap.raise_()
    point=overlap.mapTo(w,overlap.rect().center())
    assert w.childAt(point) is overlap
    assert not w.caption_tabs.interactive_at(point)
    assert w.caption_tabs.interactive_at(w.more_button.mapTo(w,w.more_button.rect().center()))


@pytest.mark.parametrize('native_first',[False,True])
def test_no_native_flag_or_layout_changes_while_either_window_is_minimized(window,monkeypatch,native_first):
    w=window;handle=w.windowHandle();calls=[]
    if native_first:
        monkeypatch.setattr(handle,'windowStates',lambda:Qt.WindowState.WindowMinimized)
        monkeypatch.setattr(w,'isMinimized',lambda:False)
    else:
        monkeypatch.setattr(w,'isMinimized',lambda:True)
        monkeypatch.setattr(handle,'windowStates',lambda:Qt.WindowState.WindowNoState)
    monkeypatch.setattr(w.caption_tabs,'_update_space',lambda:calls.append('updated'))
    w.caption_tabs.update_space()
    assert not calls


def test_native_state_events_defer_reconciliation_until_qt_finishes(window,app,monkeypatch):
    w=window;calls=[]
    monkeypatch.setattr(w.caption_tabs,'_update_space',lambda:calls.append('updated'))
    app.sendEvent(w,QWindowStateChangeEvent(Qt.WindowState.WindowNoState))
    assert not calls and w.caption_tabs.reconcile.isActive()
    wait(app,20)
    assert calls==['updated'] and not w.caption_tabs.reconcile.isActive()


def test_style_events_cannot_rebuild_frame_inside_pending_state_change(window,app,monkeypatch):
    calls=[]
    monkeypatch.setattr(window.caption_tabs,'_update_space',lambda:calls.append('updated'))
    app.sendEvent(window,QWindowStateChangeEvent(Qt.WindowState.WindowNoState))
    app.sendEvent(window,QEvent(QEvent.Type.StyleChange))
    window.caption_tabs.update_space() # safe-area callbacks can also arrive here.
    assert not calls
    wait(app,25)
    assert calls==['updated'] and not window.caption_tabs.reconcile.isActive()


@pytest.mark.parametrize('widget_maximized',[False,True])
def test_mixed_widget_native_states_wait_for_agreement_without_polling(window,app,monkeypatch,widget_maximized):
    calls=[];handle=window.windowHandle()
    state=Qt.WindowState.WindowMaximized if widget_maximized else Qt.WindowState.WindowNoState
    other=Qt.WindowState.WindowNoState if widget_maximized else Qt.WindowState.WindowMaximized
    monkeypatch.setattr(window,'windowState',lambda:state)
    monkeypatch.setattr(handle,'windowStates',lambda:other)
    monkeypatch.setattr(window.caption_tabs,'_update_space',lambda:calls.append('updated'))
    window.caption_tabs.queue_reconcile();wait(app,25)
    assert not calls and not window.caption_tabs.reconcile.isActive()
    wait(app,25)
    assert not calls # No repeated timer retries while Qt catches up.
    monkeypatch.setattr(handle,'windowStates',lambda:state)
    app.sendEvent(handle,QWindowStateChangeEvent(other));wait(app,25)
    assert calls==['updated']


def test_stale_qt_caption_is_hidden_and_detached_even_with_hidden_parent(window,monkeypatch):
    from types import SimpleNamespace
    calls=[]
    def find(parent,after,kind,title):
        assert parent==int(window.winId()) and kind=='_q_titlebar'
        return None if after else 123
    def show(child,command):calls.append(('hide',child,command))
    def parent(child,target):calls.append(('detach',child,target.value))
    api=SimpleNamespace(FindWindowExW=find,ShowWindow=show,SetParent=parent,
                        IsWindowVisible=lambda child:pytest.fail('Hidden ancestors invalidate this check'))
    monkeypatch.setattr(window.window_effects,'bounds_api',lambda:api)
    assert window.window_effects.hide_extended_caption()
    assert calls==[('hide',123,0),('detach',123,ctypes.c_void_p(-3).value)]


def test_caption_cleanup_only_runs_in_ordinary_restored_mode(window,app,monkeypatch):
    calls=[]
    monkeypatch.setattr(window.window_effects,'hide_extended_caption',lambda:calls.append('hide'))
    window.caption_tabs.update_space();assert not calls
    window.showNormal();wait(app,40)
    assert calls
    calls.clear();window.showMaximized();wait(app,40)
    assert not calls


def test_exposure_repairs_late_title_overlay_and_safe_area_inset(window,app):
    w=window;handle=w.windowHandle()
    handle.setFlag(Qt.WindowType.WindowTitleHint,True)
    handle.setFlag(Qt.WindowType.NoTitleBarBackgroundHint,False)
    w.setAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea,True)
    # No explicit call to update_space: real QWindow exposure must recover.
    app.sendEvent(handle,QExposeEvent(QRegion(w.rect())))
    wait(app,40)
    assert not handle.flags() & Qt.WindowType.WindowTitleHint
    assert handle.flags() & Qt.WindowType.NoTitleBarBackgroundHint
    assert not w.testAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea)
    assert w.tabstrip.mapTo(w,QPoint()).y()==0
    assert not w.caption_tabs.reconcile.isActive()


@pytest.mark.parametrize('maximized',[False,True])
def test_native_minimize_restore_keeps_window_state_and_document_position(window,app,pdf,maximized):
    w=window;r=w.open_pdf(pdf);wait(app,40)
    r.jump(3);wait(app,40)
    if maximized:w.showMaximized()
    else:w.showNormal()
    wait(app,40)
    before=r.state();normal=w.normalGeometry()
    for _ in range(3):
        # Qt's Windows caption buttons call QWindow.showMinimized().
        w.windowHandle().showMinimized();wait(app,40)
        assert w.isMinimized()
        assert w.windowHandle().windowStates() & Qt.WindowState.WindowMinimized
        if maximized:w.showMaximized()
        else:w.showNormal()
        wait(app,40)
        assert not w.isMinimized() and w.isMaximized()==maximized
        assert w.tabstrip.y()==0 and w.normalGeometry()==normal
        assert bool(w.windowHandle().flags() & Qt.WindowType.WindowTitleHint)==(not maximized)
        after=r.state()
        assert after['anchor_page']==before['anchor_page']
        assert abs(after['y']-before['y'])<2


def test_closed_window_cannot_restart_caption_reconciliation(window,app):
    w=window
    w.close()
    w.caption_tabs.queue_reconcile()
    assert not w.caption_tabs.reconcile.isActive()


def test_restored_window_uses_windows_caption_and_does_not_intercept_it(window,app,monkeypatch):
    from ctypes import wintypes
    from mellow import caption
    window.showNormal();wait(app,40)
    handle=window.windowHandle()
    assert handle.flags() & Qt.WindowType.WindowTitleHint
    assert not handle.flags() & (Qt.WindowType.ExpandedClientAreaHint | Qt.WindowType.NoTitleBarBackgroundHint)
    assert window.tabstrip.layout().contentsMargins().right()==0
    monkeypatch.setattr(caption.sys,'platform','win32')
    for message in (0x84,0x86):
        msg=wintypes.MSG();msg.message=message
        assert window.caption_tabs.native_hit_test(ctypes.addressof(msg)) is None
    assert not window.caption_tabs.interactive_at(window.more_button.mapTo(window,QPoint()))


def test_restored_roundtrip_keeps_maximized_header_and_split_pages(window,app,pdf):
    w=window;first=w.open_pdf(pdf);w.split(0,0);wait(app,40)
    second=w.secondary;first.jump(2);second.jump(4);wait(app,40)
    expected=[r.state()['anchor_page'] for r in (first,second)]
    layout=w.tabstrip.layout()
    before=(w.tabstrip.geometry(),layout.contentsMargins(),w.tabs.geometry(),w.styleSheet())
    for _ in range(2):
        w.showNormal();wait(app,40)
        assert w.windowHandle().flags() & Qt.WindowType.WindowTitleHint
        w.showMaximized();wait(app,40)
        assert (w.tabstrip.geometry(),layout.contentsMargins(),w.tabs.geometry(),w.styleSheet())==before
        assert not w.windowHandle().flags() & Qt.WindowType.WindowTitleHint
        assert [r.state()['anchor_page'] for r in (first,second)]==expected


@pytest.mark.parametrize('show',[1,2,3])
def test_caption_style_changes_retain_only_an_existing_native_maximize(window,monkeypatch,show):
    from types import SimpleNamespace
    calls=[]
    class API:
        def GetWindowPlacement(self,hwnd,pointer):
            value=pointer._obj;value.showCmd=show;value.flags=2
            value.rcNormalPosition[:]=(40,60,840,660)
            return True
        def SetWindowPlacement(self,hwnd,pointer):
            value=pointer._obj
            calls.append(('placement',value.showCmd,list(value.rcNormalPosition),value.flags))
            return True
    monkeypatch.setattr(window.window_effects,'bounds_api',lambda:API())
    flags=Qt.WindowType.ExpandedClientAreaHint
    handle=SimpleNamespace(flags=lambda:Qt.WindowType.WindowTitleHint,
                           setFlags=lambda flags:calls.append(('flags',flags)))
    window.window_effects.set_caption_flags(handle,flags)
    expected=[('flags',flags)]
    if show==3:expected.append(('placement',3,[40,60,840,660],2))
    assert calls==expected


@pytest.mark.parametrize('old,new',[(Qt.WindowType.ExpandedClientAreaHint,Qt.WindowType.ExpandedClientAreaHint),
                                  (Qt.WindowType.Window,Qt.WindowType.ExpandedClientAreaHint),
                                  (Qt.WindowType.ExpandedClientAreaHint,Qt.WindowType.Window)])
def test_caption_placement_fix_does_not_change_existing_full_view_behavior(window,monkeypatch,old,new):
    from types import SimpleNamespace
    calls=[]
    monkeypatch.setattr(window.window_effects,'bounds_api',lambda:pytest.fail('Full-view placement changed'))
    handle=SimpleNamespace(flags=lambda:old,setFlags=lambda flags:calls.append(flags))
    window.window_effects.set_caption_flags(handle,new)
    assert calls==[new]



@pytest.mark.parametrize('active',[False,True])
def test_activation_skips_default_native_caption_paint(window,app,monkeypatch,active):
    from ctypes import wintypes
    from mellow import caption
    monkeypatch.setattr(caption.sys,'platform','win32')
    calls=[]
    monkeypatch.setattr(window.window_effects,'refresh_caption',lambda height:calls.append(height))
    msg=wintypes.MSG();msg.message=0x86;msg.wParam=int(active)
    assert window.caption_tabs.native_hit_test(ctypes.addressof(msg))==1
    wait(app,20)
    assert calls==[window.tabstrip.minimumHeight()]
    wait(app,20)
    assert len(calls)==1 # No paint/expose polling loop.


@pytest.mark.parametrize('mode',['disabled','fullscreen','transition','ordinary'])
def test_activation_keeps_default_behavior_outside_extended_caption(window,monkeypatch,mode):
    from ctypes import wintypes
    from mellow import caption
    monkeypatch.setattr(caption.sys,'platform','win32')
    if mode=='disabled':window.caption_tabs.enabled=False
    elif mode=='fullscreen':monkeypatch.setattr(window,'isFullScreen',lambda:True)
    elif mode=='transition':window.caption_tabs._transition_fullscreen=True
    else:window.windowHandle().setFlag(Qt.WindowType.ExpandedClientAreaHint,False)
    msg=wintypes.MSG();msg.message=0x86
    assert window.caption_tabs.native_hit_test(ctypes.addressof(msg)) is None


def test_activation_uses_applied_frame_while_logical_maximize_state_catches_up(window,monkeypatch):
    from ctypes import wintypes
    from mellow import caption
    monkeypatch.setattr(caption.sys,'platform','win32')
    monkeypatch.setattr(window,'isMaximized',lambda:False)
    monkeypatch.setattr(window.windowHandle(),'windowStates',lambda:Qt.WindowState.WindowNoState)
    assert not window.caption_tabs.extended_caption()
    assert window.windowHandle().flags() & Qt.WindowType.ExpandedClientAreaHint
    msg=wintypes.MSG();msg.message=0x86;msg.wParam=0
    assert window.caption_tabs.native_hit_test(ctypes.addressof(msg))==1


def test_caption_flag_repair_requests_one_native_repaint(window,monkeypatch):
    calls=[]
    monkeypatch.setattr(window.window_effects,'refresh_caption',lambda height:calls.append(height))
    window.windowHandle().setFlag(Qt.WindowType.WindowTitleHint,True)
    window.caption_tabs.update_space()
    window.caption_tabs.update_space()
    assert calls==[window.tabstrip.minimumHeight()]


def test_long_tab_names_scroll_instead_of_expanding_header(window,app):
    tabs=window.tabs
    for index in range(12):
        tabs.addTab(f'{index}: A very long science textbook filename with many chapters.pdf')
    window.resize(560,700);wait(app,20)
    tabs.setCurrentIndex(tabs.count()-1);wait(app,20)
    assert tabs.usesScrollButtons() and tabs.elideMode()==Qt.TextElideMode.ElideRight
    assert all(tabs.tabSizeHint(index).width()<=220 for index in range(tabs.count()))
    reserve=window.tabstrip.layout().contentsMargins().right()
    end=window.add_tab_button.mapTo(window.tabstrip,QPoint(window.add_tab_button.width(),0)).x()
    assert end<=window.tabstrip.width()-reserve


def test_maximized_native_minimize_retains_restore_target_after_state_event(window,app,monkeypatch):
    w=window;handle=w.windowHandle();calls=[]
    monkeypatch.setattr(w,'isMinimized',lambda:True)
    monkeypatch.setattr(handle,'windowStates',lambda:Qt.WindowState.WindowMinimized)
    monkeypatch.setattr(w.window_effects,'retain_maximized_restore',lambda:calls.append('restore-maximized'))
    monkeypatch.setattr(w.caption_tabs,'_update_space',lambda:pytest.fail('Changed minimized decorations'))
    app.sendEvent(handle,QWindowStateChangeEvent(Qt.WindowState.WindowMaximized))
    assert not calls # Do not change placement inside native state dispatch.
    wait(app,20)
    assert calls==['restore-maximized']


@pytest.mark.parametrize('show,flags,read_ok,write_ok,expected,writes',[
    (2,0,True,True,True,1),(2,1,True,True,True,1),
    (2,2,True,True,True,0),(1,0,True,True,False,0),
    (3,0,True,True,False,0),(2,0,False,True,False,0),
    (2,0,True,False,False,1)])
def test_native_restore_flag_only_changes_minimized_placement(window,monkeypatch,show,flags,read_ok,write_ok,expected,writes):
    effects=WindowEffects(window);saved=[]
    class API:
        def GetWindowPlacement(self,hwnd,pointer):
            value=pointer._obj
            assert value.length==44
            value.showCmd=show;value.flags=flags
            value.ptMinPosition[:]=(-1,-1)
            value.ptMaxPosition[:]=(0,0)
            value.rcNormalPosition[:]=(-1200,40,-300,740)
            return read_ok
        def SetWindowPlacement(self,hwnd,pointer):
            value=pointer._obj
            saved.append((value.showCmd,value.flags,list(value.rcNormalPosition),list(value.ptMinPosition)))
            return write_ok
    monkeypatch.setattr(effects,'bounds_api',lambda:API())
    assert ctypes.sizeof(WindowPlacement)==44
    assert effects.retain_maximized_restore()==expected
    assert len(saved)==writes
    if saved:assert saved==[(2,flags|2,[-1200,40,-300,740],[-1,-1])]
