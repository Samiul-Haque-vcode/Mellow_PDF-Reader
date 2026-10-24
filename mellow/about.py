"""Visible, accurate project and development credits."""
from .dialogs import DismissibleDialog
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QDialogButtonBox
from . import __version__
from .icons import application_icon

PUBLISHER='Mellow PDF Reader project'
DEVELOPMENT_CREDIT='Developed with ChatGPT (OpenAI)'


class AboutDialog(DismissibleDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle('About Mellow PDF Reader')
        self.setFixedWidth(430)
        outer=QVBoxLayout(self)
        outer.setContentsMargins(22,20,22,20)
        outer.setSpacing(14)
        hero=QHBoxLayout()
        logo=QLabel()
        logo.setPixmap(application_icon().pixmap(52,52))
        hero.addWidget(logo)
        title=QLabel(f'Mellow PDF Reader\nVersion {__version__}')
        title.setProperty('role','section')
        hero.addWidget(title,1)
        outer.addLayout(hero)
        outer.addWidget(QLabel('A softer way to read.'))
        self.publisher=QLabel('Publisher: '+PUBLISHER)
        self.publisher.setWordWrap(True)
        outer.addWidget(self.publisher)
        outer.addWidget(QLabel('Project owner: Samiul-Haque-vcode'))
        self.credit=QLabel(DEVELOPMENT_CREDIT)
        self.credit.setProperty('role','section')
        outer.addWidget(self.credit)
        detail=QLabel('An independent project. ChatGPT (OpenAI) is credited for AI-assisted design, coding and testing support.')
        detail.setWordWrap(True)
        detail.setProperty('role','muted')
        outer.addWidget(detail)
        license_label=QLabel('Mellow source: MIT License. Qt/PySide6 and other bundled libraries retain their own licenses; see the licenses folder beside the installed application.')
        license_label.setWordWrap(True)
        license_label.setProperty('role','muted')
        outer.addWidget(license_label)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
