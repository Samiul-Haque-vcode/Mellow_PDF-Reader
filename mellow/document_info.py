"""Read-only information from the already open PDF; no extra parsing engine."""
from .dialogs import DismissibleDialog
from pathlib import Path
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLabel, QDialogButtonBox, QScrollArea, QWidget, QFrame


def document_fields(reader):
    document = reader.document()
    path = Path(reader.path)
    try:
        size = path.stat().st_size
        size_text = f'{size / 1024**2:.2f} MiB ({size:,} bytes)' if size >= 1024**2 else f'{size / 1024:.1f} KiB ({size:,} bytes)'
    except OSError:
        size_text = 'Unavailable — file may have moved'
    page = max(0, reader.pageNavigator().currentPage())
    printed = reader.page_label(page)
    number = str(page+1)
    location = number if not printed or printed == number else f'{printed} (PDF page {number})'
    points = document.pagePointSize(page)
    fields = [('Filename', path.name), ('Full path', str(path)), ('File size', size_text),
              ('Pages', str(document.pageCount())), ('Current page', location),
              ('Page size', f'{points.width()*25.4/72:.1f} × {points.height()*25.4/72:.1f} mm '
                            f'({points.width():.1f} × {points.height():.1f} pt)')]
    for key, name in [('Title', 'Title'), ('Author', 'Author'), ('Subject', 'Subject'),
                      ('Keywords', 'Keywords'), ('Creator', 'Created with'), ('Producer', 'PDF producer'),
                      ('CreationDate', 'Created'), ('ModificationDate', 'Modified')]:
        value = document.metaData(getattr(QPdfDocument.MetaDataField, key))
        if isinstance(value, QDateTime):
            value = value.toString(Qt.DateFormat.ISODate) if value.isValid() else ''
        if value:
            fields.append((name, str(value)))
    return fields


class DocumentInfoDialog(DismissibleDialog):
    def __init__(self, reader, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Document information')
        self.resize(540, 480)
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setObjectName('infoContent')
        form = QFormLayout(content)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setSpacing(12)
        self.fields = dict(document_fields(reader))
        self.resize(540,min(520,max(260,len(self.fields)*28+70)))
        self.labels = {}
        for name, value in self.fields.items():
            label = QLabel(value)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            self.labels[name] = label
            form.addRow(name, label)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
