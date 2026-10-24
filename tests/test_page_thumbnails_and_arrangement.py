"""Real page destinations, output order/rotation and disposable async grids."""
import hashlib
from pathlib import Path
from threading import Event
import pytest
from pypdf import PdfReader,PdfWriter
from PySide6.QtCore import Qt,QPointF,QTimer
from PySide6.QtWidgets import QDialog
from PySide6.QtTest import QTest
from test_reader import app,pdf,technical_pdf,wait
from test_settings_and_tools import settle
from mellow.app import Window
from mellow.storage import Store
from mellow.pages import PagesPanel,ArrangePagesDialog
from mellow.page_grid import PageGrid,CACHE_BYTES
from mellow.tool_dialog import ToolDialog
from mellow import utilities


def thumbnails_ready(app,grid):
    for _ in range(100):
        wait(app,15)
        assert len(grid.pending)<=2
        assert sum(image.sizeInBytes() for image in grid.cache.values())<=CACHE_BYTES
        if grid.cache and not grid.pending and not grid.timer.isActive():return
    pytest.fail('Visible page thumbnails did not settle')


def test_arrange_real_content_dimensions_labels_links_and_outlines(technical_pdf,tmp_path):
    from pypdf.generic import NameObject,TextStringObject,DictionaryObject
    source=tmp_path/'named-source.pdf'
    writer=PdfWriter(clone_from=technical_pdf)
    writer.add_named_destination('figure',2)
    # A second internal link exercises named GoTo actions as well as /Dest.
    annotation=writer.pages[0]['/Annots'][0].get_object()
    named=DictionaryObject({NameObject('/Type'):NameObject('/Annot'),NameObject('/Subtype'):NameObject('/Link'),
        NameObject('/Rect'):annotation['/Rect'],NameObject('/A'):DictionaryObject({
            NameObject('/S'):NameObject('/GoTo'),NameObject('/D'):TextStringObject('figure')})})
    writer.add_annotation(0,named)
    writer.write(source);writer.close()
    original=hashlib.sha256(source.read_bytes()).hexdigest()
    output=tmp_path/'arranged.pdf'
    order=[2,0,4,1,3]
    utilities.arrange(source,output,[(page,90 if page==0 else 0) for page in order])
    with PdfReader(output) as result,PdfReader(source) as before:
        assert len(result.pages)==5
        assert result.page_labels==[before.page_labels[page] for page in order]
        assert 'Figure 3.8: A mathematical diagram' in result.pages[0].extract_text()
        for index,page in enumerate(order):
            assert result.pages[index].mediabox==before.pages[page].mediabox
        assert result.pages[1].rotation==90
        assert [result.get_destination_page_number(item) for item in result.outline]==[1,3,0,4,2]
        link=result.pages[1]['/Annots'][0].get_object()
        target=link.get('/Dest') or link['/A']['/D']
        assert result.get_page_number(target[0].get_object())==0
        assert result.get_destination_page_number(result.named_destinations['figure'])==0
        assert result.pages[1]['/Annots'][1].get_object()['/A']['/D']=='figure'
        assert not result.pages[0].rotation
    assert hashlib.sha256(source.read_bytes()).hexdigest()==original


@pytest.mark.parametrize('entries',[
    [(0,0)]*8,[(i,0) for i in range(7)],[(i,45) for i in range(8)],
    [(i,True) for i in range(8)],[(str(i),0) for i in range(8)],[(i,) for i in range(8)]])
def test_invalid_arrangement_preserves_existing_output(pdf,tmp_path,entries):
    output=tmp_path/'existing.pdf'
    output.write_bytes(b'previous destination')
    with pytest.raises(ValueError):utilities.arrange(pdf,output,entries)
    assert output.read_bytes()==b'previous destination'
    assert not list(tmp_path.glob('.mellow-*'))


def test_arrange_cancellation_and_source_alias_protection(pdf,tmp_path):
    output=tmp_path/'destination.pdf'
    output.write_bytes(b'keep me')
    cancel=Event()
    def progress(done,total):
        if done>=2:cancel.set()
    entries=[(page,0) for page in reversed(range(8))]
    with pytest.raises(utilities.Cancelled):utilities.arrange(pdf,output,entries,cancel,progress)
    assert output.read_bytes()==b'keep me'
    assert not list(tmp_path.glob('.mellow-*'))
    alias=tmp_path/'alias.pdf'
    alias.hardlink_to(pdf)
    for destination in (pdf,alias):
        with pytest.raises(ValueError):utilities.arrange(pdf,destination,entries)


def test_existing_rotation_is_added_not_overwritten(technical_pdf,tmp_path):
    source=tmp_path/'rotated-source.pdf'
    writer=PdfWriter(clone_from=technical_pdf)
    writer.pages[0].rotate(90)
    writer.write(source);writer.close()
    output=tmp_path/'again.pdf'
    utilities.arrange(source,output,[(0,270),(1,90),(2,0),(3,180),(4,0)])
    with PdfReader(output) as result:
        assert [page.rotation for page in result.pages]==[0,90,0,180,0]


def test_page_grid_drag_multiple_move_rotate_and_reset(app,technical_pdf):
    d=ArrangePagesDialog(technical_pdf)
    d.show()
    thumbnails_ready(app,d.grid)
    d.grid.select_rows([0,2])
    mime=d.grid.model().mimeData(d.grid.selectedIndexes())
    target=d.grid.visualRect(d.grid.pages.index(4,0)).center()
    class Drop:
        accepted=False
        def source(self):return d.grid
        def mimeData(self):return mime
        def position(self):return QPointF(target)
        def setDropAction(self,action):assert action==Qt.DropAction.MoveAction
        def accept(self):self.accepted=True
        def ignore(self):pytest.fail('Internal page drop was rejected')
    event=Drop()
    d.grid.dropEvent(event)
    assert event.accepted
    assert d.entries()==[(1,0),(3,0),(0,0),(2,0),(4,0)]
    assert d.grid.selected_rows()==[2,3]
    d.rotate(-90)
    assert d.entries()[2:4]==[(0,270),(2,270)]
    d.grid.move_selected(-1)
    assert d.entries()==[(1,0),(0,270),(2,270),(3,0),(4,0)]
    d.grid.move_selected(1)
    assert d.entries()==[(1,0),(3,0),(0,270),(2,270),(4,0)]
    d.reset()
    assert d.entries()==[(page,0) for page in range(5)]
    d.reject()
    assert d.grid.released and not d.source.isOpen()
    assert not d.grid.cache and not d.grid.pending
    d.deleteLater();wait(app,10)


def test_arrangement_dialog_cancel_releases_file_and_rotated_thumbnail(app,technical_pdf,tmp_path):
    copy=tmp_path/'arranger.pdf'
    copy.write_bytes(Path(technical_pdf).read_bytes())
    d=ArrangePagesDialog(copy,entries=[(0,90),(1,0),(2,0),(3,0),(4,0)])
    d.show()
    thumbnails_ready(app,d.grid)
    assert d.grid.cache[(0,90)].width()>d.grid.cache[(0,90)].height()
    QTest.keyClick(d.grid,Qt.Key.Key_Escape)
    assert d.result()==QDialog.DialogCode.Rejected and not d.source.isOpen()
    moved=copy.with_suffix('.moved.pdf')
    copy.rename(moved)  # Also checked under Windows file locking.
    assert moved.exists()
    d.deleteLater();wait(app,10)


@pytest.mark.parametrize('mode',['extract','merge','images'])
def test_tool_arrangement_actual_preview_exact_save_and_source_reset(app,pdf,technical_pdf,tmp_path,mode):
    if mode=='images':
        from PIL import Image
        paths=[]
        for name,color in [('red','red'),('blue','blue')]:
            path=tmp_path/(name+'.png');Image.new('RGB',(80,60),color).save(path);paths.append(str(path))
    else:paths=[str(pdf)] if mode=='extract' else [str(pdf),str(technical_pdf)]
    hashes=[hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in paths]
    d=ToolDialog(mode,paths=paths)
    if mode=='extract':d.ranges.setText('1-4')
    d.show();settle(app,d)
    count=d.document.pageCount()
    base=d._base_output
    plan=[(page,90 if page==count-1 else 0) for page in reversed(range(count))]
    assert d.apply_arrangement(plan)
    assert not d.save_button.isEnabled() and not d.arrange_button.isEnabled()
    settle(app,d)
    assert d._base_output==base and d.current_output!=base
    with PdfReader(d.current_output) as output,PdfReader(base) as before:
        assert output.pages[0].rotation==90
        assert output.pages[0].extract_text()==before.pages[-1].extract_text()
    if mode!='merge':assert d.document.pagePointSize(0).width()>d.document.pagePointSize(0).height()
    # Re-editing is relative to the stable initial output, not cumulative.
    assert d.apply_arrangement([(page,0) for page in range(count)])
    settle(app,d)
    with PdfReader(d.current_output) as output:assert output.pages[0].rotation==0
    assert len(list(Path(d._temp.name).glob('preview-*.pdf')))==2
    # Any source/range/size change explicitly resets the arrangement.
    d.schedule_preview();settle(app,d)
    assert d._arrangement is None and d._base_output==d.current_output
    assert len(list(Path(d._temp.name).glob('preview-*.pdf')))==1
    assert d.apply_arrangement(plan);settle(app,d)
    expected=Path(d.current_output).read_bytes()
    destination=tmp_path/(mode+'-arranged.pdf')
    alias=tmp_path/'source-alias.pdf'
    alias.hardlink_to(paths[0])
    assert not d.save_to(alias)
    assert d.save_to(destination);settle(app,d)
    assert destination.read_bytes()==expected and d._disposed
    assert [hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in paths]==hashes


def test_tool_arrange_button_apply_and_cancel(app,pdf,monkeypatch):
    d=ToolDialog('extract',paths=[str(pdf)]);d.ranges.setText('1-3');d.show();settle(app,d)
    original=d.current_output
    def cancel():
        child=d.findChild(ArrangePagesDialog)
        child.grid.select_rows([0]);child.rotate(90);child.reject()
    QTimer.singleShot(50,cancel);d.arrange_pages()
    assert d.current_output==original and d._arrangement is None
    def apply():
        child=[child for child in d.findChildren(ArrangePagesDialog) if child.isVisible()][0]
        child.grid.select_rows([0]);child.rotate(90);child.accept()
    QTimer.singleShot(50,apply);d.arrange_pages();settle(app,d)
    with PdfReader(d.current_output) as output:assert output.pages[0].rotation==90
    d.reject()


def test_arranged_preview_cancellation_retry_and_stale_work(app,pdf,monkeypatch):
    d=ToolDialog('extract',paths=[str(pdf)]);d.ranges.setText('1-4');d.show();settle(app,d)
    original=utilities.arrange
    started=Event()
    def slow(source,output,entries,cancel,progress):
        started.set();cancel.wait(.1);utilities.check_cancel(cancel)
        original(source,output,entries,cancel,progress)
    monkeypatch.setattr(utilities,'arrange',slow)
    d.apply_arrangement([(page,90) for page in range(4)]);d.timer.stop();d.build_preview()
    assert started.wait(1)
    d.cancel_current();settle(app,d)
    assert not d.current_output and d.retry.isVisible() and Path(d._base_output).exists()
    d.retry.click();settle(app,d)
    assert d.current_output
    with PdfReader(d.current_output) as output:assert output.pages[0].rotation==90
    started.clear()
    d.apply_arrangement([(page,180) for page in range(4)]);d.timer.stop();d.build_preview()
    assert started.wait(1)
    d.ranges.setText('5-6');settle(app,d)
    assert d._arrangement is None and d.document.pageCount()==2
    assert 'chapter 5' in d.document.getAllText(0).text()
    d.reject()


def test_navigator_keyboard_labels_escape_jump_and_history(app,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'navigator.db'),restore=False);w.show()
    r=w.open_pdf(technical_pdf);r.jump(2);wait(app)
    w.apply_numbering(dict(pdf=2,book=20))
    before=r.state(include_history=True)
    panel=PagesPanel(r,w);panel.show();wait(app,50)
    assert panel.grid.currentIndex().row()==2
    assert panel.grid.pages.index(0,0).data()=='i'
    assert panel.grid.pages.index(2,0).data()=='20 · Current'
    QTest.keyClick(panel.grid,Qt.Key.Key_Right)
    QTest.keyClick(panel.grid,Qt.Key.Key_Escape)
    assert r.state(include_history=True)==before and panel.grid.released
    panel=PagesPanel(r,w);panel.show();wait(app,50)
    QTest.keyClick(panel.grid,Qt.Key.Key_Right)
    QTest.keyClick(panel.grid,Qt.Key.Key_Return);wait(app)
    assert panel.result()==QDialog.DialogCode.Accepted and not panel.isVisible()
    assert r.pageNavigator().currentPage()==3
    r.back();wait(app)
    assert r.pageNavigator().currentPage()==2
    w.close()


@pytest.mark.parametrize('same',[True,False])
def test_navigator_split_target_click_and_document_close(app,pdf,technical_pdf,tmp_path,same):
    w=Window(Store(tmp_path/'split-navigator.db'),restore=False);w.show()
    first=w.open_pdf(pdf)
    if not same:w.open_pdf(technical_pdf)
    w.split(0,0 if same else 1);wait(app)
    second=w.secondary;w.focus_reader(second)
    before=first.state(include_history=True)
    panel=PagesPanel(second,w);panel.show();wait(app,50)
    index=panel.grid.pages.index(3,0)
    QTest.mouseClick(panel.grid.viewport(),Qt.MouseButton.LeftButton,pos=panel.grid.visualRect(index).center())
    wait(app)
    assert second.pageNavigator().currentPage()==3 and w.active is second
    assert first.state(include_history=True)==before
    panel=PagesPanel(second,w);panel.show();wait(app,15)
    w.close_tab(0)
    assert not panel.isVisible() and panel.grid.released and not panel.grid.cache
    w.close()


def test_large_mixed_grid_visible_work_bounded_cache_and_close(app,tmp_path):
    source=tmp_path/'large-pages.pdf'
    writer=PdfWriter()
    for page in range(600):writer.add_blank_page(width=400 if page%2 else 800,height=1000 if page%2 else 500)
    writer.write(source);writer.close()
    from PySide6.QtPdf import QPdfDocument
    document=QPdfDocument();document.load(str(source))
    grid=PageGrid(document);grid.resize(500,440);grid.show()
    thumbnails_ready(app,grid)
    assert 0<len(grid.cache)<20
    for page in range(40,600,40):
        grid.scrollTo(grid.pages.index(page,0),grid.ScrollHint.PositionAtCenter)
        thumbnails_ready(app,grid)
        assert len(grid.pending)<=2
        assert sum(image.sizeInBytes() for image in grid.cache.values())<=CACHE_BYTES
    grid.scrollTo(grid.pages.index(599,0));wait(app,100)
    assert any(page>590 for page,angle in grid.cache)
    grid.close();wait(app,30)
    assert grid.released and not grid.cache and not grid.pending
    assert grid.renderer is None
    document.close()
    grid.deleteLater();document.deleteLater();wait(app,10)


@pytest.mark.parametrize('action',['home','switch','close'])
def test_programmatic_navigation_closes_thumbnail_panel(app,pdf,technical_pdf,tmp_path,action):
    w=Window(Store(tmp_path/(action+'.db')),restore=False);w.show()
    r=w.open_pdf(pdf);w.open_pdf(technical_pdf);w.select(0);wait(app)
    panel=PagesPanel(r,w);panel.show();wait(app,30)
    if action=='home':w.show_home()
    elif action=='switch':w.select(1)
    else:w.close()
    assert not panel.isVisible() and panel.grid.released
    w.close()


def test_navigator_scrollbar_access_and_configurable_shortcut(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'pages-action.db'),restore=False);w.show()
    assert not w.pages_action.isEnabled()
    r=w.open_pdf(pdf);wait(app)
    w.apply_settings({'shortcuts':{'page_thumbnails':'Ctrl+Shift+P'}})
    assert w.pages_action.shortcut().toString()=='Ctrl+Shift+P'
    assert w.pages_action not in w.reading_menu.actions()
    shown=[]
    def close_panel():
        panels=[panel for panel in w.findChildren(PagesPanel) if panel.isVisible()]
        shown.extend(panels)
        for panel in panels:panel.reject()
    QTimer.singleShot(100,close_panel)
    w.pages_action.trigger()
    assert len(shown)==1 and shown[0].grid.released
    w.close()


def test_tool_parent_close_with_arrangement_workspace(app,pdf,tmp_path):
    d=ToolDialog('extract',paths=[str(pdf)]);d.ranges.setText('1-3');d.show();settle(app,d)
    arranger=ArrangePagesDialog(d._base_output,d);arranger.show();wait(app,20)
    root=Path(d._temp.name)
    d.reject()
    assert not arranger.isVisible() and not arranger.source.isOpen()
    assert arranger.grid.released and not root.exists()


def test_rapid_close_while_thumbnails_pending_releases_source(app,technical_pdf,tmp_path):
    # Detaching a document alone leaves the renderer worker alive. Dispose that
    # worker before closing its source, including on immediate/OS-level close.
    source=tmp_path/'rapid-close.pdf'
    source.write_bytes(Path(technical_pdf).read_bytes())
    for cycle in range(20):
        d=ArrangePagesDialog(source)
        d.show()
        app.processEvents()
        d.grid.pump()
        d.reject()
        assert d.grid.renderer is None and not d.grid.pending and not d.source.isOpen()
        moved=source.with_suffix('.moved.pdf')
        source.rename(moved);moved.rename(source)
        d.deleteLater()
        wait(app,1)
