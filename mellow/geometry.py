"""Public-API page layout mapping for Qt PDF Widgets.

QPdfView has no public viewport-to-page conversion. Mirror its documented stacked
page layout, including point/DPI conversion and fit modes. Regression tests cover
mixed page sizes, margins, scrolling and all zoom modes.
"""
from bisect import bisect_right
from PySide6.QtCore import QPointF, QRectF, QSize,QSizeF
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTransform
from PySide6.QtPdfWidgets import QPdfView


class PageLayout(list):
    """Build lookup/visibility indices alongside the actual page rectangles."""
    def __init__(self):
        super().__init__()
        self.by_page={};self.tops=[];self.bottoms=[];self.extent=(0,0)
    def add(self,page,x,y,width,height,scale):
        entry=(page,QRectF(x,y,width,height),scale)
        self.append(entry);self.by_page[page]=entry;self.tops.append(y)
        right,bottom=self.extent
        self.extent=(max(right,x+width),max(bottom,y+height))
        self.bottoms.append(self.extent[1])


def document_sizes(document):
    count=document.pageCount()
    cached=getattr(document,'_mellow_page_sizes',None)
    if cached is None or len(cached)!=count:
        cached=tuple(document.pagePointSize(page) for page in range(count))
        document._mellow_page_sizes=cached
    return cached


def page_layout(view):
    document = view.document()
    if not document:
        return PageLayout()
    dpi = view.logicalDpiX() / 72
    if getattr(view,'facing_pages',False): return facing_layout(view,dpi)
    margins = view.documentMargins()
    width, height = view.viewport().width(), view.viewport().height()
    mode = view.zoomMode()
    sizes = []
    pages = range(document.pageCount())
    if view.pageMode() == QPdfView.PageMode.SinglePage:
        pages = [max(0,min(view.pageNavigator().currentPage(),document.pageCount()-1))] if document.pageCount() else []
    cached=document_sizes(document)
    for page in pages:
        points = source_rect(view,page).size() if any(getattr(view,'crop',())) else cached[page]
        if getattr(view,'rotation',0) in (90,270): points=points.transposed()
        base = (points * dpi).toSize()
        if mode == QPdfView.ZoomMode.Custom:
            size = (points * (dpi * view.zoomFactor())).toSize()
        elif mode == QPdfView.ZoomMode.FitToWidth:
            scale = max(1, width-margins.left()-margins.right()) / max(1, base.width())
            size = base * scale
        else:
            size = base.scaled(QSize(max(1, width-margins.left()-margins.right()),
                                    max(1, height-view.pageSpacing())), QtKeepAspectRatio)
        sizes.append((page, size, points))
    total = max((s.width() for _, s, _ in sizes), default=0) + margins.left()+margins.right()
    y = margins.top()
    result = PageLayout()
    for page, size, points in sizes:
        x = (max(total, width)-size.width())//2
        result.add(page,x,y,size.width(),size.height(),size.width()/max(1,points.width()))
        y += size.height()+view.pageSpacing()
    return result


from PySide6.QtCore import Qt
QtKeepAspectRatio = Qt.AspectRatioMode.KeepAspectRatio


def page_at(view, point):
    pos = QPointF(point) + QPointF(view.horizontalScrollBar().value(), view.verticalScrollBar().value())
    layouts=view.layout_pages()
    index=bisect_right(view._layout_tops,pos.y())-1
    while index>0 and view._layout_tops[index-1]==view._layout_tops[index]: index-=1
    for page,rect,scale in layouts[max(0,index):max(0,index)+2]:
        if scale>0 and rect.contains(pos):
            point=(pos-rect.topLeft())/scale
            return page,page_transform(view,page).inverted()[0].map(point)
    return None


def viewport_point(view, page, point):
    entry=view.layout_for_page(page)
    if entry:
        _,rect,scale=entry
        return (rect.topLeft() + page_transform(view,page).map(QPointF(point))*scale
                - QPointF(view.horizontalScrollBar().value(), view.verticalScrollBar().value()))
    return QPointF()


def page_transform(view,page):
    crop=source_rect(view,page)
    size=crop.size()
    angle=getattr(view,'rotation',0)
    rotation={0:QTransform(),90:QTransform(0,1,-1,0,size.height(),0),
              180:QTransform(-1,0,0,-1,size.width(),size.height()),
              270:QTransform(0,-1,1,0,0,size.width())}[angle]
    return QTransform.fromTranslate(-crop.left(),-crop.top())*rotation


def source_rect(view,page):
    sizes=document_sizes(view.document())
    size=sizes[page] if 0<=page<len(sizes) else QSizeF()
    left,top,right,bottom=getattr(view,'crop',(0,0,0,0))
    return QRectF(size.width()*left/100,size.height()*top/100,
                  size.width()*(1-(left+right)/100),size.height()*(1-(top+bottom)/100))


def spreads(count,cover=True):
    rows=[(None,0)] if cover and count else []
    start=1 if cover else 0
    rows.extend((page,page+1 if page+1<count else None) for page in range(start,count,2))
    return rows


def facing_layout(view,dpi):
    document=view.document()
    cached=document_sizes(document)
    cropped=any(view.crop)
    rows=spreads(document.pageCount(),view.cover_separate)
    if view.page_layout_mode=='two':
        current=max(0,min(view.pageNavigator().currentPage(),document.pageCount()-1))
        rows=[row for row in rows if current in row]
    margins=view.documentMargins()
    gap=max(8,view.pageSpacing())
    available_w=max(1,view.viewport().width()-margins.left()-margins.right())
    available_h=max(1,view.viewport().height()-margins.top()-margins.bottom())
    measured=[]
    for left,right in rows:
        sizes=[(source_rect(view,page).size() if cropped else cached[page]) if page is not None else None for page in (left,right)]
        if view.rotation in (90,270): sizes=[size.transposed() if size else None for size in sizes]
        widths=[size.width() if size else next(s.width() for s in sizes if s) for size in sizes]
        height=max(size.height() for size in sizes if size)
        scale=dpi*view.zoomFactor() if view.zoomMode()==view.ZoomMode.Custom else max(.001,(available_w-gap)/sum(widths))
        if view.zoomMode()==view.ZoomMode.FitInView: scale=min(scale,available_h/height)
        measured.append(((left,right),sizes,widths,scale,height))
    total=max((sum(widths)*scale+gap for _,_,widths,scale,_ in measured),default=0)
    total=max(total+margins.left()+margins.right(),view.viewport().width())
    y=margins.top();result=PageLayout()
    for row,sizes,widths,scale,height in measured:
        x=(total-(sum(widths)*scale+gap))/2
        for page,size,width in zip(row,sizes,widths):
            if page is not None:result.add(page,x,y,width*scale,size.height()*scale,scale)
            x+=width*scale+gap
        y+=height*scale+view.pageSpacing()
    return result
