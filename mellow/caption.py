"""Optional Windows caption tabs using Qt's decorated extended client area.

No frameless flag, replacement caption buttons or polling loop. The platform
backend owns non-client hit testing and system-window actions.
"""
import math
import sys
from PySide6.QtCore import Qt, QObject, QEvent,QTimer,QPoint
from shiboken6 import isValid
from PySide6.QtWidgets import QApplication, QTabBar,QToolButton,QAbstractButton

CAPTION_CONTROLS=(Qt.WindowType.CustomizeWindowHint |
                  Qt.WindowType.WindowSystemMenuHint |
                  Qt.WindowType.WindowMinimizeButtonHint |
                  Qt.WindowType.WindowMaximizeButtonHint |
                  Qt.WindowType.WindowCloseButtonHint)


def native_flags(flags, fullscreen=False):
    # Use integer complements: enum/QFlags inversion masks differ between
    # bindings/platforms and can discard high bits such as Close/Customize.
    value=(int(flags) | int(CAPTION_CONTROLS) |
           int(Qt.WindowType.NoTitleBarBackgroundHint)) & ~int(Qt.WindowType.WindowTitleHint)
    if fullscreen:
        value &= ~int(Qt.WindowType.ExpandedClientAreaHint)
    else:
        value |= int(Qt.WindowType.ExpandedClientAreaHint)
    return Qt.WindowType(value)


def restored_flags(flags):
    """Let Windows own the ordinary caption in a smaller, resizable window."""
    value=int(flags) | int(CAPTION_CONTROLS) | int(Qt.WindowType.WindowTitleHint)
    value &= ~int(Qt.WindowType.ExpandedClientAreaHint | Qt.WindowType.NoTitleBarBackgroundHint)
    return Qt.WindowType(value)


def supported():
    return (sys.platform == 'win32' and QApplication.platformName() == 'windows'
            and hasattr(Qt.WindowType, 'ExpandedClientAreaHint'))


def caption_space(top=32, right=0, fullscreen=False):
    if fullscreen:
        return 0, 0
    # Qt's Windows backend reserves three caption buttons, each 1.5 times
    # the system title height. safeAreaMargins currently reports only top.
    height=max(32, top)
    return height, max(right, math.ceil(height*4.5)+8)


class DocumentTabs(QTabBar):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setUsesScrollButtons(True)
        self.setElideMode(Qt.TextElideMode.ElideRight)

    def tabSizeHint(self,index):
        size=super().tabSizeHint(index)
        size.setWidth(min(220,size.width()))
        return size

    def mousePressEvent(self, event):
        if self.tabAt(event.position().toPoint()) < 0:
            event.ignore()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.tabAt(event.position().toPoint()) < 0:
            event.ignore()
            return
        super().mouseDoubleClickEvent(event)


class CaptionMenuButton(QToolButton):
    """Open after release, outside Windows' synchronous caption hit testing."""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.pending=QTimer(self)
        self.pending.setSingleShot(True)
        self.pending.timeout.connect(self.open_popup)
        self.clicked.connect(self.queue_popup)
        self._pressed=False
    def queue_popup(self):
        if not self.pending.isActive():self.pending.start(0)
    def open_popup(self):
        menu=self.menu()
        if menu is not None and not menu.isVisible() and self.isVisible():
            self.setDown(True)
            menu.popup(self.mapToGlobal(QPoint(0,self.height())))
    def setMenu(self,menu):
        previous=self.menu()
        if previous is not None and previous is not menu:previous.aboutToHide.disconnect(self.release_button)
        super().setMenu(menu)
        if menu is not None and previous is not menu:menu.aboutToHide.connect(self.release_button)
    def release_button(self):self.setDown(False)
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self._pressed=True
            self.setDown(True)
            event.accept()
        else:super().mousePressEvent(event)
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            pressed,self._pressed=self._pressed,False
            self.setDown(False)
            if pressed and self.rect().contains(event.position().toPoint()):self.queue_popup()
            event.accept()
        else:super().mouseReleaseEvent(event)
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Space,Qt.Key.Key_Return,Qt.Key.Key_Enter,Qt.Key.Key_Down):
            self.queue_popup();event.accept()
        else:super().keyPressEvent(event)
    def keyReleaseEvent(self,event):
        if event.key() in (Qt.Key.Key_Space,Qt.Key.Key_Return,Qt.Key.Key_Enter,Qt.Key.Key_Down):event.accept()
        else:super().keyReleaseEvent(event)


class CaptionTabs(QObject):
    def __init__(self, window, strip, enabled=False):
        super().__init__(window)
        self.window, self.strip = window, strip
        self.enabled=bool(enabled and supported())
        self.connected_handle=None
        self._updating=False
        self._transition_fullscreen=None
        self._minimized_from_maximized=False
        self._redraw_caption=True
        self._state_pending=False
        # QWidget can synchronize its normalized decoration flags back to the
        # platform window after our Show handler, restoring WindowTitleHint.
        # Reconcile once after such events, never from a paint/hit-test loop.
        self.reconcile=QTimer(self)
        self.reconcile.setSingleShot(True)
        self.reconcile.timeout.connect(self.reconcile_state)
        if self.enabled:
            # The tabs deliberately occupy the caption's safe area. Otherwise
            # QWidget adds that entire title height above QMainWindow's layout,
            # putting the tabs below the controls despite ExpandedClientAreaHint.
            # Keep our explicit right-hand reservation for caption buttons.
            window.setAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea,False)
            # Keep QWidget's maximized-caption setup identical to 0.27.2.
            # Only the platform QWindow changes to an ordinary caption while
            # restored; this avoids changing the maximized layout's metrics.
            window.setWindowFlags(native_flags(window.windowFlags()))
            window.installEventFilter(self)
        self.update_space()

    def extended_caption(self):
        if self._transition_fullscreen is not None:
            return (not self._transition_fullscreen and
                    bool(getattr(self.window,'_fullscreen_was_maximized',False)))
        handle=self.window.windowHandle()
        return not self.window.isFullScreen() and (self.window.isMaximized() or
                (handle is not None and bool(handle.windowStates() & Qt.WindowState.WindowMaximized)))

    def desired_flags(self,flags,fullscreen):
        return native_flags(flags,fullscreen) if fullscreen or self.extended_caption() else restored_flags(flags)

    def interactive_at(self,point):
        """Only real header controls claim client input; empty space still drags."""
        if not self.enabled or not self.extended_caption():return False
        local=self.strip.mapFrom(self.window,point)
        if not self.strip.rect().contains(local):return False
        # Never turn the system-button region into HTCLIENT, even when a
        # crowded/re-laying-out child temporarily extends into that region.
        reserve=self.strip.layout().contentsMargins().right()
        if local.x()>=self.strip.width()-reserve:return False
        child=self.window.childAt(point)
        while child is not None and child is not self.strip:
            if isinstance(child,QAbstractButton):return True
            if isinstance(child,QTabBar):return child.tabAt(child.mapFrom(self.window,point))>=0
            child=child.parentWidget()
        return False

    def native_hit_test(self,message):
        if not self.enabled or sys.platform!='win32':return None
        import ctypes
        from ctypes import wintypes
        msg=wintypes.MSG.from_address(int(message))
        if msg.message==0x86:  # WM_NCACTIVATE
            handle=self.window.windowHandle()
            if (self._transition_fullscreen is None and not self.window.isFullScreen() and handle is not None and
                    handle.flags() & Qt.WindowType.ExpandedClientAreaHint):
                # DefWindowProc can paint a classic white/blue caption over
                # the extended client area on activation. Qt suppresses this
                # for frameless windows, but not for extended-caption ones.
                # Follow the frame flags actually installed, including the
                # interval before QWidget/QWindow agree on their new state.
                # TRUE permits deactivation while skipping that default paint.
                self._redraw_caption=True
                self.queue_reconcile()
                return 1
        if msg.message!=0x84 or not self.extended_caption():return None  # WM_NCHITTEST
        x=ctypes.c_short(msg.lParam & 0xffff).value
        y=ctypes.c_short((msg.lParam>>16) & 0xffff).value
        point=wintypes.POINT(x,y)
        api=self.window.window_effects.bounds_api()
        if api is None:return None
        api.ScreenToClient.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
        api.ScreenToClient.restype=wintypes.BOOL
        if not api.ScreenToClient(int(self.window.winId()),ctypes.byref(point)):return None
        dpr=self.window.devicePixelRatioF()
        if self.interactive_at(QPoint(round(point.x/dpr),round(point.y/dpr))):return 1 # HTCLIENT
        return None

    def update_space(self, *_):
        if not self.enabled or self._updating or getattr(self.window,'_closing',False):
            return
        if self._state_pending and self._transition_fullscreen is None:
            return
        handle=self.window.windowHandle()
        if self.window.isMinimized() or (handle is not None and handle.windowStates() & Qt.WindowState.WindowMinimized):
            # Qt's extended-caption buttons minimize the QWindow first. While
            # QWidget catches up, changing flags can re-show its titlebar child
            # or alter the frame in the middle of the native minimize operation.
            if self._minimized_from_maximized:
                self.window.window_effects.retain_maximized_restore()
            return
        if handle is not None and self._transition_fullscreen is None:
            # Native caption actions update QWindow and QWidget separately.
            # Do not rebuild the frame using a mixture of old/new states.
            # The second state notification or exposure schedules reconciliation;
            # this path must never spin a zero-timer while a window is hidden.
            relevant=Qt.WindowState.WindowMaximized | Qt.WindowState.WindowFullScreen
            if self.window.windowState() & relevant != handle.windowStates() & relevant:
                self._redraw_caption=True
                return
        self._updating=True
        try:
            self._update_space()
        finally:
            self._updating=False

    def _update_space(self):
        if self.window.testAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea):
            self.window.setAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea,False)
        fullscreen=self.window.isFullScreen() if self._transition_fullscreen is None else self._transition_fullscreen
        handle=self.window.windowHandle()
        top, right=32, 0
        if handle is not None:
            # Qt's Windows extended-caption layer is independent of the
            # ordinary fullscreen frame. Disable that layer in fullscreen.
            # QWidget and the platform QWindow can normalize decoration flags
            # differently. Explicitly retain all controls on the actual window
            # instead of inheriting a potentially normalized-away Close hint.
            flags=self.desired_flags(handle.flags(),fullscreen)
            # QWidget adds WindowTitleHint back when system-menu/buttons are
            # requested. QWindow accepts the precise native decoration flags.
            if flags != handle.flags():
                self.window.window_effects.set_caption_flags(handle,flags)
                self._redraw_caption=True
            margins=handle.safeAreaMargins()
            top, right=margins.top(), margins.right()
            if handle is not self.connected_handle:
                previous=self.connected_handle
                if previous is not None and isValid(previous):
                    previous.removeEventFilter(self)
                    previous.safeAreaMarginsChanged.disconnect(self.update_space)
                handle.safeAreaMarginsChanged.connect(self.update_space)
                handle.installEventFilter(self)
                self.connected_handle=handle
        height, reserve=caption_space(top, right, fullscreen)
        if not fullscreen and not self.extended_caption():
            height,reserve=32,0
            self._redraw_caption=False
            self.window.window_effects.hide_extended_caption()
        margins=self.strip.layout().contentsMargins()
        if (margins.left(),margins.top(),margins.right(),margins.bottom())!=(4,0,reserve,0):
            self.strip.layout().setContentsMargins(4, 0, reserve, 0)
        if self.strip.minimumHeight()!=height:self.strip.setMinimumHeight(height)
        if (self._redraw_caption and handle is not None and self.window.isVisible()
                and self.window.updatesEnabled() and self.extended_caption() and not fullscreen):
            self._redraw_caption=False
            # Qt paints its extended caption into a separate layered HWND.
            # Correct flags alone can leave the old title/icon bitmap covering
            # our tabs until the next native paint or non-client hit test.
            self.window.window_effects.refresh_caption(height)

    def queue_reconcile(self):
        if self.enabled and not getattr(self.window,'_closing',False) and not self.reconcile.isActive():
            self.reconcile.start(0)

    def reconcile_state(self):
        self._state_pending=False
        self.update_space()

    def prepare_fullscreen(self,fullscreen=True):
        if self.enabled:
            # Change decoration flags before Qt removes Windows frame styles
            # for fullscreen. Changing flags afterward can reapply those styles.
            self._transition_fullscreen=fullscreen
            self.update_space()

    def finish_transition(self):
        if self._transition_fullscreen is not None:
            self._transition_fullscreen=None
            self.update_space()

    def eventFilter(self, obj, event):
        kind=event.type()
        if obj is self.window and kind==QEvent.Type.Hide and getattr(self.window,'_closing',False):
            self.reconcile.stop()
        if kind==QEvent.Type.WindowStateChange:
            self._state_pending=True
            self._redraw_caption=True
            # Let Qt complete minimize/maximize/restore before touching flags.
            # Observe both QWidget and QWindow: native caption buttons act on
            # the latter, and their state notifications arrive separately.
            handle=self.window.windowHandle()
            minimized=self.window.isMinimized() or (handle is not None and handle.windowStates() & Qt.WindowState.WindowMinimized)
            if minimized:
                if event.oldState() & Qt.WindowState.WindowMaximized:
                    self._minimized_from_maximized=True
            else:self._minimized_from_maximized=False
            self.queue_reconcile()
        elif obj is self.connected_handle and kind==QEvent.Type.Expose:
            # Restoring can repaint after QWidget's one-shot Show/State event.
            # Recover late title-flag normalization without an idle polling loop.
            fullscreen=self.window.isFullScreen() if self._transition_fullscreen is None else self._transition_fullscreen
            if obj.isExposed() and (self._redraw_caption or self.desired_flags(obj.flags(),fullscreen)!=obj.flags() or
                    not self.extended_caption() or
                    self.window.testAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea)):
                self.queue_reconcile()
        elif kind in (QEvent.Type.Show,
                            QEvent.Type.DevicePixelRatioChange,
                            QEvent.Type.WinIdChange,QEvent.Type.StyleChange,
                            QEvent.Type.PaletteChange,QEvent.Type.ThemeChange,
                            QEvent.Type.WindowTitleChange):
            self._redraw_caption=True
            self.update_space()
            self.queue_reconcile()
        return False
