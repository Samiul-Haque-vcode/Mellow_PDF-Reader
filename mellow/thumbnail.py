"""One disposable, asynchronous Home thumbnail; never a disk image cache."""
from PySide6.QtCore import Qt, QSize, QFile, QIODevice, QTimer
from PySide6.QtGui import QPixmap, QImage, QPainter
from PySide6.QtPdf import QPdfDocument, QPdfPageRenderer
from PySide6.QtWidgets import QLabel
from .icons import application_icon
from .theme import recolor,tuning_values


class PageThumbnail(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(88, 112)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAccessibleName('Saved page preview')
        self.document = QPdfDocument(self)
        self.source = QFile(self)
        self.renderer = QPdfPageRenderer(self)
        self.renderer.setRenderMode(QPdfPageRenderer.RenderMode.MultiThreaded)
        self.renderer.pageRendered.connect(self.rendered)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(120)
        self.timer.timeout.connect(self.load)
        self.target = None
        self.request = None
        self.image = None
        self.theme = 'Sepia'
        self.release()

    def set_source(self, path, page):
        target = (path, page) if path else None
        if target == self.target:
            return
        self.release()
        self.target = target
        self.image = None
        self.show_image()
        if self.isVisible() and target:
            self.timer.start()

    def set_theme(self, theme):
        self.theme = theme
        self.show_image()

    def show_image(self):
        if self.image is None:
            self.setPixmap(application_icon().pixmap(40, 40))
        else:
            pixmap = QPixmap.fromImage(recolor(self.image,self.theme,getattr(self,'preserve',True),*tuning_values(getattr(self,'tuning',None))))
            pixmap.setDevicePixelRatio(self.devicePixelRatioF())
            self.setPixmap(pixmap)

    def load(self):
        if not self.target or not self.isVisible():
            return
        path, page = self.target
        self.source.setFileName(path)
        if not self.source.open(QIODevice.OpenModeFlag.ReadOnly):
            return
        self.document.load(self.source)
        if self.document.error() != QPdfDocument.Error.None_:
            # Missing, encrypted and damaged PDFs retain a quiet book fallback.
            self.release()
            return
        page = max(0, min(page, self.document.pageCount() - 1))
        points = self.document.pagePointSize(page)
        dpr = self.devicePixelRatioF()
        size = points.toSize().scaled(QSize(round(80*dpr), round(104*dpr)),
                                     Qt.AspectRatioMode.KeepAspectRatio)
        self.renderer.setDocument(self.document)
        self.request = self.renderer.requestPage(page, size)

    def rendered(self, page, size, image, options, request):
        if request != self.request:
            return
        if not image.isNull():
            # Qt's page renderer can leave the paper transparent. Composite it
            # before toning so Dark doesn't leave black text on a dark canvas.
            self.image = QImage(image.size(), QImage.Format.Format_RGB32)
            self.image.fill(Qt.GlobalColor.white)
            painter = QPainter(self.image)
            painter.drawImage(0, 0, image)
            painter.end()
        self.release()
        self.show_image()

    def release(self):
        self.timer.stop()
        self.request = None
        self.renderer.setDocument(None)
        self.document.close()
        self.source.close()

    def showEvent(self, event):
        super().showEvent(event)
        if self.target and self.image is None:
            self.timer.start()

    def hideEvent(self, event):
        self.release()
        super().hideEvent(event)
