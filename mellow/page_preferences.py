"""Small reading-only dialogs; edits remain local until Save."""
from .dialogs import DismissibleDialog
from PySide6.QtCore import Qt,QSize,QRectF
from PySide6.QtGui import QPainter,QColor,QPen
from PySide6.QtPdf import QPdfPageRenderer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QLabel,QDoubleSpinBox,
    QSpinBox,QDialogButtonBox,QCheckBox,QWidget)


class CropPreview(QWidget):
    def __init__(self,document,page,parent=None):
        super().__init__(parent)
        self.setMinimumSize(230,250)
        self.image=None;self.margins=(0,0,0,0)
        self.setAccessibleName('Current page with excluded margins shaded')
        self.renderer=QPdfPageRenderer(self)
        self.renderer.setRenderMode(QPdfPageRenderer.RenderMode.MultiThreaded)
        self.renderer.setDocument(document)
        self.renderer.pageRendered.connect(self.rendered)
        size=document.pagePointSize(page).toSize().scaled(QSize(520,620),Qt.AspectRatioMode.KeepAspectRatio)
        self.request=self.renderer.requestPage(page,size)
    def rendered(self,page,size,image,options,request):
        if request!=self.request:return
        self.image=image;self.update()
    def paintEvent(self,event):
        painter=QPainter(self)
        if self.image is None:
            painter.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,'Loading page preview…');return
        size=self.image.size().scaled(self.size()-QSize(14,14),Qt.AspectRatioMode.KeepAspectRatio)
        page=QRectF((self.width()-size.width())/2,(self.height()-size.height())/2,size.width(),size.height())
        painter.fillRect(page,Qt.GlobalColor.white)
        painter.drawImage(page,self.image)
        left,top,right,bottom=self.margins
        crop=page.adjusted(page.width()*left/100,page.height()*top/100,-page.width()*right/100,-page.height()*bottom/100)
        shade=QColor(35,45,40,110)
        for rect in (QRectF(page.left(),page.top(),page.width(),crop.top()-page.top()),
                     QRectF(page.left(),crop.bottom(),page.width(),page.bottom()-crop.bottom()),
                     QRectF(page.left(),crop.top(),crop.left()-page.left(),crop.height()),
                     QRectF(crop.right(),crop.top(),page.right()-crop.right(),crop.height())):
            painter.fillRect(rect,shade)
        painter.setPen(QPen(QColor('#426f62'),2));painter.drawRect(crop)
    def release(self):
        self.request=None;self.renderer.setDocument(None)


class MarginsDialog(DismissibleDialog):
    def __init__(self,reader,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Trim reading margins');self.resize(550,570)
        outer=QVBoxLayout(self)
        heading=QLabel('Trim reading margins');heading.setProperty('role','section');outer.addWidget(heading)
        note=QLabel('Applies to this pane and is remembered when reopening this PDF.');note.setWordWrap(True);outer.addWidget(note)
        self.preview=CropPreview(reader.document(),reader.pageNavigator().currentPage(),self);outer.addWidget(self.preview,1)
        form=QFormLayout();self.edits=[]
        for name,value in zip(('Left','Top','Right','Bottom'),reader.crop):
            edit=QDoubleSpinBox();edit.setRange(0,40);edit.setDecimals(1);edit.setSingleStep(.5);edit.setSuffix(' %')
            edit.setValue(value);edit.setAccessibleName(name+' reading margin');edit.valueChanged.connect(self.update_preview)
            form.addRow(name,edit);self.edits.append(edit)
        outer.addLayout(form)
        note=QLabel('Margins refer to the original page. The PDF file stays unchanged.');note.setWordWrap(True);note.setProperty('role','muted');outer.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        self.reset_button=buttons.addButton('Reset margins',QDialogButtonBox.ButtonRole.ResetRole)
        self.reset_button.clicked.connect(self.reset)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);outer.addWidget(buttons)
        self.finished.connect(self.preview.release);self.update_preview()
    def margins(self):return tuple(edit.value() for edit in self.edits)
    def update_preview(self,*_):
        if hasattr(self,'preview'):
            self.preview.margins=self.margins();self.preview.update()
    def reset(self):
        for edit in self.edits:edit.setValue(0)


class NumberingDialog(DismissibleDialog):
    def __init__(self,reader,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Page numbering');self.resize(450,270)
        outer=QVBoxLayout(self)
        heading=QLabel('Page numbering');heading.setProperty('role','section');outer.addWidget(heading)
        self.custom=QCheckBox('Use custom book page numbers');self.custom.setChecked(True);outer.addWidget(self.custom)
        mapping=getattr(reader.document(),'_mellow_numbering',None) or dict(pdf=reader.pageNavigator().currentPage(),book=1)
        self.fields=QWidget();form=QFormLayout(self.fields)
        self.pdf_page=QSpinBox();self.pdf_page.setRange(1,reader.document().pageCount());self.pdf_page.setValue(mapping['pdf']+1)
        self.book_page=QSpinBox();self.book_page.setRange(1,1_000_000);self.book_page.setValue(mapping['book'])
        form.addRow('PDF page',self.pdf_page);form.addRow('Is book page',self.book_page);outer.addWidget(self.fields)
        self.sample=QLabel();self.sample.setWordWrap(True);outer.addWidget(self.sample)
        note=QLabel('Use #12 to go directly to PDF page 12. The PDF file stays unchanged.');note.setWordWrap(True);note.setProperty('role','muted');outer.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        self.reset_button=buttons.addButton('Use PDF labels',QDialogButtonBox.ButtonRole.ResetRole)
        self.reset_button.clicked.connect(lambda:self.custom.setChecked(False))
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);outer.addWidget(buttons)
        self.custom.toggled.connect(self.update_sample)
        self.pdf_page.valueChanged.connect(self.update_sample);self.book_page.valueChanged.connect(self.update_sample);self.update_sample()
    def mapping(self):return dict(pdf=self.pdf_page.value()-1,book=self.book_page.value()) if self.custom.isChecked() else None
    def update_sample(self,*_):
        enabled=self.custom.isChecked();self.fields.setEnabled(enabled)
        self.sample.setText(f'Book page {self.book_page.value()} opens PDF page {self.pdf_page.value()}. Earlier numeric pages use # followed by their PDF page number.' if enabled else 'Use the PDF’s original page labels.')
