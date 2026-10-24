"""Facing spreads, tiled equations, scientific text, cancellation and display recovery."""
from threading import Event
import io
import hashlib
import pytest
from PySide6.QtCore import Qt,QPointF,QRect,QModelIndex
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from reportlab.pdfgen.canvas import Canvas
from test_reader import app,pdf,technical_pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.geometry import spreads
from mellow.display import restored_bounds
from mellow.selection import clean_text
from mellow import utilities


def tiles_ready(app,r):
    for _ in range(200):
        r.viewport().update();wait(app,15)
        tasks=r.rotated_pages.tasks()
        if tasks and all(key in r.rotated_pages.cache for key,_,_ in tasks):return
    pytest.fail('Visible tiles did not render')


@pytest.mark.parametrize('layout',['two','two_continuous'])
@pytest.mark.parametrize('cover',[False,True])
@pytest.mark.parametrize('angle',[0,90,180,270])
def test_facing_spreads_render_and_map_both_pages(app,technical_pdf,tmp_path,layout,cover,angle):
    w=Window(Store(tmp_path/'faces.db'),restore=False);w.show()
    r=w.open_pdf(technical_pdf);wait(app)
    w.set_page_layout(layout);w.set_cover(cover);r.rotate_by(angle);r.jump(2);wait(app)
    tiles_ready(app,r)
    expected={p for p in next(row for row in spreads(5,cover) if 2 in row) if p is not None}
    assert r.page_layout_mode==layout and r.custom_rendering
    assert set(p for p,_,_ in r.layout_pages())==(expected if layout=='two' else set(range(5)))
    for page in expected:
        point=QPointF(50,100);hit=r.point_on_page(r.point_in_view(page,point))
        assert hit and hit[0]==page and (hit[1]-point).manhattanLength()<1
    r.select_page_text(2);assert r.copy_selection() and 'Figure 3.8' in QApplication.clipboard().text()
    assert sum(im.sizeInBytes() for im in r.rotated_pages.cache.values())<=32*1024*1024
    w.close()


def test_cover_positions_navigation_and_right_page_focus(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'cover.db'),restore=False);w.show();r=w.open_pdf(pdf);wait(app)
    w.set_page_layout('two');wait(app)
    assert [p for p,_,_ in r.layout_pages()]==[0]
    assert r.layout_pages()[0][1].left()>r.viewport().width()/2
    r.setFocus();QTest.keyClick(r,Qt.Key.Key_Space);wait(app)
    assert [p for p,_,_ in r.layout_pages()]==[1,2]
    QTest.mouseClick(r.viewport(),Qt.MouseButton.LeftButton,pos=r.point_in_view(2,QPointF(200,300)).toPoint())
    assert r.pageNavigator().currentPage()==2 and r.state()['anchor_page']==2
    QTest.keyClick(r,Qt.Key.Key_Space);wait(app)
    assert [p for p,_,_ in r.layout_pages()]==[3,4]
    QTest.keyClick(r,Qt.Key.Key_Space,Qt.KeyboardModifier.ShiftModifier);wait(app)
    assert [p for p,_,_ in r.layout_pages()]==[1,2]
    w.set_cover(False);wait(app)
    assert [p for p,_,_ in r.layout_pages()]==[0,1]
    w.close()


def test_facing_split_session_search_zoom_and_preferences(app,pdf,tmp_path):
    store=Store(tmp_path/'facing-session.db')
    w=Window(store,restore=False);w.show();a=w.open_pdf(pdf);wait(app);w.split(0,0);wait(app)
    b=w.secondary;w.focus_reader(b);w.set_page_layout('two_continuous');w.set_cover(False);wait(app)
    b.jump(4);wait(app)
    point=b.point_in_view(4,QPointF(250,250));old=b.point_on_page(point)
    b.zoom_by(1.2,point);wait(app);hit=b.point_on_page(point)
    assert hit[0]==old[0] and abs(hit[1].y()-old[1].y())<2
    b.search.setSearchString('Mellow')
    # Filtering publishes matches incrementally; wait for the requested row
    # instead of relying on native resultAtIndex's synchronous page search.
    for _ in range(150):
        if b.search.rowCount(QModelIndex())>=7:break
        wait(app,20)
    b.visit_search(6);wait(app)
    assert b.pageNavigator().currentPage()==6 and a.page_layout_mode=='continuous'
    w.close();w=Window(store,restore=True);w.show();wait(app,550)
    assert w.secondary.page_layout_mode=='two_continuous' and not w.secondary.cover_separate
    assert w.secondary.pageNavigator().currentPage()==6 and w.active is w.secondary
    assert w.readers[0].page_layout_mode=='continuous';w.close()


def test_high_zoom_tiles_keep_full_source_density_and_bound_memory(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'tiles.db'),restore=False);w.show();r=w.open_pdf(pdf);wait(app)
    r.rotate_by(90);r.zoom_to(8);r.jump(2,QPointF(100,150));wait(app);tiles_ready(app,r)
    assert any(max(key[2],key[3])>4096 for key,_,_ in r.rotated_pages.tasks())
    assert all(max(image.width(),image.height())<=768 for image in r.rotated_pages.cache.values())
    assert sum(image.sizeInBytes() for image in r.rotated_pages.cache.values())<=32*1024*1024
    assert len(r.rotated_pages.pending)<=2 and not r.viewport().grab().isNull();w.close()


def test_two_column_copy_and_scientific_unicode_keep_source_untouched(app,tmp_path):
    path=tmp_path/'columns.pdf';c=Canvas(str(path),pagesize=(600,800));c.drawString(40,750,'Study heading')
    for index in range(5):
        c.drawString(40,700-index*25,f'Left {index} alpha beta words.')
        c.drawString(330,700-index*25,f'Right {index} gamma delta words.')
    c.drawString(230,40,'Final footer');c.save();before=hashlib.sha256(path.read_bytes()).hexdigest()
    w=Window(Store(tmp_path/'copy.db'),restore=False);w.show();r=w.open_pdf(path);wait(app)
    r.select_page_text();text=r.selected_text()
    assert text.index('Left 4')<text.index('Right 0') and text.endswith('Final footer')
    assert text.count('Left ')==5 and text.count('Right ')==5
    assert clean_text('ﬁeld ﬂow λ − x² + a₁ ∫ f(x) dx')=='field flow λ − x² + a₁ ∫ f(x) dx'
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before;w.close()


def test_cancellable_parser_serializer_and_atomic_copy(tmp_path):
    cancel=Event();stream=utilities.CancelIO(io.BytesIO(b'abc'),cancel)
    assert stream.read(1)==b'a';cancel.set()
    for call in (lambda:stream.read(1),lambda:stream.seek(0),lambda:stream.write(b'x')):
        with pytest.raises(utilities.Cancelled):call()
    original=tmp_path/'large.pdf';original.write_bytes(b'x'*(3*1024*1024))
    output=tmp_path/'destination.pdf';output.write_bytes(b'keep');cancel.clear()
    def progress(done,total):cancel.set()
    with pytest.raises(utilities.Cancelled):utilities.copy_output(original,output,cancel,progress)
    assert output.read_bytes()==b'keep' and not list(tmp_path.glob('.mellow-*.pdf'))


@pytest.mark.parametrize('saved,screens',[
    (dict(rect=[-1800,100,1100,800],screen='removed',available=[-1920,0,1920,1080]),[dict(name='main',available=QRect(0,0,1280,720))]),
    (dict(rect=[2400,400,1600,1000],screen='right',available=[1920,0,2560,1440]),[dict(name='main',available=QRect(0,0,1920,1040)),dict(name='right',available=QRect(1920,0,1280,720))]),
    (dict(rect=[10,10,1150,850],screen='main',available=[0,0,1920,1080]),[dict(name='main',available=QRect(0,0,800,600))]),
])
def test_window_restoration_keeps_bounds_on_available_screens(saved,screens):
    rect=restored_bounds(saved,screens)
    assert any(screen['available'].contains(rect) for screen in screens)


def test_dpi_change_restores_source_coordinates_instead_of_old_pixels(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'dpi.db'),restore=False);w.show();r=w.open_pdf(pdf);wait(app)
    r.zoom_to(2);r.jump(3,QPointF(70,160));wait(app)
    state=r.state();state.update(dpi=state['dpi']*1.5,horizontal=99999,vertical=99999)
    r.jump(1);r.restore(state);wait(app)
    assert r.pageNavigator().currentPage()==3 and abs(r.state()['y']-state['y'])<2;w.close()


def test_merge_keeps_outlines_and_reports_page_progress(pdf,tmp_path):
    from pypdf import PdfReader
    output=tmp_path/'merged.pdf';updates=[]
    utilities.merge([str(pdf),str(pdf)],output,progress=lambda done,total:updates.append((done,total)))
    reader=PdfReader(output)
    assert len(reader.pages)==16 and len(reader.outline)==16
    assert any(done==7 and total==9 for done,total in updates)
    reader.close()


def test_tool_cancel_job_keeps_dialog_for_retry_and_releases_output(app,pdf,tmp_path,monkeypatch):
    from threading import Event
    from mellow.tool_dialog import ToolDialog
    started=Event();original=utilities.extract
    def slow(source,output,ranges,cancel,progress):
        started.set();cancel.wait(.3);utilities.check_cancel(cancel)
        return original(source,output,ranges,cancel,progress)
    monkeypatch.setattr(utilities,'extract',slow)
    d=ToolDialog('extract',paths=[str(pdf)]);d.show();d.timer.stop();d.build_preview()
    assert started.wait(1)
    assert d.cancel_job.isVisible() and d.progress.isVisible()
    d.cancel_job.click()
    for _ in range(100):
        wait(app,20)
        if not d._job:break
    assert d.isVisible() and d.retry.isVisible() and not d.save_button.isEnabled()
    assert not list(__import__('pathlib').Path(d._temp.name).glob('*.pdf'))
    monkeypatch.setattr(utilities,'extract',original);d.retry.click()
    for _ in range(200):
        wait(app,20)
        if d.current_output and not d._job:break
    assert d.current_output and d.save_button.isEnabled()
    root=d._temp.name;d.reject()
    assert not __import__('pathlib').Path(root).exists()
