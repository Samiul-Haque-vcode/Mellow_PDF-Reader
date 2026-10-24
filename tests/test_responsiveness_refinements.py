"""Long-document geometry, gesture anchoring and explicit cache lifetimes."""
import hashlib
import math
import pytest
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
from PIL import Image,ImageDraw
from PySide6.QtCore import Qt,QPoint,QPointF,QEvent,QCoreApplication
from PySide6.QtGui import QWheelEvent,QNativeGestureEvent,QPointingDevice
from PySide6.QtWidgets import QApplication,QAbstractSlider,QGestureEvent,QPinchGesture
from test_reader import app,pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.geometry import source_rect


@pytest.fixture
def mixed_book(tmp_path):
    path=tmp_path/'mixed-book.pdf';c=Canvas(str(path))
    image=Image.new('RGB',(900,1200),'#fafafa');draw=ImageDraw.Draw(image)
    for y in range(50,1150,35):draw.text((45,y),'Scanned mathematics: x + y = z',fill='#243f57')
    bitmap=ImageReader(image)
    for n in range(24):
        width,height=((600,800),(850,500),(420,1100))[n%3];c.setPageSize((width,height))
        if n%3==0:c.drawImage(bitmap,0,0,width,height)
        else:c.drawString(30,height-45,f'Science chapter {n+1}. Equation (2.4).')
        c.showPage()
    c.save();return path


def rendered(app,reader):
    for _ in range(150):
        reader.viewport().update();wait(app,10)
        tasks=reader.rotated_pages.tasks()
        if tasks and all(key in reader.rotated_pages.cache for key,_,_ in tasks):return
    pytest.fail('Visible PDF tiles never completed')


def gesture(reader,point,kind):
    if kind=='pinch':
        pinch=QPinchGesture();pinch.setCenterPoint(point);pinch.setLastScaleFactor(1);pinch.setScaleFactor(1.01)
        event=QGestureEvent([pinch])
    elif kind=='native':
        event=QNativeGestureEvent(Qt.NativeGestureType.ZoomNativeGesture,QPointingDevice.primaryPointingDevice(),2,
            point,point,QPointF(reader.viewport().mapToGlobal(point.toPoint())),.01,QPointF(),1)
    else:
        event=QWheelEvent(point,QPointF(reader.viewport().mapToGlobal(point.toPoint())),
            QPoint(0,1) if kind=='pixel' else QPoint(),QPoint() if kind=='pixel' else QPoint(0,2),
            Qt.MouseButton.NoButton,Qt.KeyboardModifier.ControlModifier,Qt.ScrollPhase.ScrollUpdate,False)
    QApplication.sendEvent(reader.viewport(),event)


@pytest.mark.parametrize('layout',['continuous','two_continuous'])
@pytest.mark.parametrize('kind',['wheel','pixel','native','pinch'])
def test_burst_gestures_keep_scan_anchor_and_independent_split_without_immediate_sync(app,mixed_book,tmp_path,monkeypatch,layout,kind):
    digest=hashlib.sha256(mixed_book.read_bytes()).hexdigest()
    w=Window(Store(tmp_path/'burst-book.db'),restore=False);w.show();first=w.open_pdf(mixed_book);w.split(0,0);wait(app,70)
    reader=w.secondary;reader.set_page_layout(layout);reader.set_rotation(90);reader.zoom_to(1.5);reader.jump(12,QPointF(100,120));wait(app,60)
    first.jump(4);w.focus_reader(reader);wait(app,30);before=first.state(include_history=True)
    point=QPointF(reader.viewport().rect().center());anchor=reader.point_on_page(point);assert anchor
    syncs=[];original=w.sync
    def tracked():syncs.append(True);original()
    monkeypatch.setattr(w,'sync',tracked)
    changes=[];reader.zoomFactorChanged.connect(changes.append)
    for _ in range(30):gesture(reader,point,kind)
    assert not syncs and not changes
    wait(app,80);hit=reader.point_on_page(point)
    assert hit and hit[0]==anchor[0] and (hit[1]-anchor[1]).manhattanLength()<2
    assert len(changes)==1 and w.active is reader
    assert first.state(include_history=True)==before
    assert reader.document().getAllText(12).text()==''
    assert hashlib.sha256(mixed_book.read_bytes()).hexdigest()==digest
    w.close()


@pytest.mark.parametrize('axis',['vertical','horizontal'])
@pytest.mark.parametrize('rotation',[0,90])
def test_scrollbar_action_wins_over_queued_zoom_correction(app,pdf,tmp_path,axis,rotation):
    w=Window(Store(tmp_path/'latest-scroll.db'),restore=False);w.show();r=w.open_pdf(pdf);r.set_rotation(rotation)
    r.zoom_to(2.8);r.jump(3,QPointF(80,160));wait(app,50)
    r.zoom_by(1.1)
    bar=r.verticalScrollBar() if axis=='vertical' else r.horizontalScrollBar()
    assert bar.maximum()>0
    bar.triggerAction(QAbstractSlider.SliderAction.SliderPageStepAdd);wanted=bar.value()
    wait(app,50)
    assert bar.value()==wanted and r._zoom_target is None
    w.close()


@pytest.mark.parametrize('layout',['continuous','two_continuous'])
@pytest.mark.parametrize('rotation',[0,90,180,270])
def test_visible_index_matches_mixed_height_spreads_and_stays_bounded(app,mixed_book,tmp_path,layout,rotation):
    w=Window(Store(tmp_path/'spatial.db'),restore=False);w.show();r=w.open_pdf(mixed_book)
    r.set_page_layout(layout);r.set_rotation(rotation);r.zoom_to(1.8);wait(app,40)
    for page in (0,7,12,23):
        r.jump(page,QPointF(20,180))
        rect=r.viewport().rect().translated(r.horizontalScrollBar().value(),r.verticalScrollBar().value())
        expected=[row[0] for row in r.layout_pages() if row[1].intersects(rect)]
        assert [row[0] for row in r.visible_pages()]==expected
        assert len(expected)<=4
        assert r.layout_for_page(page)[0]==page
    w.close()


def test_hidden_tabs_release_owned_rasters_and_pause_filtering_then_resume(app,mixed_book,pdf,tmp_path):
    w=Window(Store(tmp_path/'hidden-cache.db'),restore=False);w.show();r=w.open_pdf(mixed_book)
    r.set_rotation(90);r.jump(7);wait(app,50);rendered(app,r);w.grab()
    assert r.effect._cache is not None and r.rotated_pages.cache
    r.search.set_options(whole_words=True);r.search.setSearchString('Science')
    old=r.state(include_history=True);w.open_pdf(pdf)
    cursor=r.search._cursor;wait(app,80)
    assert r.effect._cache is None and not r.rotated_pages.cache and not r.rotated_pages.pending
    assert r.rotated_pages.renderer.document() is None and not r.rotated_pages.timer.isActive()
    assert not r.search.timer.isActive() and r.search._cursor==cursor and r.search.searchString()=='Science'
    assert r.document().source_file.isOpen()
    w.select(0);wait(app,50);rendered(app,r)
    for _ in range(150):
        if r.search.status()==r.search.Status.Finished:break
        wait(app,20)
    assert r.search.rowCount()==16 and r.search.whole_words
    assert r.state()['anchor_page']==old['anchor_page'] and abs(r.state()['y']-old['y'])<2
    assert r._past==old['past']
    w.grab();assert r.effect._cache is not None
    w.change_theme('Light');assert r.effect._cache is None
    w.close()
    assert r.document() is None and r.links.document() is None
    assert not r.search.timer.isActive() and not r.rotated_pages.pending and r.effect._cache is None


def test_page_dimensions_are_cached_and_document_detach_drops_geometry(app,mixed_book,tmp_path,monkeypatch):
    w=Window(Store(tmp_path/'dimensions.db'),restore=False);w.show();r=w.open_pdf(mixed_book);wait(app,30)
    doc=r.document();r.layout_pages();calls=[];original=doc.pagePointSize
    monkeypatch.setattr(doc,'pagePointSize',lambda page:calls.append(page) or original(page))
    for page in range(doc.pageCount()):assert source_rect(r,page).width()>0
    assert not calls
    r.setDocument(None)
    assert r._layout==[] and r._layout_by_page=={} and r._layout_bottoms==[]
    r.setDocument(doc);w.close()


def test_fractional_spread_at_viewport_bottom_keeps_the_visible_pixel_strip(app,mixed_book,tmp_path):
    w=Window(Store(tmp_path/'fractional-edge.db'),restore=False);w.show();r=w.open_pdf(mixed_book)
    r.set_page_layout('two_continuous');r.zoom_to(1.13713);wait(app,40)
    entry=next(row for row in r.layout_pages() if row[1].top()>r.viewport().height() and row[1].top()%1>.05)
    r.verticalScrollBar().setValue(math.floor(entry[1].top())-r.viewport().height()+1)
    assert entry[0] in [row[0] for row in r.visible_pages()]
    w.close()
