"""Disposable, visible-only PDF thumbnails shared by page navigation and tools."""
from collections import OrderedDict
import json
from shiboken6 import delete,isValid
from PySide6.QtCore import (Qt,QAbstractListModel,QModelIndex,QSize,QTimer,QMimeData,
    QRect,QPoint,QEvent)
from PySide6.QtGui import QPainter,QImage,QTransform,QPalette,QPen
from PySide6.QtPdf import QPdfDocument,QPdfPageRenderer
from PySide6.QtWidgets import (QListView,QStyledItemDelegate,QStyleOptionViewItem,
    QStyle,QAbstractItemView)


CACHE_BYTES=8*1024*1024
MIME='application/x-mellow-page-order'
CELL=QSize(152,198)


class PageModel(QAbstractListModel):
    def __init__(self,count,parent=None,entries=None,label=None,editable=False):
        super().__init__(parent)
        self.entries=list(entries) if entries is not None else [(page,0) for page in range(count)]
        self.label=label or (lambda page:str(page+1))
        self.editable=editable
        self.current_page=None

    def rowCount(self,parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.entries)

    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0<=index.row()<len(self.entries):return None
        page,angle=self.entries[index.row()]
        if role==Qt.ItemDataRole.UserRole:return (page,angle)
        if role in (Qt.ItemDataRole.DisplayRole,Qt.ItemDataRole.AccessibleTextRole):
            if not self.editable:return self.label(page)+(' · Current' if page==self.current_page else '')
            return f'{index.row()+1} · PDF {page+1}'+(f' · {angle}°' if angle else '')
        if role==Qt.ItemDataRole.ToolTipRole:
            return f'PDF page {page+1}'+(f' · rotate {angle}° clockwise' if angle else '')
        return None

    def flags(self,index):
        flags=Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable
        if self.editable:flags|=Qt.ItemFlag.ItemIsDropEnabled
        if self.editable and index.isValid():flags|=Qt.ItemFlag.ItemIsDragEnabled
        return flags

    def mimeTypes(self):return [MIME]

    def mimeData(self,indexes):
        data=QMimeData()
        data.setData(MIME,json.dumps(sorted({i.row() for i in indexes if i.isValid()})).encode())
        return data

    def supportedDropActions(self):return Qt.DropAction.MoveAction

    def move_selection(self,rows,before):
        rows=sorted(set(rows))
        if not rows or any(not 0<=row<len(self.entries) for row in rows):return []
        before=max(0,min(before,len(self.entries)))
        selected=[self.entries[row] for row in rows]
        selected_rows=set(rows)
        rest=[entry for row,entry in enumerate(self.entries) if row not in selected_rows]
        target=before-sum(row<before for row in rows)
        self.beginResetModel()
        self.entries=rest[:target]+selected+rest[target:]
        self.endResetModel()
        return list(range(target,target+len(selected)))

    def rotate(self,rows,delta):
        for row in rows:
            page,angle=self.entries[row]
            self.entries[row]=(page,(angle+delta)%360)
            index=self.index(row,0)
            self.dataChanged.emit(index,index)


class PageDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        grid=self.parent()
        item=QStyleOptionViewItem(option)
        self.initStyleOption(item,index)
        text=item.text
        item.text=''
        grid.style().drawControl(QStyle.ControlElement.CE_ItemViewItem,item,painter,grid)
        area=option.rect.adjusted(10,8,-10,-34)
        key=tuple(index.data(Qt.ItemDataRole.UserRole))
        image=grid.cache.get(key)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if image is not None:
            grid.cache.move_to_end(key)
            size=image.size().scaled(area.size(),Qt.AspectRatioMode.KeepAspectRatio)
            target=QRect(QPoint(),size)
            target.moveCenter(area.center())
            painter.fillRect(target,Qt.GlobalColor.white)
            painter.drawImage(target,image)
        else:
            painter.setPen(item.palette.color(QPalette.ColorRole.Mid))
            painter.drawRect(area.adjusted(14,0,-14,0))
            painter.drawText(area,Qt.AlignmentFlag.AlignCenter,'Preview unavailable' if key in grid.failed else '…')
            grid.request(index.row())
        selected=bool(option.state & QStyle.StateFlag.State_Selected)
        painter.setPen(item.palette.color(QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text))
        painter.drawText(option.rect.adjusted(4,option.rect.height()-30,-4,-4),
                         Qt.AlignmentFlag.AlignCenter,item.fontMetrics.elidedText(text,Qt.TextElideMode.ElideMiddle,option.rect.width()-8))
        if key[0]==grid.pages.current_page:
            painter.setPen(QPen(item.palette.color(QPalette.ColorRole.Highlight),2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(option.rect.adjusted(2,2,-3,-3),6,6)
        painter.restore()

    def sizeHint(self,option,index):return self.parent().gridSize()


class PageGrid(QListView):
    """At most two small async requests, an 8 MiB RAM cache, no image files."""
    def __init__(self,document,parent=None,entries=None,label=None,editable=False):
        super().__init__(parent)
        self.setObjectName('pageThumbnails')
        self.document=document
        self.pages=PageModel(document.pageCount(),self,entries,label,editable)
        self.setModel(self.pages)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setMovement(QListView.Movement.Static)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setGridSize(CELL)
        self.setUniformItemSizes(True)
        self.setWrapping(True)
        self.setWordWrap(False)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection if editable else QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setItemDelegate(PageDelegate(self))
        self.setAccessibleName('Output pages' if editable else 'PDF page thumbnails')
        if editable:
            self.setDragEnabled(True)
            self.setAcceptDrops(True)
            self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
            self.setDefaultDropAction(Qt.DropAction.MoveAction)
            self.setDropIndicatorShown(True)
        self.renderer=QPdfPageRenderer(self)
        self.renderer.setRenderMode(QPdfPageRenderer.RenderMode.MultiThreaded)
        self.renderer.setDocument(document)
        self.renderer.pageRendered.connect(self.rendered)
        self.cache=OrderedDict()
        self.pending={}
        self._request_sizes={}
        self._obsolete_requests=set()
        self.wanted=set()
        self.failed=set()
        self.released=False
        self.timer=QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.pump)
        document.statusChanged.connect(self.document_status)

    def invalidate_previews(self):
        self._obsolete_requests.update(self.pending)
        self.cache.clear();self.failed.clear();self.wanted.clear()
        self.viewport().update()

    def event(self,event):
        if event.type()==QEvent.Type.DevicePixelRatioChange and hasattr(self,'cache') and not self.released:
            self.invalidate_previews()
        return super().event(event)

    def set_thumbnail_size(self,size):
        if self.released or size==self.gridSize():return
        self.invalidate_previews()
        self.setGridSize(size)
        self.doItemsLayout()
        self.viewport().update()

    def document_status(self,status):
        if status!=QPdfDocument.Status.Ready:self.release()

    def request(self,row):
        if not self.released:
            self.wanted.add(row)
            if not self.timer.isActive():self.timer.start(0)

    def pump(self):
        if self.released or not self.isVisible():return
        visible=self.viewport().rect()
        self.wanted={row for row in self.wanted if self.visualRect(self.pages.index(row,0)).intersects(visible)}
        for row in sorted(self.wanted):
            if len(self.pending)>=2:break
            key=self.pages.entries[row]
            if key in self.cache or key in self.pending.values() or key in self.failed:continue
            page,angle=key
            points=self.document.pagePointSize(page)
            if points.isEmpty():
                self.failed.add(key)
                continue
            density=max(1.,min(2.,self.devicePixelRatioF()))
            box=QSize(round((self.gridSize().width()-20)*density),round((self.gridSize().height()-42)*density))
            if angle in (90,270):box.transpose()
            size=points.toSize().scaled(box,Qt.AspectRatioMode.KeepAspectRatio)
            # Render vectors/text at twice the physical display resolution,
            # then downsample once. Direct tiny PDF rasters lose fine strokes;
            # retaining only the final image keeps cache memory bounded.
            request=self.renderer.requestPage(page,size*2)
            self.pending[request]=key
            self._request_sizes[request]=size

    def rendered(self,page,size,image,options,request):
        key=self.pending.pop(request,None)
        target=self._request_sizes.pop(request,None)
        if self.released or key is None:return
        if request in self._obsolete_requests:
            self._obsolete_requests.discard(request)
            self.viewport().update();self.timer.start(0)
            return
        if image.isNull():
            self.failed.add(key)
            if len(self.failed)>64:self.failed={key}
        else:
            paper=QImage(image.size(),QImage.Format.Format_RGB32)
            paper.fill(Qt.GlobalColor.white)
            painter=QPainter(paper)
            painter.drawImage(0,0,image)
            painter.end()
            if target is not None:
                paper=paper.scaled(target,Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation)
            if key[1]:paper=paper.transformed(QTransform().rotate(key[1]))
            self.cache[key]=paper
            while sum(value.sizeInBytes() for value in self.cache.values())>CACHE_BYTES:
                self.cache.popitem(last=False)
        self.viewport().update()
        self.timer.start(0)

    def select_rows(self,rows):
        from PySide6.QtCore import QItemSelectionModel
        self.clearSelection()
        for row in rows:
            index=self.pages.index(row,0)
            self.selectionModel().select(index,QItemSelectionModel.SelectionFlag.Select)
        if rows:
            index=self.pages.index(rows[0],0)
            self.selectionModel().setCurrentIndex(index,QItemSelectionModel.SelectionFlag.NoUpdate)
            self.scrollTo(index)

    def selected_rows(self):return sorted(index.row() for index in self.selectedIndexes())

    def move_selected(self,direction):
        rows=self.selected_rows()
        if not rows:return
        if direction<0 and rows[0]==0 or direction>0 and rows[-1]==self.pages.rowCount()-1:return
        before=rows[0]-1 if direction<0 else rows[-1]+2
        self.select_rows(self.pages.move_selection(rows,before))

    def dropEvent(self,event):
        if event.source() is not self or not event.mimeData().hasFormat(MIME):
            event.ignore()
            return
        rows=json.loads(bytes(event.mimeData().data(MIME)))
        index=self.indexAt(event.position().toPoint())
        before=index.row() if index.isValid() else self.pages.rowCount()
        self.select_rows(self.pages.move_selection(rows,before))
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def release(self):
        if self.released:return
        self.released=True
        self.timer.stop()
        self.pending.clear()
        self._request_sizes.clear()
        self._obsolete_requests.clear();self.wanted.clear();self.failed.clear();self.cache.clear()
        self.renderer.setDocument(None)
        # setDocument(None) detaches future requests, but leaves Qt's worker
        # alive until QObject destruction. Join it now, before an owning dialog
        # closes its PDF/QFile or Python tears down an undisposed window tree.
        delete(self.renderer)
        self.renderer=None
        if self.document is not None and isValid(self.document):
            self.document.statusChanged.disconnect(self.document_status)
        self.document=None
        # The navigator's label callback captures its dialog/document. Drop it
        # together with the engine so hidden widgets retain no PDF ownership.
        self.pages.label=lambda page:str(page+1)

    def hideEvent(self,event):
        self.release()
        super().hideEvent(event)
