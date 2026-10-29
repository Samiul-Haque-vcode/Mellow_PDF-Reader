"""One explicit, disposable auto-scroll run in the focused reading pane."""
import math
import time
from PySide6.QtCore import QObject,QTimer,Qt,QEvent,Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication,QWidget,QDialog,QMenu,QLineEdit,QComboBox,QAbstractSpinBox
from shiboken6 import isValid


def scroll_speed(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or (isinstance(value,float) and not math.isfinite(value)):return 24
    return max(5,min(200,round(value)))


class AutoScroll(QObject):
    changed=Signal(bool)

    def __init__(self,window,speed=24):
        super().__init__(window)
        self.window=window
        self.speed=scroll_speed(speed)
        self.reader=None
        self._advancing=False
        self._fraction=0.
        self._edge_time=0.
        self._last=0.
        self._revision=None
        self._zoom=None
        self.timer=QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.tick)

    @property
    def running(self):return self.reader is not None

    def start(self,reader):
        self.pause()
        w=self.window
        if (w._closing or w._on_home or reader is not w.active or not reader or
                not isValid(reader) or not reader.isVisible() or not reader.document() or
                not reader.document().pageCount() or QApplication.activeModalWidget()):return False
        reader.flush_zoom()
        self.reader=reader
        self._revision=reader._revision
        self._zoom=(reader.zoomMode(),reader.zoomFactor())
        self._last=time.monotonic()
        self._fraction=0.;self._edge_time=0.
        reader.locationChanged.connect(self.location_changed)
        self.timer.start()
        self.changed.emit(True)
        return True

    def pause(self):
        reader,self.reader=self.reader,None
        self.timer.stop()
        self._fraction=0.;self._edge_time=0.
        if reader is not None:
            if isValid(reader):reader.locationChanged.disconnect(self.location_changed)
            self.changed.emit(False)

    def location_changed(self):
        # Qt can settle scrollbar ranges after a page turn. Those updates use
        # the same reading revision; navigation/zoom changes invalidate it.
        r=self.reader
        if r is not None and not self._advancing and (r._revision!=self._revision or
                (r.zoomMode(),r.zoomFactor())!=self._zoom):self.pause()

    def has_next(self,reader):
        page=reader.pageNavigator().currentPage()
        count=reader.document().pageCount()
        if not reader.facing_pages:return page+1<count
        # The last displayed pair can have either one or two pages.
        start=1 if reader.cover_separate else 0
        if reader.cover_separate and page==0:return count>1
        return start+((page-start)//2)*2+2<count

    def tick(self,now=None):
        r=self.reader;w=self.window
        if r is None:return
        if (not isValid(r) or w._closing or w._on_home or w.active is not r or
                not r.isVisible() or not r.document() or not r.document().pageCount() or w.isMinimized() or
                QApplication.activeModalWidget() or QApplication.activePopupWidget()):
            self.pause();return
        now=time.monotonic() if now is None else now
        elapsed=max(0.,min(.15,now-self._last))
        self._last=now
        self._advancing=True
        try:
            bar=r.verticalScrollBar()
            discrete=r.page_layout_mode in ('single','two')
            fits=discrete and r.at_page_edge(1) and bar.maximum()<=r.documentMargins().top()+r.documentMargins().bottom()+r.pageSpacing()
            if bar.value()<bar.maximum() and not fits:
                self._edge_time=0.
                self._fraction+=self.speed*elapsed
                distance=int(self._fraction)
                self._fraction-=distance
                if distance:
                    r._revision+=1;r._pending=None
                    r._set_scroll_position(bar,bar.value()+distance)
                    if r.custom_rendering:r.rotated_pages.update_navigation()
                return
            if not discrete or not self.has_next(r):
                self.pause();return
            # A fitted page remains visible for a screen's travel time. A
            # zoomed page pauses briefly at its foot before turning the page.
            self._edge_time+=elapsed
            dwell=max(1.5,r.viewport().height()/self.speed) if fits else 1.5
            if self._edge_time>=dwell:
                self._edge_time=0.;self._fraction=0.
                if not r.turn_page(1):self.pause()
        finally:
            if self.reader is r:self._revision=r._revision
            self._advancing=False

    def filter_event(self,obj,event):
        if not self.running or self._advancing:return
        kind=event.type();w=self.window
        if kind==QEvent.Type.ApplicationDeactivate:
            self.pause();return
        if kind==QEvent.Type.Shortcut:
            if obj in (w.auto_scroll_action,w.escape_action):return
            owner=obj
            while owner is not None:
                if owner is w:
                    self.pause();return
                owner=owner.parent()
        owned=isinstance(obj,QWidget) and (obj is w or w.isAncestorOf(obj))
        if not owned:return
        if kind in (QEvent.Type.MouseButtonPress,QEvent.Type.Wheel,QEvent.Type.NativeGesture,QEvent.Type.Gesture):
            # The toolbar toggle owns its click; pausing here first would
            # turn a Pause click into a new Start when triggered is emitted.
            button=w.toolbar.widgetForAction(w.auto_scroll_action)
            if kind==QEvent.Type.MouseButtonPress and obj is button:return
            self.pause()
        elif kind==QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Control,Qt.Key.Key_Shift,Qt.Key.Key_Alt,Qt.Key.Key_Meta):return
            # A configurable toggle shortcut must reach its action unchanged.
            shortcut=w.auto_scroll_action.shortcut()
            if shortcut.isEmpty() or QKeySequence(event.keyCombination()).matches(shortcut)!=QKeySequence.SequenceMatch.ExactMatch:
                self.pause()
        elif kind==QEvent.Type.Show and isinstance(obj,(QDialog,QMenu)):
            self.pause()
        elif kind==QEvent.Type.FocusIn and isinstance(obj,(QLineEdit,QComboBox,QAbstractSpinBox)):
            self.pause()
        elif kind==QEvent.Type.Hide and obj in (w,self.reader):
            self.pause()
        elif kind==QEvent.Type.WindowDeactivate and obj is w:
            self.pause()
        elif kind==QEvent.Type.Resize and obj is w:
            self.pause()
