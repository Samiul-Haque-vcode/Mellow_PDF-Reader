"""Explicit disambiguation for offline, heuristic reference candidates."""
from PySide6.QtCore import Qt
from .dialogs import DismissibleDialog
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QListWidget,QListWidgetItem,QPushButton
from .reading_options import page_label
from .saved_locations import plain_tooltip


class ReferenceChoices(DismissibleDialog):
    def __init__(self,reader,targets,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Matching references')
        self.resize(590,380)
        self.target=None
        self.manual=False
        box=QVBoxLayout(self)
        note=QLabel('Choose a possible target. Caption-like matches appear first; text matching can be uncertain.'
                    if targets else 'No matching text was found. Choose a page manually for scanned or nonstandard references.')
        note.setWordWrap(True)
        box.addWidget(note)
        self.listing=QListWidget()
        self.listing.setAccessibleName('Possible reference targets')
        self.listing.setWordWrap(True)
        for target in targets:
            label=page_label(reader.document(),target.page)
            heading=f'Page {label}'
            if label!=str(target.page+1):heading+=f' · PDF page {target.page+1}'
            heading+=' · '+target.evidence
            item=QListWidgetItem(heading+'\n'+target.excerpt)
            item.setData(Qt.ItemDataRole.UserRole,target)
            item.setData(Qt.ItemDataRole.AccessibleTextRole,item.text())
            item.setToolTip(plain_tooltip(heading,target.excerpt))
            self.listing.addItem(item)
        self.listing.setVisible(bool(targets))
        self.listing.itemActivated.connect(lambda *_:self.choose())
        if targets:self.listing.setCurrentRow(0)
        box.addWidget(self.listing,1)
        row=QHBoxLayout()
        manual=QPushButton('Preview page…')
        manual.setAutoDefault(False)
        manual.clicked.connect(self.choose_manual)
        row.addWidget(manual)
        row.addStretch()
        cancel=QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        self.open_button=QPushButton('Preview selected')
        self.open_button.setEnabled(bool(targets))
        self.open_button.setDefault(bool(targets))
        self.open_button.clicked.connect(self.choose)
        row.addWidget(self.open_button)
        box.addLayout(row)
        if targets:self.listing.setFocus()
        else:manual.setFocus()
    def choose(self):
        item=self.listing.currentItem()
        if item:
            self.target=item.data(Qt.ItemDataRole.UserRole)
            self.accept()
    def choose_manual(self):
        self.manual=True
        self.accept()
