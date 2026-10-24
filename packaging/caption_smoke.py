"""Windows platform check for optional caption tabs, without touchpad claims."""
import argparse
import ctypes
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


@contextmanager
def smoke_window(store, settle):
    """Release native PDF handles before TemporaryDirectory removes its files."""
    from PySide6.QtCore import QCoreApplication,QEvent
    from mellow.app import Window
    window=Window(store,restore=False)
    try:
        yield window
    finally:
        window.exit_split()
        while window.readers:
            window.close_tab(len(window.readers)-1)
        window.home.thumbnail.release()
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        settle()
        store.db.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='dist/caption-verification')
    args=parser.parse_args()
    if sys.platform!='win32':
        parser.error('This check requires the Windows Qt platform.')
    os.environ['QT_QPA_PLATFORM']='windows'
    from PySide6.QtCore import Qt,QEvent,QEventLoop,QTimer,QPoint
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from reportlab.pdfgen.canvas import Canvas
    from mellow.storage import Store
    app=QApplication([])
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    report={}
    def settle(ms=150):
        loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()
    with tempfile.TemporaryDirectory(prefix='mellow-caption-') as directory:
        root=Path(directory)
        source=root/'caption.pdf'
        canvas=Canvas(str(source))
        for index in range(4):
            canvas.setFont('Helvetica-Bold',20);canvas.setFillColorRGB(31/255,64/255,87/255)
            canvas.drawString(40,720,f'Caption test page {index+1}')
            canvas.setFont('Helvetica',11);canvas.setFillColorRGB(0,0,0)
            canvas.drawString(40,690,'Readable colored headings and ordinary body text.');canvas.showPage()
        canvas.save()
        store=Store(root/'state.db')
        try:
            with smoke_window(store,settle) as w:
                w.show();r=w.open_pdf(source);settle()
                assert w.caption_tabs.enabled
                assert w.more_button.isVisible() and w.inline_search.text.isVisible()
                assert w.brand_mark.isVisible()
                assert w.tabstrip.layout().itemAt(0).widget() is w.brand_mark
                assert w.tabstrip.layout().itemAt(1).widget() is w.more_button
                assert 'more' not in w.toolbar.entries and 'search' not in w.toolbar.entries
                native=w.windowHandle().flags()
                report['initial_flags']=dict(widget=hex(int(w.windowFlags())),native=hex(int(native)),
                    title_enum_complement=hex(int(~Qt.WindowType.WindowTitleHint)))
                print('Caption flags:',report['initial_flags'])
                assert not native & Qt.WindowType.FramelessWindowHint
                assert native & Qt.WindowType.WindowMinimizeButtonHint
                assert native & Qt.WindowType.WindowMaximizeButtonHint
                assert native & Qt.WindowType.WindowCloseButtonHint
                user32=ctypes.windll.user32
                user32.GetSystemMenu.argtypes=[ctypes.c_void_p,ctypes.c_int]
                user32.GetSystemMenu.restype=ctypes.c_void_p
                user32.GetMenuState.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_uint]
                user32.GetMenuState.restype=ctypes.c_uint
                from ctypes import wintypes
                user32.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
                user32.ClientToScreen.restype=wintypes.BOOL
                user32.SendMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
                user32.SendMessageW.restype=ctypes.c_ssize_t
                def check_menu(context):
                    point=w.more_button.mapTo(w,w.more_button.rect().center())
                    native_point=wintypes.POINT(round(point.x()*w.devicePixelRatioF()),round(point.y()*w.devicePixelRatioF()))
                    assert user32.ClientToScreen(int(w.winId()),ctypes.byref(native_point))
                    packed=(native_point.x & 0xffff)|((native_point.y & 0xffff)<<16)
                    assert user32.SendMessageW(int(w.winId()),0x84,0,packed)==1
                    for _ in range(3):
                        QTest.mouseClick(w.windowHandle(),Qt.MouseButton.LeftButton,pos=point)
                        settle(30);assert w.more_menu.isVisible(),context
                        QTest.keyClick(w.more_menu,Qt.Key.Key_Escape);settle(15)
                        assert not w.more_menu.isVisible() and not w.more_button.isDown()
                    report.setdefault('native_menu_contexts',[]).append(context)
                    print('Caption menu passed:',context,flush=True)
                second=root/'second.pdf';second.write_bytes(source.read_bytes())
                w.open_pdf(second);settle()
                check_menu('two tabs')
                w.show_home();settle();check_menu('Home with tabs')
                w.resume_reading();settle()
                close_state=user32.GetMenuState(user32.GetSystemMenu(int(w.winId()),0),0xF060,0)
                assert close_state!=0xFFFFFFFF and not close_state & 3
                report['native_close_command_enabled']=True
                report['decorated_extended_client_area']=True
                def bounds():
                    # Observe automatic recovery; calling update_space here
                    # would hide a caption restored by a late native update.
                    settle()
                    assert bool(w.windowHandle().flags() & Qt.WindowType.WindowTitleHint)==(not w.isMaximized())
                    assert bool(w.windowHandle().flags() & Qt.WindowType.NoTitleBarBackgroundHint)==w.isMaximized()
                    assert bool(w.windowHandle().flags() & Qt.WindowType.ExpandedClientAreaHint)==w.isMaximized()
                    user32.FindWindowExW.argtypes=[wintypes.HWND,wintypes.HWND,wintypes.LPCWSTR,wintypes.LPCWSTR]
                    user32.FindWindowExW.restype=wintypes.HWND
                    overlays=[]
                    overlay=user32.FindWindowExW(int(w.winId()),None,'_q_titlebar',None)
                    while overlay:
                        overlays.append(overlay)
                        overlay=user32.FindWindowExW(int(w.winId()),overlay,'_q_titlebar',None)
                    assert len(overlays)==(1 if w.isMaximized() else 0),('Duplicate/stale Qt caption',w.isMaximized(),overlays)
                    report.setdefault('caption_overlay_counts',[]).append(dict(maximized=w.isMaximized(),count=len(overlays)))
                    height,reserve=w.caption_tabs.strip.minimumHeight(),w.tabstrip.layout().contentsMargins().right()
                    assert height>=32 and (reserve>=144 if w.isMaximized() else reserve==0)
                    origin=w.tabstrip.mapTo(w,QPoint())
                    tab_center=w.tabs.mapTo(w,w.tabs.tabRect(0).center())
                    safe_top=w.windowHandle().safeAreaMargins().top()
                    sample=dict(maximized=w.isMaximized(),tab_top=origin.y(),
                                tab_center=tab_center.y(),caption_height=safe_top,
                                window_top_margin=w.contentsMargins().top())
                    report.setdefault('caption_row_positions',[]).append(sample)
                    print('Caption row position:',sample,flush=True)
                    assert origin.y()==0 and w.contentsMargins().top()==0,sample
                    assert not w.testAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea)
                    if safe_top>0:assert 0<=tab_center.y()<safe_top,sample
                    end=w.add_tab_button.mapTo(w.tabstrip,QPoint(w.add_tab_button.width(),0)).x()
                    assert end<=w.tabstrip.width()-reserve
                    assert not w.grab().isNull() and not r.document().render(0,r.viewport().size()).isNull()
                def check_caption_pixels(context):
                    # QWidget.grab() omits Qt's separate layered caption HWND.
                    # Capture the composed desktop instead, excluding Windows'
                    # buttons whose active/inactive appearance should change.
                    reserve=w.tabstrip.layout().contentsMargins().right()
                    origin=w.tabstrip.mapToGlobal(QPoint(8,4))
                    width=w.tabstrip.width()-reserve-16
                    height=w.tabstrip.minimumHeight()-8
                    def capture():
                        pixmap=w.screen().grabWindow(0,origin.x(),origin.y(),width,height)
                        assert not pixmap.isNull(),'Desktop caption capture unavailable'
                        return pixmap.toImage()
                    w.raise_();w.activateWindow();settle()
                    before=capture()
                    for active in (0,1,0,1):
                        assert user32.SendMessageW(int(w.winId()),0x86,active,0)==1
                        settle(40)
                        after=capture()
                        assert before.size()==after.size()
                        changed=0
                        for y in range(before.height()):
                            for x in range(before.width()):
                                a,b=before.pixelColor(x,y),after.pixelColor(x,y)
                                if max(abs(a.red()-b.red()),abs(a.green()-b.green()),abs(a.blue()-b.blue()))>32:
                                    changed+=1
                        fraction=changed/(before.width()*before.height())
                        if fraction>=0.02:
                            before.save(str(output/'caption-before.png'))
                            after.save(str(output/'caption-overlap.png'))
                        assert fraction<0.02,(context,active,fraction)
                    report.setdefault('caption_activation_pixel_checks',[]).append(context)
                bounds()
                # Reproduce Qt 6.12's hidden-ancestor visibility mistake: a
                # still-visible-bit caption can survive a switch to native chrome.
                w.showMaximized();settle();bounds()
                stale=user32.FindWindowExW(int(w.winId()),None,'_q_titlebar',None)
                assert stale
                w.showNormal();settle();bounds()
                w.hide();settle()
                user32.SetParent.argtypes=[wintypes.HWND,wintypes.HWND]
                user32.SetParent.restype=wintypes.HWND
                user32.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
                user32.ShowWindow.restype=wintypes.BOOL
                user32.IsWindowVisible.argtypes=[wintypes.HWND]
                user32.IsWindowVisible.restype=wintypes.BOOL
                user32.SetParent(stale,int(w.winId()))
                user32.ShowWindow(stale,4) # SW_SHOWNOACTIVATE, ancestor stays hidden.
                assert not user32.IsWindowVisible(stale)
                w.caption_tabs.update_space()
                assert not user32.FindWindowExW(int(w.winId()),None,'_q_titlebar',None)
                w.show();settle();bounds()
                report['hidden_parent_stale_overlay_recovered']=True
                print('Hidden-parent Qt caption overlay recovered.',flush=True)
                check_caption_pixels('normal')
                # Use real OS pointer input. QTest mouse events and calling
                # showMinimized() do not exercise Windows caption buttons.
                class TitleBarInfo(ctypes.Structure):
                    _fields_=[('size',wintypes.DWORD),('rect',wintypes.RECT),
                              ('states',wintypes.DWORD*6),('buttons',wintypes.RECT*6)]
                class MouseInput(ctypes.Structure):
                    _fields_=[('dx',wintypes.LONG),('dy',wintypes.LONG),
                              ('data',wintypes.DWORD),('flags',wintypes.DWORD),
                              ('time',wintypes.DWORD),('extra',ctypes.c_size_t)]
                class Input(ctypes.Structure):
                    _fields_=[('kind',wintypes.DWORD),('mouse',MouseInput)]
                user32.SendInput.argtypes=[wintypes.UINT,ctypes.POINTER(Input),ctypes.c_int]
                user32.SendInput.restype=wintypes.UINT
                user32.SetCursorPos.argtypes=[ctypes.c_int,ctypes.c_int]
                user32.SetCursorPos.restype=wintypes.BOOL
                user32.IsZoomed.argtypes=[wintypes.HWND]
                user32.IsZoomed.restype=wintypes.BOOL
                user32.GetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int]
                user32.GetWindowLongW.restype=wintypes.LONG
                def native_state():
                    return dict(widget=w.windowState().value,native=w.windowHandle().windowStates().value,
                                zoomed=bool(user32.IsZoomed(int(w.winId()))),
                                flags=hex(int(w.windowHandle().flags())),
                                style=hex(user32.GetWindowLongW(int(w.winId()),-16)&0xffffffff))
                original_update=w.caption_tabs._update_space
                def trace_update():
                    before=native_state();original_update();after=native_state()
                    if before!=after:print('Caption reconciliation:',before,after,flush=True)
                w.caption_tabs._update_space=trace_update
                def click_native_button(index):
                    info=TitleBarInfo();info.size=ctypes.sizeof(info)
                    user32.SendMessageW(int(w.winId()),0x33f,0,ctypes.addressof(info))
                    rect=info.buttons[index]
                    assert rect.right>rect.left and rect.bottom>rect.top,(index,info.size)
                    x,y=(rect.left+rect.right)//2,(rect.top+rect.bottom)//2
                    packed=(x&0xffff)|((y&0xffff)<<16)
                    print('Native click before:',index,(x,y),int(info.states[index]),
                          user32.SendMessageW(int(w.winId()),0x84,0,packed),native_state(),flush=True)
                    assert user32.SetCursorPos(x,y)
                    values=(Input*2)()
                    values[0].mouse.flags=2 # MOUSEEVENTF_LEFTDOWN
                    values[1].mouse.flags=4 # MOUSEEVENTF_LEFTUP
                    # Queue both before pumping: native caption presses can
                    # enter a modal loop that waits for the release event.
                    assert user32.SendInput(2,values,ctypes.sizeof(Input))==2
                    settle()
                    print('Native click after:',index,native_state(),flush=True)
                for _ in range(2):
                    click_native_button(2)
                    assert w.isMinimized(),'Physical-input minimize button failed'
                    w.showNormal();settle();bounds()
                    click_native_button(3)
                    assert w.isMaximized(),'Physical-input maximize button failed'
                    bounds()
                    w.showNormal();settle();bounds()
                report['restored_native_buttons_real_pointer_input']=True
                app.sendEvent(w,QEvent(QEvent.Type.ThemeChange))
                w.windowHandle().setFlag(Qt.WindowType.WindowTitleHint,True)
                w.windowHandle().setFlag(Qt.WindowType.NoTitleBarBackgroundHint,False)
                bounds()
                check_menu('recovered caption')
                report['late_caption_normalization_recovered']=True
                w.resize(560,700);settle();bounds()
                w.grab().save(str(output/'caption-narrow.png'))
                w.screen().grabWindow(int(w.winId())).save(str(output/'caption-native-narrow.png'))
                w.showMaximized();settle();bounds()
                check_caption_pixels('maximized')
                report['normal_narrow_maximized_controls_fit']=True
                report['tabs_share_native_caption_row']=True
                w.grab().save(str(output/'caption-maximized.png'))
                w.screen().grabWindow(int(w.winId())).save(str(output/'caption-native-maximized.png'))
                w.change_theme('Dark');settle();bounds()
                check_caption_pixels('dark')
                w.grab().save(str(output/'caption-dark.png'))
                w.change_theme('Black');settle();bounds()
                w.grab().save(str(output/'caption-black.png'))
                w.change_theme('Sepia');settle()
                w.split(0,1);settle();check_menu('split PDFs')
                secondary=w.secondary
                secondary.setFocus();settle()
                # Exercise the same QWindow path used by Qt's extended-caption
                # Minimize button and the actual Windows system-menu command.
                # This is state/geometry automation, not a physical click claim.
                user32.IsIconic.argtypes=[wintypes.HWND]
                user32.IsIconic.restype=wintypes.BOOL
                user32.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
                user32.ShowWindow.restype=wintypes.BOOL
                user32.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
                user32.GetClientRect.restype=wintypes.BOOL
                def client_bounds():
                    rect=wintypes.RECT();origin=wintypes.POINT()
                    assert user32.GetClientRect(int(w.winId()),ctypes.byref(rect))
                    assert user32.ClientToScreen(int(w.winId()),ctypes.byref(origin))
                    return origin.x,origin.y,rect.right-rect.left,rect.bottom-rect.top
                for maximized in (False,True):
                    if maximized:w.showMaximized()
                    else:w.showNormal()
                    settle();bounds()
                    snapshots=w.visible_states()
                    before_normal=w.normalGeometry()
                    before_geometry=w.geometry()
                    before_native=w.window_effects.capture_bounds()
                    before_client=client_bounds()
                    for route in ('caption QWindow','system menu')*3:
                        if route=='caption QWindow':w.windowHandle().showMinimized()
                        else:user32.SendMessageW(int(w.winId()),0x112,0xF020,0) # WM_SYSCOMMAND / SC_MINIMIZE
                        settle()
                        assert w.isMinimized() and user32.IsIconic(int(w.winId())),route
                        # Explicit reconciliation must not undo native minimize.
                        w.caption_tabs.update_space();settle()
                        assert user32.IsIconic(int(w.winId())),route
                        from mellow.window_effects import WindowPlacement
                        placement=WindowPlacement();placement.length=ctypes.sizeof(placement)
                        assert w.window_effects.bounds_api().GetWindowPlacement(int(w.winId()),ctypes.byref(placement))
                        sample=dict(route=route,expected_maximized=maximized,
                                    show_command=placement.showCmd,placement_flags=placement.flags)
                        print('Minimized restore placement:',sample,flush=True)
                        report.setdefault('minimized_placements',[]).append(sample)
                        if maximized:assert placement.flags & 2,sample
                        user32.ShowWindow(int(w.winId()),9) # SW_RESTORE, as from taskbar
                        settle();bounds()
                        assert not w.isMinimized() and w.isMaximized()==maximized,route
                        print('Restored geometry:',route,dict(before_normal=before_normal.getRect(),
                              after_normal=w.normalGeometry().getRect(),before=before_geometry.getRect(),
                              after=w.geometry().getRect(),native_before=before_native,
                              native_after=w.window_effects.capture_bounds()),flush=True)
                        # Qt may refresh its cached invisible-border margins
                        # after the first native restore. Compare actual HWND
                        # client and outer bounds; the maximized Qt layout must
                        # also stay exact, per the owner's constraint.
                        if maximized:assert w.geometry()==before_geometry,route
                        assert w.window_effects.capture_bounds()==before_native,route
                        assert client_bounds()==before_client,route
                        for reader,state in snapshots:
                            after=reader.state()
                            assert after['anchor_page']==state['anchor_page'],route
                            assert abs(after['y']-state['y'])<2,route
                        check_menu(f'{route} restored, maximized={maximized}')
                        report.setdefault('minimize_restore',[]).append(dict(route=route,maximized=maximized))
                secondary.setFocus();settle()
                def dwm_value():
                    from ctypes import wintypes
                    try:
                        api=ctypes.WinDLL('dwmapi');value=wintypes.BOOL()
                        api.DwmGetWindowAttribute.argtypes=[wintypes.HWND,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD]
                        api.DwmGetWindowAttribute.restype=ctypes.c_long
                        if api.DwmGetWindowAttribute(int(w.winId()),3,ctypes.byref(value),ctypes.sizeof(value))==0:return int(value.value)
                    except (OSError,AttributeError):pass
                    return None
                original_dwm=dwm_value()
                maximized_geometry=w.geometry()
                maximized_native=w.window_effects.capture_bounds()
                maximized_client=client_bounds()
                def transition():
                    started=time.perf_counter();w.fullscreen()
                    while w._fullscreen_snapshots is not None and time.perf_counter()-started<2:settle(5)
                    assert w._fullscreen_snapshots is None and w.updatesEnabled()
                    assert w._root_layout.isEnabled() and w.window_effects._restore is None
                    if original_dwm is not None:assert dwm_value()==original_dwm
                    report.setdefault('fullscreen_settle_ms',[]).append(round((time.perf_counter()-started)*1000,3))
                transition();w.show_chrome();settle()
                assert w.tabstrip.layout().contentsMargins().right()==0
                assert not w.windowHandle().flags() & Qt.WindowType.ExpandedClientAreaHint
                get_style=ctypes.windll.user32.GetWindowLongW
                get_style.argtypes=[ctypes.c_void_p,ctypes.c_int]
                get_style.restype=ctypes.c_long
                assert not get_style(int(w.winId()),-16) & (0x00C00000 | 0x00040000)
                assert w.secondary is secondary
                transition();bounds()
                assert w.isMaximized() and w.active is secondary
                assert w.window_effects.capture_bounds()==maximized_native
                assert client_bounds()==maximized_client
                assert w.windowHandle().flags() & Qt.WindowType.ExpandedClientAreaHint
                report['fullscreen_split_exit_restores_caption_space']=True
                w.showNormal();settle()
                normal=w.geometry()
                normal_native=w.window_effects.capture_bounds()
                normal_client=client_bounds()
                for _ in range(2):
                    transition();transition()
                    actual=w.geometry()
                    sample=dict(expected=normal.getRect(),actual=actual.getRect(),
                                expected_native=normal_native,actual_native=w.window_effects.capture_bounds(),
                                secondary_active=w.active is secondary,
                                maximized=w.isMaximized(),fullscreen=w.isFullScreen())
                    report.setdefault('normal_roundtrips',[]).append(sample)
                    print('Normal fullscreen roundtrip:',sample,flush=True)
                    assert w.active is secondary,sample
                    assert client_bounds()==normal_client,sample
                    if normal_native is None:assert actual==normal,sample
                    if normal_native is not None:assert sample['actual_native']==normal_native,sample
                report['repeated_normal_geometry_and_focus']=True
                report['dwm_original_attribute_restored']=original_dwm is not None
                # Qt's caption backend must leave an actual tab operable.
                QTest.mouseClick(w.tabs,Qt.MouseButton.LeftButton,pos=w.tabs.tabRect(0).center())
                settle();assert w.tabs.currentIndex()==0
                report['tab_click_and_pdf_render']=True
                w.show_home();settle()
                assert w.home.opened.isVisible() and not w.add_tab_button.isVisible()
                assert w.more_button.isVisible() and w.brand_mark.isVisible()
                w.resume_reading();settle()
                assert w.add_tab_button.isVisible()
                report['home_single_opener_and_header_controls']=True
                report['limitations']='Windows CI geometry/render checks only; physical Snap hover, touchpads, screen readers and mixed-DPI monitors require interactive testing.'
        except BaseException as error:
            report['status']='failed'
            report['error']=f'{type(error).__name__}: {error}'
            raise
        else:
            report['status']='passed'
        finally:
            (output/'CAPTION.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('Windows caption platform checks passed.')


if __name__=='__main__':main()
