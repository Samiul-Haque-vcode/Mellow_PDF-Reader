from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton,QLabel
from PySide6.QtPdfWidgets import QPdfView
from .reader import Reader
from .references import Target


class PreviewDialog(QDialog):
    """An independent source-PDF view: no raster copies or source navigation."""
    def __init__(self,source,target,window):
        super().__init__(window)
        self.source=source
        self.window=window
        self.setWindowTitle(target.title+' — original colors')
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(540,480)
        box=QVBoxLayout(self)
        box.setContentsMargins(5,5,5,5)
        if target.evidence:
            evidence=QLabel('Text match · '+target.evidence)
            evidence.setTextFormat(Qt.TextFormat.PlainText)
            evidence.setToolTip(target.excerpt)
            evidence.setProperty('role','muted')
            box.addWidget(evidence)
        self.reader=Reader(source.document(),source.path,self)
        self.reader.theme('Original')
        window.apply_reader_options(self.reader)
        self.reader.setZoomMode(QPdfView.ZoomMode.Custom)
        self.reader.setZoomFactor(1.1)
        self.reader.setAccessibleName('Original PDF reference preview')
        box.addWidget(self.reader)
        row=QHBoxLayout()
        pin=QPushButton('Pin')
        pin.setCheckable(True)
        pin.toggled.connect(self.set_pinned)
        row.addWidget(pin)
        for label,factor in [('−',1/1.2),('+',1.2)]:
            button=QPushButton(label)
            button.setAccessibleName('Zoom out reference preview' if factor<1 else 'Zoom in reference preview')
            button.clicked.connect(lambda checked=False,f=factor: self.reader.zoom_by(f))
            row.addWidget(button)
        opposite=QPushButton('Open in opposite pane')
        opposite.clicked.connect(self.send_opposite)
        row.addWidget(opposite)
        close=QPushButton('Close')
        close.clicked.connect(self.close)
        row.addWidget(close)
        box.addLayout(row)
        self.reader.previewRequested.connect(lambda r,t: window.preview(source,t))
        self.reader.referenceRequested.connect(lambda r,s: window.resolve_reference(source,s))
        self.reader.referenceNavigationRequested.connect(lambda r,s:window.resolve_reference(r,s,navigate=True))
        self.reader.marginsRequested.connect(window.reader_margins)
        QTimer.singleShot(0,lambda: self.reader.jump(target.page,target.point(),record=False))
        # Keep the preview near the cursor while remaining inside the screen.
        from PySide6.QtGui import QCursor
        pos=QCursor.pos()
        screen=self.screen().availableGeometry()
        self.move(max(screen.left(),min(pos.x()+12,screen.right()-self.width())),
                  max(screen.top(),min(pos.y()+12,screen.bottom()-self.height())))
    def set_pinned(self,checked):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,checked)
        self.show()
    def send_opposite(self):
        state=self.reader.state()
        target=Target(state.get('anchor_page',state['page']),state['x'],state['y'])
        self.window.preview_opposite(self.source,target)
        self.close()
