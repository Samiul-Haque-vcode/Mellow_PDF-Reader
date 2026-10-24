"""Dismissible Mellow dialogs; child pickers retain their own interaction."""
from PySide6.QtCore import Qt,QEvent,QEventLoop
from PySide6.QtWidgets import QApplication,QDialog,QWidget,QInputDialog,QLineEdit
from shiboken6 import isValid


class OutsideDismissal:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._outside_filter=False

    def _child_window(self,widget):
        # QWidget.isAncestorOf stops at native child-window boundaries.
        # QObject ownership also covers dialogs and combo popup windows.
        while widget is not None:
            if widget is self:return True
            widget=widget.parent()
        return False

    def showEvent(self,event):
        super().showEvent(event)
        self._outside_filter=True
        QApplication.instance().installEventFilter(self)

    def hideEvent(self,event):
        self._outside_filter=False
        QApplication.instance().removeEventFilter(self)
        super().hideEvent(event)

    def eventFilter(self,obj,event):
        if self._outside_filter:
            if event.type() in (QEvent.Type.MouseButtonPress,QEvent.Type.NonClientAreaMouseButtonPress) and isinstance(obj,QWidget):
                # A combo menu, file picker or confirmation may extend beyond
                # this window. Errors may also be owned by the main window;
                # their input must never discard the pending dialog edits.
                if self._child_window(obj):return super().eventFilter(obj,event)
                if QApplication.activeModalWidget() is not None or QApplication.activePopupWidget() is not None:
                    return super().eventFilter(obj,event)
                if not self.frameGeometry().contains(event.globalPosition().toPoint()):
                    self.reject()
                    return True  # dismiss without activating the control below
            elif event.type()==QEvent.Type.Close and obj is self.parentWidget():
                self.reject()
            elif event.type()==QEvent.Type.ApplicationDeactivate:
                if QApplication.activeModalWidget() is None and QApplication.activePopupWidget() is None:
                    self.reject()
        return super().eventFilter(obj,event)

    def exec(self):
        # QDialog.exec makes the window modal, so Windows discards clicks on
        # the reader before an outside-click filter can see them. Keep the
        # synchronous result contract but show a nonmodal window instead.
        self.setWindowModality(Qt.WindowModality.NonModal)
        loop=QEventLoop()
        self.finished.connect(loop.quit)
        self.destroyed.connect(loop.quit)
        self.show()
        loop.exec()
        if not isValid(self):return QDialog.DialogCode.Rejected
        self.finished.disconnect(loop.quit)
        self.destroyed.disconnect(loop.quit)
        return self.result()


class DismissibleDialog(OutsideDismissal,QDialog):
    pass


class DismissibleInputDialog(OutsideDismissal,QInputDialog):
    @classmethod
    def getText(cls,parent,title,label,echo=QLineEdit.EchoMode.Normal,text=''):
        dialog=cls(parent)
        dialog.setWindowTitle(title);dialog.setLabelText(label)
        dialog.setInputMode(QInputDialog.InputMode.TextInput)
        dialog.setTextEchoMode(echo);dialog.setTextValue(text)
        accepted=dialog.exec()==QDialog.DialogCode.Accepted
        value=dialog.textValue();dialog.deleteLater()
        return value,accepted

    @classmethod
    def getDouble(cls,parent,title,label,value=0,minimum=-2147483647,maximum=2147483647,decimals=1):
        dialog=cls(parent)
        dialog.setWindowTitle(title);dialog.setLabelText(label)
        dialog.setInputMode(QInputDialog.InputMode.DoubleInput)
        dialog.setDoubleDecimals(decimals);dialog.setDoubleRange(minimum,maximum);dialog.setDoubleValue(value)
        accepted=dialog.exec()==QDialog.DialogCode.Accepted
        value=dialog.doubleValue();dialog.deleteLater()
        return value,accepted

    @classmethod
    def getInt(cls,parent,title,label,value=0,minimum=-2147483647,maximum=2147483647):
        dialog=cls(parent)
        dialog.setWindowTitle(title);dialog.setLabelText(label)
        dialog.setInputMode(QInputDialog.InputMode.IntInput)
        dialog.setIntRange(minimum,maximum);dialog.setIntValue(value)
        accepted=dialog.exec()==QDialog.DialogCode.Accepted
        value=dialog.intValue();dialog.deleteLater()
        return value,accepted
