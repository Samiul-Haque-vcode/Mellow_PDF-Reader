"""Render the original vector brand mark into Windows icon sizes."""
import os
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import Qt
from PIL import Image
from mellow.icons import ASSETS

app=QApplication.instance() or QApplication([])
image=QImage(256,256,QImage.Format.Format_ARGB32)
image.fill(Qt.GlobalColor.transparent)
painter=QPainter(image)
QSvgRenderer(str(ASSETS/'logo.svg')).render(painter)
painter.end()
image.save(str(ASSETS/'logo.png'))
Image.open(ASSETS/'logo.png').save(ASSETS/'mellow.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
