"""Exact, temporary output previews for the three small PDF utilities."""
import shutil
import tempfile
from .dialogs import DismissibleDialog
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QPointF,QFile,QIODevice,QEvent
from PySide6.QtGui import QKeySequence
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
    QListWidget,QListWidgetItem,QAbstractItemView,QLineEdit,QComboBox,QSplitter,
    QWidget,QFileDialog,QDialogButtonBox,QSpinBox,QProgressBar)
from .jobs import FileJob
from . import utilities
from .icons import icon
from .pages import ArrangePagesDialog
from .geometry import page_layout


MODES={
 'extract':('Split / extract PDF','Choose a PDF and enter the pages to keep.','Choose PDF…'),
 'merge':('Merge PDFs','Add PDFs, then drag or use the arrows to set their order.','Add PDFs…'),
 'images':('Images to PDF','Add images and arrange their page order.','Add images…'),
}


class ToolDialog(DismissibleDialog):
    def __init__(self,mode,parent=None,paths=None):
        super().__init__(parent)
        self.mode=mode
        title,help_text,add_text=MODES[mode]
        self.setWindowTitle(title)
        self.resize(1000,680)
        self.setMinimumSize(660,470)
        self._temp=tempfile.TemporaryDirectory(prefix='mellow-preview-')
        self._job=None
        self._generation=0
        self._pending=False
        self._closing=False
        self._saving=False
        self._disposed=False
        self.current_output=None
        self._base_output=None
        self._arrangement=None
        self.saved_path=None
        self.output_sources=[]
        self._published_request=None
        self._view_state=None
        self._restore_target=None
        self._preview_layout_key=None
        self._preview_layout=[]
        self.restore_timer=QTimer(self)
        self.restore_timer.setSingleShot(True)
        self.restore_timer.timeout.connect(self.restore_preview_view)
        self.timer=QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(220)
        self.timer.timeout.connect(self.build_preview)
        box=QVBoxLayout(self)
        box.setContentsMargins(18,16,18,16)
        heading=QLabel(title)
        heading.setProperty('role','title')
        box.addWidget(heading)
        help_label=QLabel(help_text+' Preview updates before you save a new file.')
        help_label.setWordWrap(True)
        help_label.setProperty('role','muted')
        box.addWidget(help_label)
        split=QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(2)
        box.addWidget(split,1)
        self.inputs=QWidget()
        left=QVBoxLayout(self.inputs)
        left.setContentsMargins(0,8,10,0)
        left.addWidget(QLabel('Source files'))
        self.listing=QListWidget()
        self.listing.setAccessibleName('Source file order')
        self.listing.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.listing.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove if mode!='extract' else QAbstractItemView.DragDropMode.NoDragDrop)
        self.listing.model().rowsMoved.connect(lambda *_: self.schedule_preview())
        left.addWidget(self.listing,1)
        self.add_button=QPushButton(add_text)
        self.add_button.setIcon(icon('open'))
        self.add_button.clicked.connect(self.choose_files)
        left.addWidget(self.add_button)
        order=QHBoxLayout()
        self.up=QPushButton('Move up')
        self.down=QPushButton('Move down')
        remove=QPushButton('Remove')
        self.up.clicked.connect(lambda: self.move(-1))
        self.down.clicked.connect(lambda: self.move(1))
        remove.clicked.connect(self.remove_selected)
        if mode!='extract':
            order.addWidget(self.up)
            order.addWidget(self.down)
        order.addWidget(remove)
        left.addLayout(order)
        self.ranges=QLineEdit('1')
        self.ranges.setPlaceholderText('1-5,8,12-14')
        self.ranges.setAccessibleName('Pages to extract')
        self.ranges.installEventFilter(self)
        self.size=QComboBox()
        self.size.addItems(['A4','Letter'])
        self.size.setAccessibleName('Output page size')
        if mode=='extract':
            left.addWidget(QLabel('Pages to keep · e.g. 1-5,8,12-14'))
            left.addWidget(self.ranges)
        if mode=='images':
            left.addWidget(QLabel('Output page size'))
            left.addWidget(self.size)
        self.ranges.textChanged.connect(lambda *_: self.schedule_preview())
        self.size.currentTextChanged.connect(lambda *_: self.schedule_preview())
        self.arrange_button=QPushButton('Arrange pages…')
        self.arrange_button.setToolTip('Reorder or rotate output pages. Changing sources, ranges or page size resets the arrangement.')
        self.arrange_button.setEnabled(False)
        self.arrange_button.clicked.connect(self.arrange_pages)
        left.addWidget(self.arrange_button)
        note=QLabel('Original files remain unchanged. Previews are temporary and stay on this device.')
        note.setProperty('role','muted')
        note.setWordWrap(True)
        left.addWidget(note)
        split.addWidget(self.inputs)
        right=QWidget()
        layout=QVBoxLayout(right)
        layout.setContentsMargins(8,8,0,0)
        toolbar=QHBoxLayout()
        toolbar.addWidget(QLabel('Output preview'))
        toolbar.addStretch()
        self.previous=QPushButton('‹')
        self.previous.setAccessibleName('Previous preview page')
        self.next=QPushButton('›')
        self.next.setAccessibleName('Next preview page')
        self.page=QSpinBox()
        self.page.setRange(1,1)
        self.page.setPrefix('Page ')
        self.page.setAccessibleName('Preview page')
        self.count=QLabel('/ 0')
        self.fit=QComboBox()
        self.fit.addItems(['Fit Page','Fit Width','100%','150%','200%'])
        self.fit.setAccessibleName('Output preview zoom')
        for widget in (self.previous,self.page,self.count,self.next,self.fit): toolbar.addWidget(widget)
        layout.addLayout(toolbar)
        self.output_info=QLabel()
        self.output_info.setAccessibleName('Output page dimensions')
        self.output_info.setProperty('role','muted')
        layout.addWidget(self.output_info)
        self.document=QPdfDocument(self)
        self.preview_file=QFile(self)
        self.view=QPdfView()
        self.view.setAccessibleName('Output PDF preview')
        self.view.setDocument(self.document)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitInView)
        self.view.viewport().installEventFilter(self)
        layout.addWidget(self.view,1)
        split.addWidget(right)
        split.setStretchFactor(0,2)
        split.setStretchFactor(1,3)
        self.status=QLabel('Add files to see the output preview.')
        self.status.setWordWrap(True)
        box.addWidget(self.status)
        progress_row=QHBoxLayout()
        self.progress=QProgressBar()
        self.progress.setRange(0,0)
        self.progress.hide()
        progress_row.addWidget(self.progress,1)
        self.cancel_job=QPushButton('Cancel job')
        self.cancel_job.clicked.connect(self.cancel_current)
        self.cancel_job.hide()
        progress_row.addWidget(self.cancel_job)
        self.retry=QPushButton('Retry preview')
        self.retry.clicked.connect(self.queue_preview)
        self.retry.hide()
        progress_row.addWidget(self.retry)
        box.addLayout(progress_row)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        self.save_button=self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText('Save new PDF…')
        self.save_button.setEnabled(False)
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        box.addWidget(self.buttons)
        self.page.valueChanged.connect(self.go_preview_page)
        self.view.pageNavigator().currentPageChanged.connect(self.page_changed)
        self.previous.clicked.connect(lambda: self.page.setValue(self.page.value()-1))
        self.next.clicked.connect(lambda: self.page.setValue(self.page.value()+1))
        self.fit.currentIndexChanged.connect(self.fit_changed)
        self.enable_preview_controls(False)
        if paths: self.add_paths(paths)
    def paths(self):
        return [self.listing.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.listing.count())]
    def add_paths(self,paths):
        if not paths: return
        if self.mode=='extract':
            self.listing.clear()
            paths=paths[:1]
        for path in paths:
            path=str(Path(path).resolve())
            item=QListWidgetItem(Path(path).name)
            item.setData(Qt.ItemDataRole.UserRole,path)
            item.setToolTip(path)
            self.listing.addItem(item)
        self.schedule_preview()
    def choose_files(self):
        if self.mode=='extract':
            path,_=QFileDialog.getOpenFileName(self,'Choose source PDF','','PDF (*.pdf)')
            if path: self.add_paths([path])
        else:
            pattern='Images (*.png *.jpg *.jpeg *.bmp *.webp)' if self.mode=='images' else 'PDF (*.pdf)'
            paths,_=QFileDialog.getOpenFileNames(self,MODES[self.mode][0],'',pattern)
            self.add_paths(paths)
    def move(self,direction):
        row=self.listing.currentRow()
        target=row+direction
        if 0<=row<self.listing.count() and 0<=target<self.listing.count():
            item=self.listing.takeItem(row)
            self.listing.insertItem(target,item)
            self.listing.setCurrentRow(target)
            self.schedule_preview()
    def remove_selected(self):
        for item in self.listing.selectedItems(): self.listing.takeItem(self.listing.row(item))
        self.schedule_preview()
    def enable_preview_controls(self,enabled):
        for widget in (self.page,self.previous,self.next,self.fit): widget.setEnabled(enabled)
    def request_key(self):
        sources=[]
        for path in self.paths():
            try:
                stat=Path(path).stat();sources.append((path,stat.st_size,stat.st_mtime_ns))
            except OSError:sources.append((path,None,None))
        return (self.mode,tuple(sources),''.join(self.ranges.text().split()) if self.mode=='extract' else '',
                self.size.currentText() if self.mode=='images' else '',
                tuple(tuple(entry) if isinstance(entry,(tuple,list)) else (entry,) for entry in self._arrangement) if self._arrangement is not None else None)
    def go_preview_page(self,value):
        self.restore_timer.stop()
        self._restore_target=None
        self._view_state=None
        self.position_preview(value-1,QPointF())
        self.schedule_position(value-1,QPointF())
    def fit_changed(self,*_):
        self.restore_timer.stop()
        self._restore_target=None
        self._view_state=None
        page=self.view.pageNavigator().currentPage()
        point=QPointF(self.view.pageNavigator().currentLocation())
        self.set_fit()
        self.position_preview(page,point)
        self.schedule_position(page,point)
    def schedule_position(self,page,point):
        if self.current_output and not self._disposed and not self._closing:
            self._restore_target=(self._generation,page,QPointF(point))
            self.restore_timer.start(0)
    def eventFilter(self,obj,event):
        if obj is self.ranges and event.type()==QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):
            # Text changes already scheduled the preview. Enter must not
            # activate the dialog's unrelated default file-picker button.
            if self.timer.isActive():self.timer.start(0)
            return True
        if event.type()==QEvent.Type.Resize and obj is self.view.viewport() and self.current_output and not self.restore_timer.isActive():
            nav=self.view.pageNavigator()
            self.schedule_position(nav.currentPage(),nav.currentLocation())
        return super().eventFilter(obj,event)
    def preview_layout(self):
        key=(self._generation,self.view.viewport().size(),self.view.zoomMode(),self.view.zoomFactor(),self.view.logicalDpiX())
        if key!=self._preview_layout_key:
            self._preview_layout_key=key
            self._preview_layout=page_layout(self.view)
        return self._preview_layout
    def position_preview(self,page,point):
        if not self.current_output or not 0<=page<self.document.pageCount():return
        self.view.pageNavigator().jump(page,point)
        # Native QPdfView can retain the old pixel scroll offset when zoom
        # changes, even though its navigator still reports the desired page.
        # Use the same public-API page geometry as the main reader to align it.
        for index,rect,scale in self.preview_layout():
            if index==page:
                self.view.verticalScrollBar().setValue(round(rect.top()+point.y()*scale))
                self.view.horizontalScrollBar().setValue(round(rect.left()+point.x()*scale))
                break
    def capture_preview_view(self):
        page=self.view.pageNavigator().currentPage()
        if self._published_request is None or not 0<=page<self.document.pageCount():return None
        arrangement=self._published_request[4]
        base_page,angle=arrangement[page] if arrangement is not None else (page,0)
        return dict(request=self._published_request,base_page=base_page,angle=angle,
                    location=QPointF(self.view.pageNavigator().currentLocation()),
                    size=self.document.pagePointSize(page),mode=self.view.zoomMode(),zoom=self.view.zoomFactor())
    def restore_preview_view(self):
        target=self._restore_target
        self._restore_target=None
        if target is None or target[0]!=self._generation or self._disposed or self._closing or not self.current_output:return
        _,page,location=target
        self.position_preview(page,location)
        self.page_changed(page)
        self._view_state=None
    def schedule_preview(self):
        if self._disposed or self._saving:return
        for dialog in self.findChildren(ArrangePagesDialog):dialog.reject()
        self._base_output=None
        self._arrangement=None
        self.queue_preview()
    def queue_preview(self):
        if self._disposed or self._saving: return
        if self.current_output and (not self.restore_timer.isActive() or self._view_state is None):self._view_state=self.capture_preview_view()
        self.restore_timer.stop()
        self._restore_target=None
        if not self.paths():self._view_state=None
        self.retry.hide()
        self._generation+=1
        self._pending=True
        self.current_output=None
        self.save_button.setEnabled(False)
        self.arrange_button.setEnabled(False)
        self.enable_preview_controls(False)
        self.release_preview()
        self.count.setText('/ 0')
        self.count.setAccessibleName('No output preview')
        self.output_info.clear()
        self.output_info.setToolTip('')
        self.status.setText('Preparing preview…' if self.paths() else 'Add files to see the output preview.')
        if self._job: self._job.cancel()
        self.timer.start()
    def arrange_pages(self):
        if not self.current_output or not self._base_output or self._job or self._saving:return
        try:dialog=ArrangePagesDialog(self._base_output,self,self._arrangement)
        except (OSError,ValueError) as error:
            self.status.setText(str(error))
            return
        accepted=dialog.exec()==QDialog.DialogCode.Accepted
        entries=dialog.entries()
        dialog.deleteLater()
        if accepted and not self._closing and not self._disposed:
            self.apply_arrangement(entries)
    def apply_arrangement(self,entries):
        if not self.current_output or not self._base_output or self._job or self._saving:return False
        self._arrangement=list(entries)
        self.queue_preview()
        return True
    def build_preview(self):
        if self._disposed or self._closing or self._saving: return
        if self._job: return  # finished() starts the latest pending request.
        self._pending=False
        paths=self.paths()
        if not paths: return
        generation=self._generation
        output=str(Path(self._temp.name)/f'preview-{generation}.pdf')
        mode,ranges,size=self.mode,self.ranges.text(),self.size.currentText()
        request=self.request_key()
        base,entries=self._base_output,self._arrangement
        def operation(cancel,progress):
            if base and entries is not None:utilities.arrange(base,output,entries,cancel,progress)
            elif mode=='extract': utilities.extract(paths[0],output,ranges,cancel,progress)
            elif mode=='merge': utilities.merge(paths,output,cancel,progress)
            else: utilities.images_to_pdf(paths,output,size,cancel,progress)
        job=FileJob(operation,output,self)
        self._job=job
        self.progress.show();self.cancel_job.show();self.progress.setRange(0,0)
        job.stageChanged.connect(lambda text:self.set_stage(text) if generation==self._generation and not self._closing else None)
        job.progress.connect(lambda done,total:self.set_progress(done,total) if generation==self._generation and not self._closing else None)
        job.succeeded.connect(lambda _: self.preview_ready(generation,output,paths,request))
        job.failed.connect(lambda message: self.preview_failed(generation,message))
        job.finished.connect(lambda: self.job_finished(job))
        job.start()
    def set_stage(self,text):
        self.status.setText(text)
        self.progress.setRange(0,0)
    def set_progress(self,done,total):
        self.progress.setRange(0,max(1,total));self.progress.setValue(done)
    def cancel_current(self):
        if not self._job:return
        if not self._saving:self._generation+=1
        self._pending=False;self.timer.stop();self._job.cancel()
        self.cancel_job.setEnabled(False)
        self.status.setText('Cancelling current job…')
    def preview_ready(self,generation,output,paths,request):
        if self._closing or generation!=self._generation: return
        if request!=self.request_key():
            self.schedule_preview()
            return
        self.preview_file.setFileName(output)
        if not self.preview_file.open(QIODevice.OpenModeFlag.ReadOnly):
            self.preview_failed(generation,'Could not open the output PDF.')
            return
        # Owning the QFile explicitly lets us release the Windows file handle
        # immediately, rather than waiting for QPdfDocument's internal device.
        self.document.load(self.preview_file)
        if self.document.error()!=QPdfDocument.Error.None_ or not self.document.pageCount():
            self.release_preview()
            self.preview_failed(generation,'Could not render the output PDF.')
            return
        self.view.setDocument(self.document)
        self.current_output=output
        if self._arrangement is None:self._base_output=output
        self.output_sources=list(paths)
        self._published_request=request
        count=self.document.pageCount()
        self.page.blockSignals(True)
        self.page.setRange(1,count)
        self.page.setValue(1)
        self.page.blockSignals(False)
        self.count.setText(f'/ {count}')
        self.count.setAccessibleName(f'{count} output pages')
        self.set_fit()
        page,location=0,QPointF()
        state=self._view_state
        if state and state['request'][:3]==request[:3]:
            arrangement=request[4]
            page=next((i for i,entry in enumerate(arrangement) if entry[0]==state['base_page']),0) if arrangement is not None else min(state['base_page'],count-1)
            angle=arrangement[page][1] if arrangement is not None else 0
            self.view.setZoomMode(state['mode'])
            if state['mode']==QPdfView.ZoomMode.Custom:self.view.setZoomFactor(state['zoom'])
            dimensions=self.document.pagePointSize(page)
            if angle==state['angle'] and state['size'].width()>0 and state['size'].height()>0:
                point=state['location']
                location=QPointF(max(0,min(dimensions.width(),point.x()*dimensions.width()/state['size'].width())),
                                max(0,min(dimensions.height(),point.y()*dimensions.height()/state['size'].height())))
        self.enable_preview_controls(True)
        self.position_preview(page,location)
        self.page_changed(page)
        self.schedule_position(page,location)
        self.save_button.setEnabled(True)
        self.arrange_button.setEnabled(True)
        self.status.setText(f'{count} page'+('s' if count!=1 else '')+' · Preview ready. Save creates a new PDF.')
    def preview_failed(self,generation,message):
        if generation==self._generation and not self._closing:
            self.status.setText('Preview failed: '+message)
            self.save_button.setEnabled(False)
    def job_finished(self,job):
        if self._job is job: self._job=None
        self.progress.hide();self.cancel_job.hide();self.cancel_job.setEnabled(True)
        if not self.current_output and not self._pending and not self._closing:
            self.status.setText('Preview cancelled. Retry or change the inputs.') if self.status.text().startswith('Cancelling current') else None
            self.retry.setVisible(bool(self.paths()))
        job.deleteLater()
        if self.saved_path:
            self.dispose()
            super().accept()
        elif self._closing:
            self.dispose()
            super().reject()
        elif self._saving:
            self._saving=False
            self.inputs.setEnabled(True)
            self.save_button.setEnabled(bool(self.current_output))
            self.arrange_button.setEnabled(bool(self.current_output))
        elif self._pending:
            self.timer.start()
        # Keep only the current output. Qt's document was closed before an old
        # preview can be removed, including on Windows with open-file locking.
        if not self._disposed:
            for path in Path(self._temp.name).glob('preview-*.pdf'):
                if str(path) not in (self.current_output,self._base_output):
                    try: path.unlink()
                    except OSError: pass
    def page_changed(self,page):
        self.page.blockSignals(True)
        self.page.setValue(page+1)
        self.page.blockSignals(False)
        ready=bool(self.current_output) and self.view.document() is self.document
        self.previous.setEnabled(ready and page>0)
        self.next.setEnabled(ready and page+1<self.document.pageCount())
        if ready and 0<=page<self.document.pageCount():
            size=self.document.pagePointSize(page)
            self.output_info.setText(f'Page size: {size.width()*25.4/72:.1f} × {size.height()*25.4/72:.1f} mm')
            self.output_info.setToolTip(f'{size.width():g} × {size.height():g} pt · Current output page')
    def set_fit(self,*_):
        index=self.fit.currentIndex()
        if index<2: self.view.setZoomMode(QPdfView.ZoomMode.FitInView if index==0 else QPdfView.ZoomMode.FitToWidth)
        else:
            self.view.setZoomMode(QPdfView.ZoomMode.Custom)
            self.view.setZoomFactor(float(self.fit.currentText().strip('%'))/100)
    def save(self):
        if not self.current_output or self._job or self._saving: return
        if not self.ensure_current_preview():return
        dialog=QFileDialog(self,'Save a new PDF')
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setNameFilter('PDF (*.pdf)')
        dialog.setDefaultSuffix('pdf')
        if dialog.exec() and dialog.selectedFiles(): self.save_to(dialog.selectedFiles()[0])
    def save_to(self,destination):
        if not self.current_output or self._job or self._saving: return False
        if not self.ensure_current_preview():return False
        if not str(destination).lower().endswith('.pdf'): destination=str(destination)+'.pdf'
        try: utilities.safe_output(destination,self.output_sources)
        except (OSError,ValueError) as error:
            self.status.setText(str(error))
            return False
        source=self.current_output
        sources=list(self.output_sources)
        self._saving=True
        self.inputs.setEnabled(False)
        self.arrange_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.status.setText('Saving PDF…')
        def operation(cancel,progress):
            utilities.safe_output(destination,sources)
            utilities.copy_output(source,destination,cancel,progress)
        job=FileJob(operation,str(destination),self)
        self._job=job
        self.progress.show();self.cancel_job.show();self.progress.setRange(0,0)
        job.stageChanged.connect(self.set_stage);job.progress.connect(self.set_progress)
        job.succeeded.connect(self.save_succeeded)
        job.failed.connect(lambda message: self.status.setText('Save failed: '+message))
        job.cancelled.connect(lambda: self.status.setText('Save cancelled.'))
        job.finished.connect(lambda: self.job_finished(job))
        job.start()
        return True
    def ensure_current_preview(self):
        if self._published_request==self.request_key():return True
        self.schedule_preview()
        self.status.setText('Inputs changed. Updating the output preview before saving…')
        return False
    def save_succeeded(self,path):
        self.saved_path=path
    def release_preview(self):
        self._preview_layout_key=None
        self._preview_layout=[]
        self.document._mellow_page_sizes=None
        self.view.setDocument(None)
        self.document.close()
        self.preview_file.close()
    def dispose(self):
        if self._disposed: return
        self.timer.stop()
        self.restore_timer.stop()
        self._restore_target=None
        self._view_state=None
        self.current_output=None
        self._published_request=None
        self.release_preview()
        self._base_output=None
        self._temp.cleanup()
        self._disposed=True
    def reject(self):
        for dialog in self.findChildren(ArrangePagesDialog):dialog.reject()
        if self._job:
            self._closing=True
            self.timer.stop()
            self.inputs.setEnabled(False)
            self.save_button.setEnabled(False)
            self.status.setText('Cancelling…')
            self._job.cancel()
            return
        self.dispose()
        super().reject()
    def closeEvent(self,event):
        self.reject()
        if self._job: event.ignore()
        else: event.accept()
