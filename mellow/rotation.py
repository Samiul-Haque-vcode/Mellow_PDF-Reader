"""Bounded asynchronous tiles for rotated pages and facing-page spreads.

PDF text/link coordinates remain in the original source system. Only visible
regions render at the requested pixel density; no full-page high-zoom bitmap or
permanent page-image cache is created.
"""
from collections import OrderedDict
import math
from PySide6.QtCore import QObject,QSize,QTimer,QPointF,QRect,QRectF
from PySide6.QtGui import QColor,QPainter,QTransform
from PySide6.QtPdf import QPdfPageRenderer,QPdfDocumentRenderOptions,QPdfPageNavigator
from .theme import canvas_color

TILE=768
CACHE_BYTES=32*1024*1024


class RotatedPages(QObject):
    def __init__(self,view):
        super().__init__(view)
        self.view=view
        self.navigator=QPdfPageNavigator(self)
        self.renderer=QPdfPageRenderer(self)
        self.renderer.setRenderMode(QPdfPageRenderer.RenderMode.MultiThreaded)
        self.renderer.pageRendered.connect(self.rendered)
        self.cache=OrderedDict();self.pending={};self.failed=set()
        self.syncing=False
        self.timer=QTimer(self);self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.sync)
        self.navigator.currentPageChanged.connect(self.queue_sync)
        for signal in (view.verticalScrollBar().sliderMoved,view.verticalScrollBar().actionTriggered):
            signal.connect(lambda *_:QTimer.singleShot(0,self.update_navigation))
    def set_document(self,document):
        self.renderer.setDocument(document)
        self.cache.clear();self.pending.clear();self.failed.clear();self.timer.stop()
    def pause(self):
        self.set_document(None)
    def resume(self):
        self.renderer.setDocument(self.view.document())
        self.queue_sync()
    def sync(self):
        v=self.view
        if not v.custom_rendering or not v.document() or self.syncing: return
        self.syncing=True
        try:
            v.layout_pages()
            right,bottom=v._layout_extent
            right+=v.documentMargins().right();bottom+=v.documentMargins().bottom()
            v.horizontalScrollBar().setRange(0,max(0,math.ceil(right)-v.viewport().width()))
            v.verticalScrollBar().setRange(0,max(0,math.ceil(bottom)-v.viewport().height()))
            v.horizontalScrollBar().setPageStep(v.viewport().width());v.verticalScrollBar().setPageStep(v.viewport().height())
        finally:self.syncing=False
        v.viewport().update()
    def queue_sync(self,*_):
        if self.view.custom_rendering:self.sync();self.timer.start(0)
    def scrolled(self):
        self.view.locationChanged.emit();self.view.viewport().update()
    def update_navigation(self):
        v=self.view
        if not v.custom_rendering:return
        if self.syncing or not v.document() or v._positioning:return
        sy=v.verticalScrollBar().value()
        visible=[p for p,r,_ in v.visible_pages() if r.top()<=sy+v.documentMargins().top()+1 and r.bottom()>sy]
        page=v.pageNavigator().currentPage()
        if page not in visible:
            page=visible[0] if visible else next((p for p,r,_ in v.layout_pages() if r.bottom()>sy),0)
            self.navigator.update(page,QPointF(),v.zoomFactor())
        v.locationChanged.emit();v.viewport().update()
    def rendered(self,page,size,image,options,request_id):
        key=self.pending.pop(request_id,None)
        if key is None:return
        if key[-1] and not image.isNull():image=image.transformed(QTransform().rotate(key[-1]))
        if page!=key[1]:return
        if image.isNull() or (image.width(),image.height())!=key[6:8]:
            self.failed.add(key)
            if len(self.failed)>32:self.failed={key}
        elif key[0]==id(self.view.document()) and key[-1]==self.view.rotation:
            self.cache[key]=image
            while self.cache and sum(i.sizeInBytes() for i in self.cache.values())>CACHE_BYTES:self.cache.popitem(last=False)
        self.view.viewport().update()
    def tasks(self):
        v=self.view;sx,sy=v.horizontalScrollBar().value(),v.verticalScrollBar().value()
        visible=QRectF(v.viewport().rect()).translated(sx,sy)
        # Exceptionally large/high-DPI windows still have a bounded visible raster.
        density=min(v.devicePixelRatioF(),math.sqrt(5_000_000/max(1,visible.width()*visible.height())))
        tasks=[]
        for page,rect,_ in v.visible_pages():
            part=rect.intersected(visible)
            if part.isEmpty():continue
            width,height=max(1,round(rect.width()*density)),max(1,round(rect.height()*density))
            dx,dy=width/rect.width(),height/rect.height()
            first_x=max(0,int((part.left()-rect.left())*dx)//TILE)
            last_x=min((width-1)//TILE,int((part.right()-rect.left())*dx)//TILE)
            first_y=max(0,int((part.top()-rect.top())*dy)//TILE)
            last_y=min((height-1)//TILE,int((part.bottom()-rect.top())*dy)//TILE)
            for row in range(first_y,last_y+1):
                for col in range(first_x,last_x+1):
                    tile=QRect(col*TILE,row*TILE,min(TILE,width-col*TILE),min(TILE,height-row*TILE))
                    key=(id(v.document()),page,width,height,tile.x(),tile.y(),tile.width(),tile.height(),tuple(v.crop),v.rotation)
                    target=QRectF(rect.x()-sx+tile.x()/dx,rect.y()-sy+tile.y()/dy,tile.width()/dx,tile.height()/dy)
                    angle=v.rotation
                    original_w,original_h=(height,width) if angle in (90,270) else (width,height)
                    transforms={0:QTransform(),90:QTransform(0,1,-1,0,original_h,0),180:QTransform(-1,0,0,-1,original_w,original_h),270:QTransform(0,-1,1,0,0,original_w)}
                    left,top,right,bottom=v.crop
                    full_w=round(original_w/(1-(left+right)/100))
                    full_h=round(original_h/(1-(top+bottom)/100))
                    clip=transforms[angle].inverted()[0].mapRect(QRectF(tile)).toAlignedRect()
                    clip.translate(round(full_w*left/100),round(full_h*top/100))
                    tasks.append((key,target,clip))
        return tasks
    def paint(self,painter):
        v=self.view
        painter.fillRect(v.viewport().rect(),QColor(canvas_color(v.effect.theme,v.effect.warmth,v.effect.contrast)))
        sx,sy=v.horizontalScrollBar().value(),v.verticalScrollBar().value()
        for _,rect,_ in v.visible_pages():
            if rect.translated(-sx,-sy).intersects(v.viewport().rect()):painter.fillRect(rect.translated(-sx,-sy),QColor('white'))
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for key,target,tile in self.tasks():
            if key in self.cache:
                painter.drawImage(target,self.cache[key]);self.cache.move_to_end(key)
            elif key in self.failed:
                painter.setPen(QColor('#826e50'));painter.drawText(target.adjusted(8,8,-8,-8),'Unable to render this region')
            elif key not in self.pending.values() and len(self.pending)<2:
                options=QPdfDocumentRenderOptions()
                full=QSize(key[2],key[3])
                if v.rotation in (90,270):full.transpose()
                left,top,right,bottom=key[-2]
                full=QSize(round(full.width()/(1-(left+right)/100)),round(full.height()/(1-(top+bottom)/100)))
                options.setScaledSize(full);options.setScaledClipRect(tile)
                request=self.renderer.requestPage(key[1],tile.size(),options)
                self.pending[request]=key
