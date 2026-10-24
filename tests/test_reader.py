import os
os.environ['QT_QPA_PLATFORM']='offscreen'
# Every Window below receives an isolated Store.

import pytest
from reportlab.pdfgen.canvas import Canvas
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer, QModelIndex
from PySide6.QtGui import QImage
from pypdf import PdfReader
from mellow.app import Window
from mellow.storage import Store
from mellow import utilities

@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])

def wait(app, ms=250):
    loop=QEventLoop()
    QTimer.singleShot(ms,loop.quit)
    loop.exec()

@pytest.fixture
def pdf(tmp_path):
    path=tmp_path/'textbook.pdf'
    c=Canvas(str(path))
    for i in range(8):
        c.bookmarkPage(f'p{i}')
        c.addOutlineEntry(f'Chapter {i+1}',f'p{i}',0)
        c.drawString(50,750,f'Mellow chapter {i+1} Equation (2.4)')
        c.setFillColorRGB(0.1,0.3,0.8)
        c.rect(50,500,150,100,fill=1)
        c.setFillColorRGB(0,0,0)
        c.linkRect('Go to chapter 3','p2',(50,700,250,730))
        c.showPage()
    c.save()
    return path

def test_reader(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'meta.db'),restore=False)
    w.show()
    r=w.open_pdf(str(pdf))
    wait(app)
    assert r.document().pageCount()==8
    assert not r.document().render(0,r.size()).isNull()
    r.jump(3)
    wait(app)
    assert r.pageNavigator().currentPage()==3
    r.search.setSearchString('Mellow')

    for _ in range(30):
        if r.search.rowCount(QModelIndex()) == 8: break
        wait(app,100)
    assert r.search.rowCount(QModelIndex())==8
    r.setCurrentSearchResultIndex(0)
    result=r.search.resultAtIndex(0)
    assert result.page()==0
    r.jump(3)
    wait(app)
    w.split(0,0)
    w.secondary.jump(6)
    wait(app)
    assert w.secondary.pageNavigator().currentPage()==6
    assert r.pageNavigator().currentPage()==3
    for theme in ['Sepia','Black','Dark','Original']:
        w.change_theme(theme)
        wait(app)
        assert not w.grab().isNull()
    w.focus_reader(w.secondary)
    w.save_session()
    state=w.store.get('session')
    assert state['secondary']['page']==6
    assert state['documents'][0]['page']==3
    w.close()
    restored=Window(w.store,restore=False)
    restored.show()
    restored.restore_session()
    wait(app,600)
    assert restored.secondary.pageNavigator().currentPage()==6
    assert restored.readers[0].pageNavigator().currentPage()==3
    restored.close()

def test_storage(tmp_path,pdf):
    s=Store(tmp_path/'data.db')
    s.add('favorite',str(pdf),4,'Equation')
    out=tmp_path/'backup.json'
    s.export_favorites(out)
    s.import_favorites(out)
    assert len(s.locations('favorite'))==2
    s.relocate(str(pdf),str(tmp_path/'moved.pdf'))
    assert all(x['path'].endswith('moved.pdf') for x in s.locations('favorite'))
    out.write_text('[{"path":"a","title":"x","page":-1}]')
    with pytest.raises(ValueError): s.import_favorites(out)
    assert len(s.locations('favorite'))==2

def test_utilities(pdf,tmp_path):
    extracted=tmp_path/'extract.pdf'
    merged=tmp_path/'merge.pdf'
    utilities.extract(pdf,extracted,'2-3,7')
    assert len(PdfReader(extracted).pages)==3
    utilities.merge([pdf,extracted],merged)
    assert len(PdfReader(merged).pages)==11
    with pytest.raises(ValueError): utilities.extract(pdf,pdf,'1')
    for bad in ['0','9','3-1','1-2-3']:
        with pytest.raises(ValueError): utilities.page_range(bad,8)

@pytest.fixture
def technical_pdf(tmp_path):
    from PIL import Image
    source=tmp_path/'technical-source.pdf'
    c=Canvas(str(source),pagesize=(600,800))
    sizes=[(600,800),(800,500),(420,1100),(600,800),(600,800)]
    for page,size in enumerate(sizes):
        c.setPageSize(size)
        c.bookmarkPage(f'chapter{page}',fit='XYZ',left=0,top=size[1]-30,zoom=1)
        c.addOutlineEntry(f'Chapter {page+1}',f'chapter{page}',0)
        if page==0:
            c.drawString(40,700,'See Figure 3.8 and Equation (2.4).')
            c.drawString(40,640,'Linked Figure 3.8')
            c.linkRect('figure','chapter2',(35,625,230,660))
        elif page==1:
            c.drawString(40,400,'Section 4.2 is discussed later.')
        elif page==2:
            c.drawString(40,1000,'Figure 3.8: A mathematical diagram')
            c.setFillColorRGB(.05,.25,.8)
            c.rect(40,700,180,160,fill=1)
            c.setFillColorRGB(0,0,0)
            c.drawString(40,600,'x + y = z                    (2.4)')
        elif page==3:
            c.drawString(40,700,'4.2 The central theorem')
            c.drawString(40,650,'Table 5.1: Comparison')
        else:
            image=Image.new('RGB',(100,100),'gray')
            c.drawInlineImage(image,40,500,200,200)
        c.showPage()
    c.save()
    output=tmp_path/'technical.pdf'
    from pypdf import PdfWriter
    writer=PdfWriter(clone_from=source)
    writer.set_page_label(0,1,style='/r')
    writer.set_page_label(2,4,style='/D',start=1)
    writer.write(output)
    return output


def test_link_preview_preserves_location(app,technical_pdf,tmp_path):
    from PySide6.QtCore import QPointF,Qt
    from PySide6.QtTest import QTest
    w=Window(Store(tmp_path/'links.db'),restore=False)
    w.show()
    r=w.open_pdf(technical_pdf)
    wait(app)
    point=r.point_in_view(0,QPointF(100,155))
    hit=r.point_on_page(point)
    assert hit[0]==0
    assert abs(hit[1].y()-155)<1
    target=r.internal_link(point)
    assert target is not None and target.page==2
    before=r.state()
    QTest.mouseClick(r.viewport(),Qt.MouseButton.LeftButton,pos=point.toPoint())
    wait(app)
    assert len(w.popups)==1
    assert r.state()['vertical']==before['vertical']
    assert w.popups[0].reader.pageNavigator().currentPage()==2
    popup=w.popups[0]
    popup.set_pinned(True)
    popup.send_opposite()
    wait(app)
    assert w.secondary is not None
    assert w.secondary.pageNavigator().currentPage()==2
    assert r.pageNavigator().currentPage()==0
    w.close()
    wait(app,20)


@pytest.mark.parametrize('label,page',[('Figure 3.8',2),('Equation (2.4)',2),('Section 4.2',3),('Table 5.1',3)])
def test_offline_reference_matching(app,technical_pdf,label,page):
    from PySide6.QtPdf import QPdfDocument
    from mellow.references import ReferenceResolver
    doc=QPdfDocument()
    doc.load(str(technical_pdf))
    resolver=ReferenceResolver(doc,label,0)
    completed=[]
    resolver.finished.connect(completed.append)
    resolver.start()
    for _ in range(30):
        if completed: break
        wait(app,30)
    assert completed and completed[0]
    assert completed[0][0].page==page
    assert completed[0][0].y>=0
    resolver.cancel()


def test_no_reference_in_scan_and_cancel(app,technical_pdf):
    from PySide6.QtPdf import QPdfDocument
    from mellow.references import ReferenceResolver
    doc=QPdfDocument()
    doc.load(str(technical_pdf))
    assert doc.getAllText(4).text()==''
    resolver=ReferenceResolver(doc,'Figure 99.1',0)
    results=[]
    resolver.finished.connect(results.append)
    resolver.start()
    wait(app,250)
    assert results==[[]]
    cancelled=ReferenceResolver(doc,'Figure 3.8',0)
    cancelled.start()
    cancelled.cancel()
    wait(app,50)
    assert cancelled.count==0


def test_favorites_in_both_split_panes(app,pdf,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'favorites.db'),restore=False)
    w.show()
    a=w.open_pdf(pdf)
    b=w.open_pdf(technical_pdf)
    wait(app)
    w.split(0,1)
    wait(app)
    secondary=w.secondary
    secondary.jump(3)
    before=secondary.state()
    w.focus_reader(a)
    target=w.open_saved(dict(path=str(technical_pdf),page=2,x=0,y=0))
    wait(app)
    assert w.secondary is secondary
    assert secondary.state()['vertical']==before['vertical']
    assert target is w.readers[w.tabs.currentIndex()]
    assert target.pageNavigator().currentPage()==2
    w.focus_reader(secondary)
    target=w.open_saved(dict(path=str(pdf),page=5,x=0,y=0))
    wait(app)
    assert target is secondary
    assert secondary.pageNavigator().currentPage()==5
    assert w.readers[w.tabs.currentIndex()].pageNavigator().currentPage()==2
    w.close()


def test_scroll_history_tabs_and_session(app,pdf,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'positions.db'),restore=False)
    w.show()
    a=w.open_pdf(pdf)
    wait(app)
    a.setZoomMode(a.ZoomMode.Custom)
    a.setZoomFactor(1.5)
    wait(app)
    a.verticalScrollBar().setValue(1637)
    a.horizontalScrollBar().setValue(90)
    wait(app)
    snapshot=a.state()
    a.jump(6)
    wait(app)
    a.back()
    wait(app)
    assert a.verticalScrollBar().value()==snapshot['vertical']
    assert a.horizontalScrollBar().value()==snapshot['horizontal']
    a.forward()
    wait(app)
    assert a.pageNavigator().currentPage()==6
    a.back()
    w.open_pdf(technical_pdf)
    wait(app)
    w.tabs.setCurrentIndex(0)
    wait(app)
    assert a.verticalScrollBar().value()==snapshot['vertical']
    w.close()
    restored=Window(w.store,restore=False)
    restored.show()
    restored.restore_session()
    wait(app)
    assert restored.readers[0].verticalScrollBar().value()==snapshot['vertical']
    restored.close()


def test_session_missing_file_keeps_active_identity(app,pdf,technical_pdf,tmp_path):
    store=Store(tmp_path/'missing.db')
    store.set('session',dict(documents=[dict(path=str(tmp_path/'missing.pdf'),page=1),
        dict(path=str(pdf),page=3),dict(path=str(technical_pdf),page=2)],active_path=str(technical_pdf)))
    w=Window(store,restore=False)
    messages=[]
    w.error=messages.append
    w.show()
    w.restore_session()
    wait(app)
    assert len(w.readers)==2
    assert w.active.path==str(technical_pdf)
    assert w.active.pageNavigator().currentPage()==2
    assert len(messages)==1 and 'missing.pdf' in messages[0]
    w.close()


def test_printed_labels_and_zoom(app,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'labels.db'),restore=False)
    w.show()
    r=w.open_pdf(technical_pdf)
    wait(app)
    assert r.document().pageLabel(0)=='i'
    w.page.setCurrentText('ii')
    w.go_page()
    wait(app)
    assert r.pageNavigator().currentPage()==1
    w.page.setCurrentText('#4')
    w.go_page()
    wait(app)
    assert r.pageNavigator().currentPage()==3
    w.fit.setCurrentText('125%')
    w.set_zoom_text()
    wait(app)
    assert r.zoomFactor()==1.25
    w.close()


def test_fullscreen_reveal_and_exit(app,pdf,tmp_path):
    from PySide6.QtTest import QTest
    from PySide6.QtCore import QPoint,Qt
    w=Window(Store(tmp_path/'fullscreen.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    w.fullscreen()
    wait(app)
    assert w.isFullScreen()
    assert not w.toolbar.isVisible() and not w.tabstrip.isVisible()
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QEvent,QPointF
    event=QMouseEvent(QEvent.Type.MouseMove,QPointF(200,1),QPointF(200,1),Qt.MouseButton.NoButton,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(r.viewport(),event)
    wait(app)
    assert w.toolbar.isVisible() and w.tabstrip.isVisible()
    QTest.keyClick(w,Qt.Key.Key_Escape)
    wait(app)
    assert not w.isFullScreen() and w.toolbar.isVisible()
    w.close()


def test_theme_pixel_colors_and_original(app):
    from PySide6.QtGui import QColor
    from mellow.theme import recolor
    image=QImage(3,1,QImage.Format.Format_RGBA8888)
    image.setPixelColor(0,0,QColor('white'))
    image.setPixelColor(1,0,QColor('black'))
    image.setPixelColor(2,0,QColor('#1144cc'))
    sepia=recolor(image,'Sepia')
    assert sepia.pixelColor(0,0).name()=='#faf1d9'
    assert sepia.pixelColor(1,0).name()=='#634f38'
    assert sepia.pixelColor(2,0)==image.pixelColor(2,0)
    assert recolor(image,'Original')==image
    assert recolor(image,'Dark').pixelColor(0,0).name()=='#242622'


def test_atomic_cancellation_images_and_hardlinks(app,pdf,tmp_path):
    from threading import Event
    output=tmp_path/'safe.pdf'
    output.write_bytes(b'existing destination')
    cancel=Event()
    cancel.set()
    with pytest.raises(utilities.Cancelled): utilities.merge([pdf],output,cancel)
    assert output.read_bytes()==b'existing destination'
    with pytest.raises(ValueError): utilities.images_to_pdf([tmp_path/'absent.png'],output)
    assert output.read_bytes()==b'existing destination'
    image=QImage(50,70,QImage.Format.Format_RGB32)
    image.fill(0xff3050a0)
    first,second=tmp_path/'a.png',tmp_path/'b.png'
    image.save(str(first))
    image.save(str(second))
    utilities.images_to_pdf([first,second],output,'Letter')
    reader=PdfReader(output)
    assert len(reader.pages)==2
    assert round(float(reader.pages[0].mediabox.width))==612
    link=tmp_path/'hardlink.pdf'
    os.link(pdf,link)
    with pytest.raises(ValueError): utilities.extract(pdf,link,'1')
    assert not list(tmp_path.glob('.mellow-*'))


def test_portable_directory(tmp_path):
    from mellow.config import data_directory
    exe=tmp_path/'MellowPDFReader.exe'
    assert data_directory(True,exe)==tmp_path/'mellow-data'
    (tmp_path/'portable.ini').touch()
    assert data_directory(False,exe)==tmp_path/'mellow-data'


def test_worker_completion_and_cancellation(app,pdf,tmp_path):
    from mellow.jobs import FileJob
    output=tmp_path/'worker.pdf'
    job=FileJob(lambda cancel,progress: utilities.extract(pdf,output,'1-3',cancel,progress),output)
    success=[]
    job.succeeded.connect(success.append)
    job.start()
    for _ in range(50):
        wait(app,20)
        if not job.isRunning(): break
    job.wait(2000)
    wait(app,20)
    assert success==[str(output)]
    assert len(PdfReader(output).pages)==3
    cancelled=FileJob(lambda cancel,progress: utilities.merge([pdf],output,cancel,progress),output)
    cancelled.cancel()
    signals=[]
    cancelled.cancelled.connect(lambda: signals.append(True))
    cancelled.start()
    cancelled.wait(2000)
    wait(app,20)
    assert signals==[True]


def test_search_back_and_preview_document_close(app,pdf,tmp_path):
    from mellow.references import Target
    from PySide6.QtCore import QCoreApplication,QEvent
    w=Window(Store(tmp_path/'searchback.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    r.jump(4)
    wait(app)
    original=r.state()
    r.search.setSearchString('Mellow')
    for _ in range(30):
        if r.search.rowCount(QModelIndex())==8: break
        wait(app,100)
    r.visit_search(0)
    wait(app)
    assert r.pageNavigator().currentPage()==0
    r.back()
    wait(app)
    assert r.verticalScrollBar().value()==original['vertical']
    w.preview(r,Target(2))
    wait(app)
    w.close_tab(0)
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    wait(app)
    assert not w.readers and not w.popups
    w.close()


def test_split_layout_session_swap_and_focus(app,pdf,technical_pdf,tmp_path):
    from PySide6.QtCore import Qt
    w=Window(Store(tmp_path/'layout.db'),restore=False)
    w.show()
    a=w.open_pdf(pdf)
    w.open_pdf(technical_pdf)
    wait(app)
    w.split(0,1)
    wait(app)
    w.orientation()
    w.swap()
    w.splitter.setSizes([280,500])
    w.focus_reader(w.secondary)
    w.secondary.jump(3)
    a.jump(5)
    wait(app)
    w.close()
    restored=Window(w.store,restore=False)
    restored.show()
    restored.restore_session()
    wait(app)
    assert restored.splitter.orientation()==Qt.Orientation.Vertical
    assert restored.splitter.widget(0) is restored.secondary
    assert restored.active is restored.secondary
    assert restored.secondary.path==str(technical_pdf)
    assert restored.readers[0].pageNavigator().currentPage()==5
    assert restored.secondary.pageNavigator().currentPage()==3
    restored.close()


def test_layout_changes_keep_reading_anchor(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'reflow.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    w.split(0,0)
    wait(app)
    r.setZoomMode(r.ZoomMode.FitToWidth)
    r.jump(4)
    wait(app)
    r.verticalScrollBar().setValue(r.verticalScrollBar().value()+90)
    wait(app)
    original=r.state()
    w.orientation()
    wait(app)
    changed=r.state()
    assert changed['anchor_page']==original['anchor_page']
    assert abs(changed['y']-original['y'])<3
    w.focus_reader(r)
    w.maximize_pane()
    wait(app)
    assert not w.secondary.isVisible()
    w.maximize_pane()
    wait(app)
    assert w.secondary.isVisible()
    assert r.state()['anchor_page']==original['anchor_page']
    w.close()


def test_password_and_bad_file_handling(app,pdf,tmp_path,monkeypatch):
    from pypdf import PdfWriter
    from PySide6.QtWidgets import QInputDialog
    protected=tmp_path/'protected.pdf'
    writer=PdfWriter(clone_from=pdf)
    writer.encrypt('test-password')
    writer.write(protected)
    w=Window(Store(tmp_path/'encrypted.db'),restore=False)
    errors=[]
    w.error=errors.append
    monkeypatch.setattr(QInputDialog,'getText',lambda *args,**kwargs: ('test-password',True))
    w.show()
    result=w.open_pdf(protected)
    wait(app)
    assert result is not None and result.document().pageCount()==8
    malformed=tmp_path/'broken.pdf'
    malformed.write_text('not a PDF')
    assert w.open_pdf(malformed) is None
    assert w.open_pdf(tmp_path/'missing.pdf') is None
    assert len(errors)==2
    assert len(w.readers)==1
    w.close()
