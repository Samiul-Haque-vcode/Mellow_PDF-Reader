"""Two-point selection and cancellable text-only copying on the GUI thread."""
from PySide6.QtCore import Qt,QObject,QTimer,QEvent
from PySide6.QtGui import QCursor,QKeySequence
from PySide6.QtWidgets import QApplication,QMenu,QToolTip,QProgressDialog
from shiboken6 import isValid
from .selection import TextSelection


class SelectionCopy(QObject):
    def __init__(self,reader,joined):
        super().__init__(reader)
        self.reader=reader
        self.document=reader.document()
        self.selection=TextSelection(self.document)
        self.selection.ranges=dict(reader.text_selection.ranges)
        self.pages=iter(sorted(self.selection.ranges))
        self.joined=joined
        self.chunks=[]
        self.done=False
        self.publishing=False
        self.clipboard=QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.clipboard_changed)
        self.count=0
        self.progress=QProgressDialog('Preparing selected text…','Cancel',0,len(self.selection.ranges),reader.window())
        self.progress.setWindowModality(Qt.WindowModality.NonModal)
        self.progress.setMinimumDuration(300)
        self.progress.setAutoClose(False)
        self.progress.setAutoReset(False)
        self.progress.canceled.connect(self.cancel)
        self.timer=QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.step)
        self.timer.start(0)

    def step(self):
        if self.done:return
        if not isValid(self.reader) or self.reader.document() is not self.document:
            self.cancel();return
        page=next(self.pages,None)
        if page is None:
            text=('\n\n' if self.joined else '\n').join(self.chunks)
            if text:
                self.publishing=True
                self.clipboard.setText(text)
                self.publishing=False
                self.reader.selection_hint('Selected text copied.')
            else:self.reader.selection_hint('No selectable text was found. Scanned PDFs may have no text layer.')
            self.finish();return
        try:
            text=self.selection.page_text(page,self.joined)
        except Exception:
            self.reader.selection_hint('Could not copy this selection. The clipboard was kept unchanged.')
            self.cancel();return
        if text:self.chunks.append(text)
        self.count+=1
        self.progress.setValue(self.count)
        if not self.done:self.timer.start(0)

    def clipboard_changed(self):
        if not self.publishing:self.cancel()

    def cancel(self):self.finish()
    def finish(self):
        if self.done:return
        self.done=True
        self.timer.stop()
        self.clipboard.dataChanged.disconnect(self.clipboard_changed)
        app=QApplication.instance()
        if getattr(app,'_mellow_copy_job',None) is self:app._mellow_copy_job=None
        self.chunks.clear()
        self.selection.set_document(None)
        self.document=None
        self.progress.close();self.progress.deleteLater()
        if isValid(self.reader) and self.reader._copy_job is self:self.reader._copy_job=None
        self.deleteLater()


class SelectionControls:
    def setup_selection_controls(self):
        self._two_point_mode=None
        self._point_release=False
        self._point_popup_position=None
        self._copy_popup=None
        self._copy_job=None
        self._selection_generation=0
        self.selection_message=''

    def selection_hint(self,message):
        self.selection_message=message
        self.viewport().setAccessibleDescription(message)
        QToolTip.showText(QCursor.pos(),message,self.viewport())

    def cancel_selection_work(self):
        self._selection_generation+=1
        self._two_point_mode=None
        self._point_release=False
        self._point_popup_position=None
        if self._copy_job:self._copy_job.cancel()
        popup,self._copy_popup=self._copy_popup,None
        if popup is not None and isValid(popup):popup.close();popup.deleteLater()
        self.viewport().unsetCursor()

    def start_point_selection(self):
        self.clear_selection()
        self._two_point_mode='start'
        self._selection_timer.stop();self._left_down=False
        self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.selection_hint('Click the starting text, scroll, then click the ending text. Esc cancels.')

    def point_selection_click(self,event):
        self._point_release=True
        hit=self.point_on_page(event.position())
        index=self.text_selection.caret(*hit,near_only=True) if hit else None
        if index is None:
            self.selection_hint('Click selectable text. Scanned pages may have no text layer.')
        elif self._two_point_mode=='start':
            self.text_selection.begin(*hit)
            self._two_point_mode='end'
            self.selection_hint('Scroll to the ending text and click. Esc cancels.')
        else:
            self.text_selection.set_extent(hit[0],index)
            if self.text_selection.ranges:
                self._two_point_mode=None
                self.viewport().unsetCursor()
                self._point_popup_position=self.viewport().mapToGlobal(event.position().toPoint())
            else:self.selection_hint('Choose a different ending point to select text.')
            self.selection_updated()
        event.accept()

    def point_selection_release(self,event):
        self._point_release=False
        point,self._point_popup_position=self._point_popup_position,None
        if point is not None:
            token=self._selection_generation
            def show():
                if isValid(self) and self.isVisible() and token==self._selection_generation and self.text_selection.ranges:
                    self.show_copy_choices(point)
            QTimer.singleShot(0,show)
        event.accept()

    def show_copy_choices(self,point):
        menu=QMenu(self)
        menu.setAccessibleName('Copy selected text')
        menu.addAction('Copy — Preserve Line Breaks',lambda:self.copy_selection(False))
        menu.addAction('Copy — Join Paragraphs',lambda:self.copy_selection(True))
        self._copy_popup=menu
        menu.installEventFilter(self)
        def hidden():
            if self._copy_popup is menu:self._copy_popup=None
            menu.deleteLater()
        menu.aboutToHide.connect(hidden)
        menu.popup(point)

    def eventFilter(self,obj,event):
        if obj is self._copy_popup and event.type() in (QEvent.Type.ShortcutOverride,QEvent.Type.KeyPress):
            copy=QKeySequence(event.keyCombination()).matches(self.copy_action.shortcut())==QKeySequence.SequenceMatch.ExactMatch
            if copy or event.key()==Qt.Key.Key_Escape:
                if event.type()==QEvent.Type.KeyPress:
                    obj.close()
                    if copy:self.copy_selection()
                    else:self.clear_selection()
                    self.setFocus()
                event.accept();return True
        return super().eventFilter(obj,event)

    def select_document_text(self):
        self.clear_selection()
        if self.document():
            self.text_selection.ranges={page:(0,None) for page in range(self.document().pageCount())}
            self.selection_updated()

    def copy_text_selection(self,joined=False):
        app=QApplication.instance()
        previous=getattr(app,'_mellow_copy_job',None)
        if previous is not None and isValid(previous):previous.cancel()
        if self._copy_job:self._copy_job.cancel()
        if len(self.text_selection.ranges)>8:
            self._copy_job=SelectionCopy(self,joined)
            app._mellow_copy_job=self._copy_job
            return True
        text=self.text_selection.text(join_paragraphs=joined)
        if text:
            QApplication.clipboard().setText(text)
            return True
        self.selection_hint('No selectable text was found. Scanned PDFs may have no text layer.')
        return False
