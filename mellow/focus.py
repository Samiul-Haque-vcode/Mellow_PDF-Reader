"""Explicit keyboard return paths; outside-click dismissal never steals focus."""
from PySide6.QtCore import Qt
from shiboken6 import isValid


def restore_focus(widget):
    if widget is not None and isValid(widget) and widget.isVisible() and widget.isEnabled():
        widget.window().activateWindow()
        widget.setFocus(Qt.FocusReason.OtherFocusReason)


def owns(dialog,widget):
    from PySide6.QtWidgets import QWidget
    # Child menus, combo popups and native/modal pickers own their Escape.
    return isinstance(widget,QWidget) and widget.window() is dialog
