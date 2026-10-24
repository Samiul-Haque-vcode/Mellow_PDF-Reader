"""A small search dialog tied to one reading pane, including preview panes."""
from PySide6.QtCore import QModelIndex, Qt, Signal, QEvent, QPoint, QSize
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QLabel,
    QWidget,QToolButton,QCheckBox,QListView,QApplication,QStyledItemDelegate,QStyleOptionViewItem,QStyle)
from shiboken6 import isValid
from .icons import icon
from .style import CHROME
from .focus import owns,restore_focus


def feedback(reader):
    model = reader.search
    total = model.rowCount(QModelIndex())
    index = reader.currentSearchResultIndex()
    searching = hasattr(model, 'status') and model.status() == model.Status.Searching
    counter = f'{index+1} of {total}' if 0 <= index < total else f'{total} found'
    if not model.searchString():
        counter, message = '', 'Enter text to search this PDF.'
    elif total:
        message = f'{index+1} of {total} matches' if 0 <= index < total else f'{total} matches · Enter: next · Shift+Enter: previous'
        if searching: message += ' · Searching…'
    elif searching:
        counter, message = 'Searching…', 'Searching… Results appear as pages are searched.'
    else:
        counter, message = 'No matches', 'No matches. Scanned pages may have no searchable text.'
    return counter, message, total


def step_match(reader, delta):
    total = reader.search.rowCount(QModelIndex())
    if total:
        index = reader.currentSearchResultIndex()
        target = (index + delta) % total if 0 <= index < total else (0 if delta > 0 else total-1)
        reader.visit_search(target)


def model_signals(reader):
    result = [reader.search.rowsInserted, reader.search.modelReset, reader.currentSearchResultIndexChanged]
    if hasattr(reader.search, 'statusChanged'):
        result.append(reader.search.statusChanged)
    return result


class InlineSearch(QWidget):
    activated = Signal()
    geometryChanged = Signal()
    resultsRequested = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.reader = None
        self._connections = []
        self._query_signal = None
        box = QHBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(2)
        self.label=QLabel('Find:')
        box.addWidget(self.label)
        self.text = QLineEdit()
        self.text.setObjectName('pdfSearchText')
        self.text.setAccessibleName('Search focused PDF')
        self.text.setPlaceholderText('Find in PDF')
        self.text.setClearButtonEnabled(True)
        self.text.setFixedWidth(138)
        self.text.installEventFilter(self)
        self.label.setBuddy(self.text)
        self.text.textChanged.connect(self.changed)
        self.text.returnPressed.connect(lambda: self.step(1))
        box.addWidget(self.text)
        self.status = QLabel()
        self.status.setObjectName('pdfSearchStatus')
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setMaximumWidth(88)
        box.addWidget(self.status)
        self.previous, self.next = [QToolButton() for _ in range(2)]
        for button, tip, callback in [(self.previous, 'Previous match', lambda: self.step(-1)),
                                       (self.next, 'Next match (Enter)', lambda: self.step(1))]:
            button.setToolTip(tip)
            button.setAccessibleName(tip)
            button.clicked.connect(callback)
            box.addWidget(button)
        self.results=QToolButton()
        self.results.setToolTip('Search results and options')
        self.results.setAccessibleName('Search results and options')
        self.results.clicked.connect(self.resultsRequested)
        box.addWidget(self.results)
        for button in (self.previous,self.next,self.results):
            button.setProperty('readingButton',True)
            button.setIconSize(QSize(16,16))
        self.set_theme('Sepia')
        self._compact=False

    def set_compact(self, compact):
        if compact==self._compact:return
        self._compact=compact
        self.text.setFixedWidth(100 if compact else 138)
        self.label.setVisible(not compact)
        self.status.setVisible(not compact)
        self.fit_width()
        self.updateGeometry()

    def fit_width(self):
        # Keep the compound field at its current compact size as matches change.
        self.layout().invalidate()
        self.setFixedWidth(self.layout().sizeHint().width())

    def eventFilter(self, obj, event):
        if obj is self.text:
            if event.type()==QEvent.Type.FocusIn:self.activated.emit()
            elif (event.type()==QEvent.Type.KeyPress and
                  event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and
                  event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self.step(-1)
                return True
        return super().eventFilter(obj,event)

    def set_theme(self, theme):
        for button, name in [(self.previous, 'previous'), (self.next, 'next'), (self.results,'search_results')]:
            button.setIcon(icon(name, CHROME['text']))

    def bind(self, reader):
        if reader is self.reader:
            return
        if self.reader is not None and isValid(self.reader):
            for signal in self._connections:
                signal.disconnect(self.update_count)
            if self._query_signal: self._query_signal.disconnect(self.sync_text)
        self._connections.clear()
        self._query_signal = None
        self.reader = reader
        self.text.blockSignals(True)
        self.text.setText(reader.search.searchString() if reader else '')
        self.text.blockSignals(False)
        if reader:
            self._connections = model_signals(reader)
            for signal in self._connections: signal.connect(self.update_count)
            self._query_signal=reader.search.searchStringChanged
            self._query_signal.connect(self.sync_text)
        self.update_count()

    def sync_text(self,*_):
        value=self.reader.search.searchString() if self.reader else ''
        if self.text.text()==value: return
        self.text.blockSignals(True)
        self.text.setText(value)
        self.text.blockSignals(False)

    def changed(self, value):
        if self.reader and value != self.reader.search.searchString():
            self.reader.setCurrentSearchResultIndex(-1)
            self.reader.search.setSearchString(value)
        self.update_count()

    def update_count(self, *_):
        counter, message, total = feedback(self.reader) if self.reader else ('', '', 0)
        self.status.setText(counter)
        self.status.setToolTip(message)
        self.status.setAccessibleName(message)
        self.text.setToolTip(message+' · Enter: next · Shift+Enter: previous · Escape: return to reading')
        self.previous.setEnabled(total > 0)
        self.next.setEnabled(total > 0)
        self.fit_width()
        self.updateGeometry()
        self.geometryChanged.emit()

    def step(self, delta):
        if self.reader:
            self.activated.emit()
            step_match(self.reader, delta)
            self.update_count()


class SearchResultDelegate(QStyledItemDelegate):
    """Two elided lines per visible row, without widgets or horizontal scrolling."""
    def sizeHint(self,option,index):
        return QSize(0,max(52,option.fontMetrics.height()*2+16))
    def paint(self,painter,option,index):
        item=QStyleOptionViewItem(option)
        self.initStyleOption(item,index)
        title,_,excerpt=item.text.partition('\n')
        item.text=''
        option.widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem,item,painter,option.widget)
        painter.save()
        painter.setPen(item.palette.text().color())
        font=item.font
        font.setBold(True)
        painter.setFont(font)
        width=max(0,item.rect.width()-18)
        painter.drawText(item.rect.adjusted(9,6,-9,0),Qt.AlignmentFlag.AlignTop,
                         painter.fontMetrics().elidedText(title,Qt.TextElideMode.ElideRight,width))
        font.setBold(False)
        painter.setFont(font)
        painter.setOpacity(.75)
        painter.drawText(item.rect.adjusted(9,10+option.fontMetrics.height(),-9,0),Qt.AlignmentFlag.AlignTop,
                         painter.fontMetrics().elidedText(excerpt,Qt.TextElideMode.ElideRight,width))
        painter.restore()


class SearchDialog(QDialog):
    def __init__(self, reader, initial=None, parent=None):
        super().__init__(parent)
        self._filter_installed=False
        self._closed=False
        self.setWindowFlags(Qt.WindowType.Popup|Qt.WindowType.FramelessWindowHint)
        self.reader = reader
        self.setWindowTitle('Search PDF')
        self.setMinimumWidth(400)
        box = QVBoxLayout(self)
        self.text = QLineEdit()
        self.text.setObjectName('pdfSearchText')
        self.text.setPlaceholderText('Search text in this PDF')
        self.text.setClearButtonEnabled(True)
        self.text.installEventFilter(self)
        self.status = QLabel()
        self.status.setObjectName('pdfSearchStatus')
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        box.addWidget(self.text)
        filters=QHBoxLayout()
        self.whole_words=QCheckBox('Whole words')
        self.match_case=QCheckBox('Match case')
        self.whole_words.setChecked(reader.search.whole_words)
        self.match_case.setChecked(reader.search.match_case)
        filters.addWidget(self.whole_words)
        filters.addWidget(self.match_case)
        filters.addStretch()
        box.addLayout(filters)
        self.whole_words.toggled.connect(lambda value:reader.search.set_options(whole_words=value))
        self.match_case.toggled.connect(lambda value:reader.search.set_options(match_case=value))
        box.addWidget(self.status)
        self.results=QListView()
        self.results.setObjectName('searchResults')
        self.results.setAccessibleName('Search results')
        self.results.setModel(reader.search)
        self.results.setItemDelegate(SearchResultDelegate(self.results))
        self.results.setUniformItemSizes(True)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results.setMinimumHeight(180)
        self.results.installEventFilter(self)
        self.results.clicked.connect(self.visit)
        self.results.activated.connect(self.visit)
        box.addWidget(self.results,1)
        self.text.returnPressed.connect(lambda: self.step(1))
        self.text.textChanged.connect(self.changed)
        self._connections = []
        for signal in model_signals(reader):
            signal.connect(self.update_count)
            self._connections.append(signal)
        self.text.setText(reader.search.searchString() if initial is None else initial)
        self.text.selectAll()
        self.text.setFocus()
        self.update_count()
        self._query_sync=reader.search.searchStringChanged
        self._query_sync.connect(self.sync_query)
        self._option_sync=reader.search.optionsChanged
        self._option_sync.connect(self.sync_options)
        self.finished.connect(self.disconnect_model)

    def changed(self, value):
        if value != self.reader.search.searchString():
            self.reader.setCurrentSearchResultIndex(-1)
            self.reader.search.setSearchString(value)
        self.update_count()

    def update_count(self, *_):
        _, message, total = feedback(self.reader)
        self.status.setText(message)
        index=self.reader.currentSearchResultIndex()
        if 0<=index<total and self.results.currentIndex().row()!=index:
            self.results.setCurrentIndex(self.reader.search.index(index,0))

    def step(self, delta):
        step_match(self.reader, delta)
        self.update_count()

    def eventFilter(self,obj,event):
        if self._filter_installed and event.type()==QEvent.Type.MouseButtonPress:
            if not self.frameGeometry().contains(event.globalPosition().toPoint()):
                self.reject()
                return False
        if event.type()==QEvent.Type.ShortcutOverride and event.key()==Qt.Key.Key_Escape:
            if obj is self or isinstance(obj,QWidget) and self.isAncestorOf(obj):
                event.accept()
                return True
        if event.type()==QEvent.Type.KeyPress and owns(self,obj):
            if event.key()==Qt.Key.Key_Escape:
                self.reject()
                restore_focus(self.reader)
                return True
            if obj is self.text and event.key()==Qt.Key.Key_Down and event.modifiers()==Qt.KeyboardModifier.NoModifier:
                self.results.setFocus()
                if not self.results.currentIndex().isValid() and self.reader.search.rowCount():
                    self.results.setCurrentIndex(self.reader.search.index(0,0))
                return True
            if obj is self.results and event.key()==Qt.Key.Key_Up and self.results.currentIndex().row()==0 and event.modifiers()==Qt.KeyboardModifier.NoModifier:
                self.text.setFocus()
                return True
        if obj is self.text and event.type()==QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.step(-1)
                return True
        if obj is getattr(self,'results',None) and event.type()==QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):
                self.visit(self.results.currentIndex())
                return True
        return super().eventFilter(obj,event)

    def showEvent(self,event):
        super().showEvent(event)
        self._filter_installed=True
        QApplication.instance().installEventFilter(self)

    def done(self,result):
        if self._closed:return
        self._closed=True
        self._filter_installed=False
        QApplication.instance().removeEventFilter(self)
        super().done(result)

    def visit(self,index):
        if index.isValid():
            self.reader.visit_search(index.row())
            self.update_count()

    def sync_query(self):
        if self.text.text()!=self.reader.search.searchString():
            self.text.blockSignals(True)
            self.text.setText(self.reader.search.searchString())
            self.text.blockSignals(False)

    def sync_options(self):
        for control,value in ((self.whole_words,self.reader.search.whole_words),(self.match_case,self.reader.search.match_case)):
            control.blockSignals(True)
            control.setChecked(value)
            control.blockSignals(False)

    def disconnect_model(self, *_):
        for signal in self._connections:
            signal.disconnect(self.update_count)
        self._connections.clear()
        for signal,callback in ((self._query_sync,self.sync_query),(self._option_sync,self.sync_options)):
            try:signal.disconnect(callback)
            except (RuntimeError,TypeError):pass
        self.results.setModel(None)


class SearchPanel(SearchDialog):
    """Disposable anchored results; closing it leaves this pane's search intact."""
    def __init__(self,reader,parent=None):
        super().__init__(reader,parent=parent)
        self.setObjectName('locationsPanel')
        self.resize(480,460)
        heading=QLabel('Search results')
        heading.setProperty('role','section')
        self.layout().insertWidget(0,heading)
    def position_near(self,anchor):
        screen=anchor.screen().availableGeometry()
        self.resize(min(480,screen.width()-16),min(460,screen.height()-16))
        point=anchor.mapToGlobal(QPoint(0,anchor.height()+4))
        self.move(max(screen.left()+8,min(point.x(),screen.right()-self.width()-7)),
                  max(screen.top()+8,min(point.y(),screen.bottom()-self.height()-7)))
