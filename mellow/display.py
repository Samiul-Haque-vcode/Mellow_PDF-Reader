"""Restore logical window bounds on available screens without off-screen chrome."""
from PySide6.QtCore import QRect


def screen_records(screens):
    return [dict(name=screen.name(),available=screen.availableGeometry(),dpi=screen.logicalDotsPerInch()) for screen in screens]


def window_record(window):
    screen=window.screen();rect=window.normalGeometry()
    if not rect.isValid():rect=window.geometry()
    return dict(rect=[rect.x(),rect.y(),rect.width(),rect.height()],screen=screen.name(),
                available=[screen.availableGeometry().x(),screen.availableGeometry().y(),screen.availableGeometry().width(),screen.availableGeometry().height()],
                maximized=window.isMaximized() or (window.isFullScreen() and window._fullscreen_was_maximized))


def restored_bounds(saved,screens):
    if not screens:return None
    try:
        rect=QRect(*map(int,saved['rect']))
        old=QRect(*map(int,saved.get('available',saved['rect'])))
    except (KeyError,TypeError,ValueError,OverflowError):return None
    if not rect.isValid():return None
    target=next((screen for screen in screens if screen['name']==saved.get('screen')),None)
    if target is None:target=max(screens,key=lambda screen:rect.intersected(screen['available']).width()*max(0,rect.intersected(screen['available']).height()))
    available=target['available']
    width=min(available.width(),max(min(640,available.width()),rect.width()))
    height=min(available.height(),max(min(440,available.height()),rect.height()))
    if old!=available:
        fx=(rect.x()-old.x())/max(1,old.width()-rect.width())
        fy=(rect.y()-old.y())/max(1,old.height()-rect.height())
        x=available.x()+round(max(0,min(1,fx))*(available.width()-width))
        y=available.y()+round(max(0,min(1,fy))*(available.height()-height))
    else:x,y=rect.x(),rect.y()
    return QRect(max(available.left(),min(x,available.right()-width+1)),
                 max(available.top(),min(y,available.bottom()-height+1)),width,height)
