"""Native window bounds, transition animation and minimized restore placement."""
import ctypes
import math
import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


class WindowPlacement(ctypes.Structure):
    # Win32 DWORD/UINT/LONG remain 32-bit in both x86 and x64 processes.
    _fields_=[('length',ctypes.c_uint32),('flags',ctypes.c_uint32),
              ('showCmd',ctypes.c_uint32),('ptMinPosition',ctypes.c_int32*2),
              ('ptMaxPosition',ctypes.c_int32*2),('rcNormalPosition',ctypes.c_int32*4)]


class WindowEffects:
    def __init__(self, window):
        self.window=window
        self._restore=None
        self._api=None
        self._user32=None

    def bounds_api(self):
        if sys.platform!='win32' or QApplication.platformName()!='windows':return None
        if self._user32 is None:
            from ctypes import wintypes
            api=ctypes.WinDLL('user32')
            api.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
            api.GetWindowRect.restype=wintypes.BOOL
            api.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,
                                      ctypes.c_int,ctypes.c_int,wintypes.UINT]
            api.SetWindowPos.restype=wintypes.BOOL
            api.GetWindowPlacement.argtypes=[wintypes.HWND,ctypes.POINTER(WindowPlacement)]
            api.GetWindowPlacement.restype=wintypes.BOOL
            api.SetWindowPlacement.argtypes=[wintypes.HWND,ctypes.POINTER(WindowPlacement)]
            api.SetWindowPlacement.restype=wintypes.BOOL
            self._user32=api
        return self._user32

    def retain_maximized_restore(self):
        """Qt caption minimize loses the Maximize bit; retain Windows' restore target.

        Only alter an already minimized placement, after native state handling.
        Keep its normal rectangle, show command, activation and all other flags.
        """
        try:
            api=self.bounds_api()
            if api is None:return False
            placement=WindowPlacement()
            placement.length=ctypes.sizeof(placement)
            hwnd=int(self.window.winId())
            if not api.GetWindowPlacement(hwnd,ctypes.byref(placement)):return False
            if placement.showCmd!=2:return False # SW_SHOWMINIMIZED
            if placement.flags & 2:return True # WPF_RESTORETOMAXIMIZED
            placement.flags |= 2
            return bool(api.SetWindowPlacement(hwnd,ctypes.byref(placement)))
        except (OSError,AttributeError):return False

    def refresh_caption(self,height):
        """Request one native top-strip paint, without erasing/moving the window."""
        try:
            from ctypes import wintypes
            api=self.bounds_api()
            if api is None:return False
            invalidate=api.InvalidateRect
            invalidate.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT),wintypes.BOOL]
            invalidate.restype=wintypes.BOOL
            ratio=self.window.devicePixelRatioF()
            rect=wintypes.RECT(0,0,math.ceil(self.window.width()*ratio),math.ceil(height*ratio))
            return bool(invalidate(int(self.window.winId()),ctypes.byref(rect),False))
        except (OSError,AttributeError):return False

    def hide_extended_caption(self):
        """Remove Qt's leftover layered caption in ordinary-title-bar mode.

        Qt 6.12 skips hiding/detaching its _q_titlebar child when the parent
        is hidden, because IsWindowVisible(child) is then false even if the
        child's WS_VISIBLE bit remains set. It resurfaces on the next restore.
        Only detach this window's own Qt caption, as Qt itself does on flag
        changes; maximizing can reattach the same HWND normally.
        """
        try:
            from ctypes import wintypes
            api=self.bounds_api()
            if api is None:return False
            api.FindWindowExW.argtypes=[wintypes.HWND,wintypes.HWND,wintypes.LPCWSTR,wintypes.LPCWSTR]
            api.FindWindowExW.restype=wintypes.HWND
            api.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
            api.ShowWindow.restype=wintypes.BOOL
            api.SetParent.argtypes=[wintypes.HWND,wintypes.HWND]
            api.SetParent.restype=wintypes.HWND
            parent=int(self.window.winId())
            child=api.FindWindowExW(parent,None,'_q_titlebar',None)
            hidden=False
            while child:
                following=api.FindWindowExW(parent,child,'_q_titlebar',None)
                # Do not gate this on IsWindowVisible: a hidden/minimizing
                # ancestor is exactly what makes Qt's own check unreliable.
                api.ShowWindow(child,0) # SW_HIDE: clear the child's visible bit.
                api.SetParent(child,wintypes.HWND(-3)) # HWND_MESSAGE, matching Qt.
                hidden=True
                child=following
            return hidden
        except (OSError,AttributeError):return False

    def set_caption_flags(self,handle,flags):
        """Keep a native maximize across Qt's caption-style replacement.

        Qt rebuilds WS_* styles when flags change and retains only visibility
        and enabled state. A real caption-button maximize can therefore lose
        WS_MAXIMIZE while we switch from the ordinary to extended caption.
        """
        placement=None;api=None
        try:
            # This correction is only for the restored -> maximized caption
            # switch. Keep existing fullscreen/extended-caption behavior.
            api=(self.bounds_api() if flags & Qt.WindowType.ExpandedClientAreaHint
                 and handle.flags() & Qt.WindowType.WindowTitleHint
                 and not handle.flags() & Qt.WindowType.ExpandedClientAreaHint else None)
            if api is not None:
                current=WindowPlacement();current.length=ctypes.sizeof(current)
                if api.GetWindowPlacement(int(self.window.winId()),ctypes.byref(current)) and current.showCmd==3:
                    placement=current
        except (OSError,AttributeError):pass
        handle.setFlags(flags)
        if placement is not None:
            api.SetWindowPlacement(int(self.window.winId()),ctypes.byref(placement))

    def capture_bounds(self):
        """Keep physical outer bounds independent of Qt's changing frame margins."""
        try:
            from ctypes import wintypes
            api=self.bounds_api()
            if api is None:return None
            rect=wintypes.RECT()
            if api.GetWindowRect(int(self.window.winId()),ctypes.byref(rect)):
                return (rect.left,rect.top,rect.right-rect.left,rect.bottom-rect.top)
        except (OSError,AttributeError):pass
        return None

    def restore_bounds(self,bounds):
        if bounds is None:return False
        try:
            api=self.bounds_api()
            if api is None:return False
            if self.capture_bounds()==bounds:return True
            # SWP_NOZORDER | SWP_NOACTIVATE: do not steal foreground activation.
            return bool(api.SetWindowPos(int(self.window.winId()),None,*bounds,0x14))
        except (OSError,AttributeError):return False

    def begin(self):
        self.finish()
        if sys.platform!='win32' or QApplication.platformName()!='windows':return
        try:
            from ctypes import wintypes
            api=self._api
            if api is None:
                api=ctypes.WinDLL('dwmapi')
                args=[wintypes.HWND,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD]
                api.DwmGetWindowAttribute.argtypes=args
                api.DwmGetWindowAttribute.restype=ctypes.c_long
                api.DwmSetWindowAttribute.argtypes=args
                api.DwmSetWindowAttribute.restype=ctypes.c_long
                self._api=api
            hwnd=int(self.window.winId())
            previous=wintypes.BOOL()
            if api.DwmGetWindowAttribute(hwnd,3,ctypes.byref(previous),ctypes.sizeof(previous))!=0:return
            disabled=wintypes.BOOL(True)
            if api.DwmSetWindowAttribute(hwnd,3,ctypes.byref(disabled),ctypes.sizeof(disabled))==0:
                self._restore=(api,hwnd,previous)
        except (OSError,AttributeError):
            pass

    def finish(self):
        saved,self._restore=self._restore,None
        if saved:
            api,hwnd,previous=saved
            api.DwmSetWindowAttribute(hwnd,3,ctypes.byref(previous),ctypes.sizeof(previous))
