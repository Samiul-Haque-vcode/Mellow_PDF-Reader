"""On-demand PDF-region magnification and an incremental outline navigation index."""
import bisect,math
from PySide6.QtCore import QObject,Signal,QTimer,Qt,QEvent,QPoint,QPointF,QRect,QSize,QModelIndex
from PySide6.QtGui import QPainter,QColor,QImage,QTransform,QPen,QCursor
from PySide6.QtPdf import QPdfBookmarkModel,QPdfPageRenderer,QPdfDocumentRenderOptions
from PySide6.QtWidgets import QWidget
from shiboken6 import delete,isValid
from .theme import recolor,canvas_color,normalize_theme
from .style import PALETTES
from .geometry import source_rect


class LensOverlay(QWidget):
    def __init__(self,reader):
        super().__init__(reader.window())
        self.reader=reader;self.image=None;self.message='Loading…'
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName('Magnifying lens')
    def paintEvent(self,event):
        p=QPainter(self);effect=self.reader.effect
        colors=PALETTES[normalize_theme(effect.theme)]
        p.fillRect(self.rect(),QColor(canvas_color(effect.theme,effect.warmth,effect.contrast)))
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        area=self.rect().adjusted(6,6,-6,-23)
        if self.image is not None:
            target=QRect(QPoint(),self.image.size().scaled(area.size(),Qt.AspectRatioMode.KeepAspectRatio))
            target.moveCenter(area.center());p.drawImage(target,self.image)
        else:
            p.setPen(QColor(colors['muted']));p.drawText(area,Qt.AlignmentFlag.AlignCenter,self.message)
        p.setPen(QPen(QColor(colors['accent']),1));p.drawRect(self.rect().adjusted(0,0,-1,-1))
        p.setPen(QColor(colors['text']))
        p.drawText(self.rect().adjusted(8,self.height()-22,-8,-3),Qt.AlignmentFlag.AlignLeft,'Magnifier · Esc to close')
        p.end()


class ReadingAids(QObject):
    changed=Signal()
    def __init__(self,reader):
        super().__init__(reader);self.reader=reader
        self.lens_enabled=False;self.overlay=None;self.renderer=None
        self.pending=None;self.desired=None;self.last_render=None;self.pointer=None
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(35);self.timer.timeout.connect(self.render)
        self.outline=QPdfBookmarkModel(self)
        self.outline.modelReset.connect(self.rebuild)
        self.outline.rowsInserted.connect(self.rebuild)
        self.outline.dataChanged.connect(self.rebuild)
        self.index_timer=QTimer(self);self.index_timer.setSingleShot(True);self.index_timer.timeout.connect(self.index_batch)
        self.targets=[];self._stack=[];self._found=[];self._keys=[];self.index_ready=False
        self.last_chapter=None;self.chapter_revision=None
        reader.viewport().installEventFilter(self)
        reader.locationChanged.connect(self.refresh)
        self.set_document(reader.document())

    def set_document(self,document):
        self.set_lens_enabled(False)
        self.outline.setDocument(document)
        self.rebuild()

    def rebuild(self,*_):
        self.index_timer.stop();self.targets=[];self._keys=[];self._found=[]
        self.last_chapter=None;self.index_ready=False
        self._stack=[(QModelIndex(),0)] if self.reader.document() else []
        if self._stack:self.index_timer.start(0)
        self.changed.emit()

    def index_batch(self):
        document=self.reader.document()
        if not document:self._stack=[];return
        for _ in range(200):
            if not self._stack or len(self._found)>=10000:break
            parent,row=self._stack[-1]
            if row>=self.outline.rowCount(parent):self._stack.pop();continue
            self._stack[-1]=(parent,row+1)
            index=self.outline.index(row,0,parent)
            page=index.data(QPdfBookmarkModel.Role.Page.value)
            point=index.data(QPdfBookmarkModel.Role.Location.value)
            point=point if isinstance(point,QPointF) else QPointF()
            if isinstance(page,int) and 0<=page<document.pageCount() and math.isfinite(point.x()) and math.isfinite(point.y()):
                size=document.pagePointSize(page)
                x=point.x() if 0<=point.x()<=size.width() else 0.
                y=point.y() if 0<=point.y()<=size.height() else 0.
                self._found.append((page,round(y,2),round(x,2)))
            if self.outline.rowCount(index):self._stack.append((index,0))
        if self._stack and len(self._found)<10000:self.index_timer.start(0);return
        self.targets=sorted(set(self._found));self._keys=self.targets
        self._stack=[];self._found=[];self.index_ready=True;self.changed.emit()

    def chapter_target(self,direction):
        if not self.index_ready or not self.targets or not self.reader.document():return None
        r=self.reader
        if self.last_chapter is not None and self.chapter_revision==r._revision:
            current=self.last_chapter
        else:
            state=r.state();current=(state.get('anchor_page',state['page']),max(0.,state.get('y',0))+2.,max(0.,state.get('x',0)))
        index=bisect.bisect_right(self._keys,current)-1
        index+=1 if direction>0 else -1
        return self.targets[index] if 0<=index<len(self.targets) else None

    def chapter_step(self,direction):
        target=self.chapter_target(direction)
        if target is None:return False
        page,y,x=target
        self.reader.jump(page,QPointF(x,y))
        self.last_chapter=target;self.chapter_revision=self.reader._revision
        self.changed.emit();return True

    def set_lens_enabled(self,enabled):
        enabled=bool(enabled and self.reader.document() and self.reader.isVisible())
        if enabled==self.lens_enabled:return
        self.lens_enabled=enabled
        if enabled:
            self.overlay=LensOverlay(self.reader)
            self.renderer=QPdfPageRenderer(self)
            self.renderer.setRenderMode(QPdfPageRenderer.RenderMode.MultiThreaded)
            self.renderer.setDocument(self.reader.document());self.renderer.pageRendered.connect(self.rendered)
            self.pointer=self.reader.viewport().mapFromGlobal(QCursor.pos())
            self.refresh()
        else:
            self.timer.stop();self.pending=None;self.desired=None;self.last_render=None;self.pointer=None
            if self.overlay is not None:self.overlay.hide();self.overlay.deleteLater();self.overlay=None
            if self.renderer is not None:
                self.renderer.setDocument(None);delete(self.renderer);self.renderer=None
        self.changed.emit()

    def eventFilter(self,obj,event):
        if self.lens_enabled:
            if event.type()==QEvent.Type.MouseMove:
                self.pointer=event.position().toPoint();self.refresh()
            elif event.type()==QEvent.Type.Leave:
                self.pointer=None;self.refresh()
            elif event.type() in (QEvent.Type.Resize,QEvent.Type.DevicePixelRatioChange):self.refresh()
        return False

    def refresh(self,*_):
        if not self.lens_enabled or self.overlay is None:return
        r=self.reader;view=r.viewport()
        hit=r.point_on_page(QPointF(self.pointer)) if self.pointer is not None and view.rect().contains(self.pointer) else None
        if hit is None or not r.isVisible():
            self.desired=None;self.overlay.hide();self.timer.stop();return
        page,point=hit
        width=min(292,max(40,view.width()-12));height=min(206,max(40,view.height()-12))
        self.overlay.resize(width,height)
        x=self.pointer.x()+18;y=self.pointer.y()+18
        if x+width>view.width():x=self.pointer.x()-width-18
        if y+height>view.height():y=self.pointer.y()-height-18
        local=QPoint(max(0,min(x,view.width()-width)),max(0,min(y,view.height()-height)))
        self.overlay.move(view.mapTo(self.reader.window(),local));self.overlay.show();self.overlay.raise_()
        entry=next(iter(r.page_entries(page)),None)
        if entry is None:return
        points=r.document().pagePointSize(page)
        if points.isEmpty():return
        density=max(1.,min(2.,r.devicePixelRatioF()))
        factor=min(entry[2]*2*density,65535/max(points.width(),points.height()))
        full=QSize(max(1,round(points.width()*factor)),max(1,round(points.height()*factor)))
        box=QSize(max(1,round((width-12)*density)),max(1,round((height-29)*density)))
        if r.rotation in (90,270):box.transpose()
        bounds=source_rect(r,page)
        bounds=QRect(round(bounds.x()*factor),round(bounds.y()*factor),max(1,round(bounds.width()*factor)),max(1,round(bounds.height()*factor)))
        w=min(box.width(),bounds.width());h=min(box.height(),bounds.height())
        clip=QRect(max(bounds.left(),min(round(point.x()*factor)-w//2,bounds.right()-w+1)),
                   max(bounds.top(),min(round(point.y()*factor)-h//2,bounds.bottom()-h+1)),w,h)
        effect=r.effect
        descriptor=(page,full.width(),full.height(),clip.x(),clip.y(),clip.width(),clip.height(),r.rotation,effect.theme,effect.preserve,effect.warmth,effect.contrast)
        if descriptor!=self.desired:
            self.desired=descriptor
            if descriptor!=self.last_render:
                self.overlay.image=None;self.overlay.message='Loading…';self.overlay.update()
        if descriptor!=self.last_render and not self.timer.isActive():self.timer.start()

    def render(self):
        if not self.lens_enabled or self.pending is not None or self.desired is None:return
        data=self.desired
        options=QPdfDocumentRenderOptions();options.setScaledSize(QSize(data[1],data[2]))
        clip=QRect(*data[3:7]);options.setScaledClipRect(clip)
        request=self.renderer.requestPage(data[0],clip.size(),options)
        self.pending=(request,data)

    def rendered(self,page,size,image,options,request):
        if not self.lens_enabled or self.pending is None or request!=self.pending[0]:return
        data=self.pending[1];self.pending=None
        if data==self.desired and self.overlay is not None and not image.isNull():
            paper=QImage(image.size(),QImage.Format.Format_RGB32);paper.fill(Qt.GlobalColor.white)
            painter=QPainter(paper);painter.drawImage(0,0,image);painter.end()
            if data[7]:paper=paper.transformed(QTransform().rotate(data[7]))
            self.overlay.image=recolor(paper,data[8],data[9],data[10],data[11])
            self.overlay.update();self.last_render=data
        if data==self.desired and self.overlay is not None and image.isNull():
            # A failed render must wait for new input, not retry on a zero-ms loop.
            self.overlay.image=None;self.overlay.message='Preview unavailable'
            self.overlay.update();self.last_render=data
        if self.desired is not None and self.desired!=self.last_render:self.timer.start(0)
