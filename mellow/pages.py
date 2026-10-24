"""Temporary page navigation and a small pre-save page arrangement workspace."""
from .dialogs import DismissibleDialog
from pathlib import Path
from shiboken6 import isValid
from PySide6.QtCore import Qt,QPoint,QTimer,QEvent,QFile,QIODevice,QSize
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import (QApplication,QDialog,QVBoxLayout,QHBoxLayout,QLabel,
    QToolButton,QPushButton,QDialogButtonBox,QWidget,QSpinBox,QComboBox)
from .page_grid import PageGrid
from .reading_options import page_label
from .icons import icon
from .focus import owns,restore_focus


class PagesPanel(DismissibleDialog):
    def __init__(self,reader,parent=None):
        super().__init__(parent,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint)
        self.setObjectName('locationsPanel')
        self.setWindowTitle('Pages')
        self.reader=reader
        self.document=reader.document()
        self._finished=False
        self._filter_installed=False
        self.resize(500,540)
        root=QVBoxLayout(self)
        root.setContentsMargins(14,12,14,12)
        header=QHBoxLayout()
        title=QLabel('Pages')
        title.setProperty('role','section')
        header.addWidget(title,1)
        close=QToolButton()
        close.setIcon(icon('close'))
        close.setAccessibleName('Close page thumbnails')
        close.clicked.connect(self.reject)
        header.addWidget(close)
        root.addLayout(header)
        name=QLabel(Path(reader.path).name)
        name.setTextFormat(Qt.TextFormat.PlainText)
        name.setProperty('role','muted')
        name.setWordWrap(True)
        root.addWidget(name)
        controls=QHBoxLayout()
        controls.addWidget(QLabel('Page:'))
        self.page_number=QSpinBox()
        self.page_number.setRange(1,self.document.pageCount())
        self.page_number.setKeyboardTracking(False)
        self.page_number.setAccessibleName('PDF page number')
        self.page_number.setToolTip('Browse by physical PDF page number; Enter opens the selected page.')
        controls.addWidget(self.page_number)
        controls.addWidget(QLabel(f'/ {self.document.pageCount()}'),1)
        self.thumbnail_size=QComboBox()
        self.thumbnail_size.addItems(['Small','Medium','Large'])
        self.thumbnail_size.setAccessibleName('Thumbnail size')
        controls.addWidget(self.thumbnail_size)
        root.addLayout(controls)
        self.grid=PageGrid(self.document,self,label=lambda page:page_label(self.document,page))
        root.addWidget(self.grid,1)
        self.grid.clicked.connect(self.visit)
        self.grid.activated.connect(self.visit)
        self.document.statusChanged.connect(self.document_status)
        self.start_page=reader.pageNavigator().currentPage()
        self.grid.pages.current_page=self.start_page
        self.page_number.setValue(self.start_page+1)
        self.page_number.valueChanged.connect(self.browse_page)
        self.page_number.lineEdit().returnPressed.connect(lambda:self.visit(self.grid.pages.index(self.page_number.value()-1,0)))
        self.thumbnail_size.currentIndexChanged.connect(self.resize_thumbnails)
        self.grid.selectionModel().currentChanged.connect(self.selected_page)
        self.grid.installEventFilter(self)

    def browse_page(self,number):
        index=self.grid.pages.index(number-1,0)
        self.grid.setCurrentIndex(index)
        self.grid.scrollTo(index,self.grid.ScrollHint.PositionAtCenter)

    def selected_page(self,index,previous):
        if index.isValid():
            self.page_number.blockSignals(True)
            self.page_number.setValue(index.row()+1)
            self.page_number.blockSignals(False)

    def resize_thumbnails(self,index):
        row=self.grid.currentIndex().row()
        self.grid.set_thumbnail_size([QSize(152,198),QSize(184,240),QSize(216,282)][index])
        if row>=0:self.grid.scrollTo(self.grid.pages.index(row,0),self.grid.ScrollHint.PositionAtCenter)

    def document_status(self,status):
        if status!=QPdfDocument.Status.Ready:self.reject()

    def visit(self,index):
        if self._finished or not index.isValid():return
        if self.reader.document() is not self.document or self.document.status()!=QPdfDocument.Status.Ready:
            self.reject()
            return
        self.reader.jump(index.row())
        self.accept()

    def showEvent(self,event):
        super().showEvent(event)
        self._filter_installed=True
        QApplication.instance().installEventFilter(self)
        self.grid.setFocus()
        QTimer.singleShot(0,self.select_start)

    def select_start(self):
        if not self._finished:
            index=self.grid.pages.index(self.start_page,0)
            self.grid.setCurrentIndex(index)
            self.grid.scrollTo(index,self.grid.ScrollHint.PositionAtCenter)

    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.ShortcutOverride and event.key()==Qt.Key.Key_Escape:
            if obj is self or isinstance(obj,QWidget) and self.isAncestorOf(obj):
                event.accept()
                return True
        if event.type()==QEvent.Type.KeyPress and owns(self,obj) and event.key()==Qt.Key.Key_Escape:
            self.reject()
            restore_focus(self.reader)
            return True
        return super().eventFilter(obj,event)

    def done(self,result):
        if self._finished:return
        self._finished=True
        self._filter_installed=False
        QApplication.instance().removeEventFilter(self)
        self.grid.release()
        if self.document is not None and isValid(self.document):
            self.document.statusChanged.disconnect(self.document_status)
        self.document=None
        super().done(result)

    def position_near(self,anchor):
        available=anchor.screen().availableGeometry()
        self.resize(min(500,available.width()-16),min(540,available.height()-16))
        point=anchor.mapToGlobal(QPoint(0,anchor.height()+4))
        self.move(max(available.left()+8,min(point.x(),available.right()-self.width()-7)),
                  max(available.top()+8,min(point.y(),available.bottom()-self.height()-7)))


class ArrangePagesDialog(DismissibleDialog):
    def __init__(self,path,parent=None,entries=None):
        super().__init__(parent)
        self.setWindowTitle('Arrange pages')
        self.resize(820,620)
        self.source=QFile(str(path),self)
        self.document=QPdfDocument(self)
        self.grid=None
        if not self.source.open(QIODevice.OpenModeFlag.ReadOnly):
            self.deleteLater()
            raise ValueError('Could not open pages for arrangement.')
        self.document.load(self.source)
        if self.document.error()!=QPdfDocument.Error.None_ or not self.document.pageCount():
            self.document.close();self.source.close()
            self.deleteLater()
            raise ValueError('Could not read pages for arrangement.')
        root=QVBoxLayout(self)
        title=QLabel('Arrange pages')
        title.setProperty('role','title')
        root.addWidget(title)
        note=QLabel('Drag pages to reorder. Select one or more pages to rotate. Changes apply to the new PDF only.')
        note.setWordWrap(True)
        note.setProperty('role','muted')
        root.addWidget(note)
        self.grid=PageGrid(self.document,self,entries=entries,editable=True)
        root.addWidget(self.grid,1)
        actions=QHBoxLayout()
        for label,callback in [('Move earlier',lambda:self.grid.move_selected(-1)),
                               ('Move later',lambda:self.grid.move_selected(1)),
                               ('Rotate left',lambda:self.rotate(-90)),
                               ('Rotate right',lambda:self.rotate(90)),('Reset',self.reset)]:
            button=QPushButton(label)
            button.setAutoDefault(False)
            button.clicked.connect(callback)
            actions.addWidget(button)
        root.addLayout(actions)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Apply|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.grid.setCurrentIndex(self.grid.pages.index(0,0))

    def rotate(self,delta):
        self.grid.pages.rotate(self.grid.selected_rows(),delta)

    def reset(self):
        model=self.grid.pages
        model.beginResetModel()
        model.entries=[(page,0) for page in range(self.document.pageCount())]
        model.endResetModel()
        self.grid.select_rows([0])

    def entries(self):return list(self.grid.pages.entries)

    def done(self,result):
        if self.grid is not None:self.grid.release()
        self.document.close()
        self.source.close()
        super().done(result)
