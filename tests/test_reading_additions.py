"""Session-only recovery, scoped reading keys, search, privacy and rotation."""
import hashlib
from pathlib import Path
import pytest
from reportlab.pdfgen.canvas import Canvas
from PySide6.QtCore import QPointF,Qt,QTimer,QModelIndex
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialog,QLineEdit,QPushButton,QCheckBox
from test_reader import app,pdf,technical_pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.shortcuts import validate


@pytest.mark.parametrize('vertical',[False,True])
def test_space_and_arrow_keys_only_control_focused_pane(app,pdf,tmp_path,vertical):
    w=Window(Store(tmp_path/'keys.db'),restore=False)
    w.show()
    a=w.open_pdf(pdf)
    wait(app)
    w.split(0,0)
    if vertical: w.orientation()
    wait(app)
    b=w.secondary
    a.jump(2);b.jump(5)
    wait(app)
    before=a.state()
    b.setFocus()
    start=b.verticalScrollBar().value()
    QTest.keyClick(b,Qt.Key.Key_Space)
    assert b.verticalScrollBar().value()>start
    QTest.keyClick(b,Qt.Key.Key_Space,Qt.KeyboardModifier.ShiftModifier)
    assert b.verticalScrollBar().value()==start
    QTest.keyClick(b,Qt.Key.Key_Down)
    assert b.verticalScrollBar().value()==start+b.fontMetrics().lineSpacing()
    QTest.keyClick(b,Qt.Key.Key_Up)
    assert b.verticalScrollBar().value()==start
    QTest.keyClick(b,Qt.Key.Key_Right)
    assert b.pageNavigator().currentPage()==6
    QTest.keyClick(b,Qt.Key.Key_Left)
    assert b.pageNavigator().currentPage()==5
    assert a.state()==before
    w.page.lineEdit().setFocus()
    w.page.setCurrentText('1 2')
    w.page.lineEdit().setCursorPosition(1)
    b_state=b.state()
    QTest.keyClick(w.page.lineEdit(),Qt.Key.Key_Space)
    QTest.keyClick(w.page.lineEdit(),Qt.Key.Key_Left)
    assert w.page.currentText()=='1  2'
    assert b.state()==b_state
    # A remapped or disabled reading key follows Settings in every pane.
    w.apply_settings({'shortcuts':{'screen_next':'Ctrl+Shift+Space','line_down':''}})
    b.setFocus()
    previous=b.verticalScrollBar().value()
    QTest.keyClick(b,Qt.Key.Key_Down)
    assert b.verticalScrollBar().value()==previous
    QTest.keyClick(b,Qt.Key.Key_Space,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier)
    assert b.verticalScrollBar().value()>previous
    w.close()


def test_reopen_closed_tab_restores_state_order_and_is_not_persisted(app,pdf,technical_pdf,tmp_path):
    store=Store(tmp_path/'closed.db')
    w=Window(store,restore=False);w.show()
    a=w.open_pdf(pdf);w.open_pdf(technical_pdf)
    w.select(0);wait(app)
    a.jump(2);a.zoom_by(1.4);wait(app)
    a.verticalScrollBar().setValue(a.verticalScrollBar().value()+70)
    old=a.state(include_history=True)
    w.close_tab(0);wait(app)
    assert len(w.readers)==1 and w.reopen_action.isEnabled()
    QTest.keyClick(w,Qt.Key.Key_T,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier)
    wait(app)
    assert [r.path for r in w.readers]==[str(pdf),str(technical_pdf)]
    assert w.tabs.tabText(0)==pdf.name
    assert w.readers[0].state(include_history=True)==old
    assert not w.reopen_action.isEnabled()
    w.readers[0].zoom_by(1.1,smooth=True)
    target_zoom=w.readers[0]._zoom_target
    w.close_tab(0);w.close_tab(0);wait(app)
    assert w._on_home
    w.reopen_closed_tab();wait(app)
    assert w.active.path==str(technical_pdf)
    assert w.closed_tabs[-1]['state']['zoom']==target_zoom
    w.close()
    other=Window(store,restore=False)
    assert other.closed_tabs==[] and not other.reopen_action.isEnabled()
    assert 'closed_tabs' not in store.get('session',{})
    other.close()


def test_missing_closed_tab_is_recoverable_and_keeps_stack(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'missing.db'),restore=False);w.show()
    w.open_pdf(pdf);wait(app);w.close_tab(0)
    moved=pdf.with_name('moved.pdf');pdf.rename(moved)
    errors=[];w.error=errors.append
    w.reopen_closed_tab()
    assert errors and len(w.closed_tabs)==1 and not w.readers
    moved.rename(pdf)
    w.reopen_closed_tab();wait(app)
    assert len(w.readers)==1 and not w.closed_tabs
    w.close()


def test_find_selected_text_opens_prefilled_search_in_focused_split(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'find.db'),restore=False);w.show()
    w.open_pdf(pdf);wait(app);w.split(0,0);wait(app)
    r=w.secondary
    r.text_selection.anchor=(0,0)
    r.text_selection.set_extent(0,6)
    r.selection_updated();r.setFocus()
    assert r.selected_text()=='Mellow'
    QTest.keyClick(r,Qt.Key.Key_F3,Qt.KeyboardModifier.ControlModifier)
    assert QApplication.activeModalWidget() is None
    assert w.inline_search.text.text()=='Mellow' and w.active is r
    assert w.inline_search.isVisible() and r.search.searchString()=='Mellow'
    wait(app)
    assert r.search.rowCount(QModelIndex())>0
    assert w.readers[0].search.searchString()==''
    w.close()


def test_history_pause_and_clear_survive_close_without_removing_favorites(app,pdf,tmp_path):
    store=Store(tmp_path/'privacy.db')
    w=Window(store,restore=False);w.show();r=w.open_pdf(pdf);wait(app)
    store.add('favorite',str(pdf),2,'Keep this')
    assert len(store.history())==1
    w.apply_settings({'history_paused':True})
    old=store.history()
    r.jump(5);w.show_home()
    assert store.history()==old
    def clear_dialog():
        dialog=next(d for d in w.findChildren(QDialog) if d.windowTitle()=='Reading history' and d.isVisible())
        button=next(b for b in dialog.findChildren(QPushButton) if b.text()=='Clear history and pause')
        button.click()
        assert next(iter(dialog.findChildren(QCheckBox))).isChecked()
        dialog.accept()
    QTimer.singleShot(40,clear_dialog)
    w.history_dialog()
    assert store.history()==[] and w.home.listing.count()==0
    w.close()
    assert store.history()==[] and store.get('history_paused')
    assert store.locations('favorite')[0]['title']=='Keep this'
    assert pdf.is_file() and store.get('session')['documents']
    w=Window(store,restore=False);w.show();w.restore_session();wait(app)
    assert w.readers and store.history()==[]
    w.apply_settings({'history_paused':False})
    w.save_session()
    assert len(store.history())==1
    w.close()


def test_preview_find_selection_does_not_take_over_main_toolbar(app,pdf,tmp_path,monkeypatch):
    from mellow.references import Target
    w=Window(Store(tmp_path/'preview-find.db'),restore=False);w.show()
    source=w.open_pdf(pdf);wait(app)
    popup=w.preview(source,Target(0));wait(app)
    r=popup.reader
    r.text_selection.anchor=(0,0);r.text_selection.set_extent(0,6);r.selection_updated()
    calls=[]
    monkeypatch.setattr(w,'search_dialog',lambda **kwargs:calls.append(kwargs))
    r.find_selection_action.trigger()
    assert calls==[dict(initial='Mellow',reader=r)]
    assert w.active is source
    w.close();wait(app,20)


@pytest.fixture
def colored_pdf(tmp_path):
    path=tmp_path/'corners.pdf'
    c=Canvas(str(path),pagesize=(300,500))
    c.setFillColorRGB(1,0,0);c.rect(20,400,70,50,fill=1,stroke=0)
    c.setFillColorRGB(0,0,1);c.rect(20,20,60,80,fill=1,stroke=0)
    c.setFillColorRGB(0,0,0);c.drawString(40,350,'Rotate this selection')
    c.save()
    return path


def rendered(app,reader):
    for _ in range(100):
        reader.viewport().update();wait(app,20)
        tasks=reader.rotated_pages.tasks()
        if tasks and all(key in reader.rotated_pages.cache for key,_,_ in tasks): return
    pytest.fail('Rotated page never rendered')


@pytest.mark.parametrize('angle',[90,180,270])
def test_rotation_renders_real_source_colors_and_text_coordinates(app,colored_pdf,tmp_path,angle):
    original=hashlib.sha256(colored_pdf.read_bytes()).hexdigest()
    w=Window(Store(tmp_path/'rotation.db'),restore=False);w.show()
    r=w.open_pdf(colored_pdf);w.change_theme('Light');wait(app)
    r.rotate_by(angle);rendered(app,r)
    image=r.viewport().grab().toImage()
    for point,color in [(QPointF(50,75),'red'),(QPointF(50,440),'blue')]:
        pos=r.point_in_view(0,point)
        hit=r.point_on_page(pos)
        assert hit[0]==0 and (hit[1]-point).manhattanLength()<1
        pixel=image.pixelColor(round(pos.x()),round(pos.y()))
        if color=='red': assert pixel.red()>220 and pixel.blue()<40
        else: assert pixel.blue()>220 and pixel.red()<40
    r.select_page_text(0)
    assert r.copy_selection() and 'Rotate this selection' in QApplication.clipboard().text()
    # Word lookup uses the same original coordinates after a visual turn.
    text_bounds=r.text_selection.full(0).bounds()[0].boundingRect()
    pos=r.point_in_view(0,QPointF(text_bounds.left()+10,text_bounds.center().y()))
    QTest.mouseDClick(r.viewport(),Qt.MouseButton.LeftButton,pos=pos.toPoint())
    assert 'Rotate' in r.selected_text()
    assert hashlib.sha256(colored_pdf.read_bytes()).hexdigest()==original
    assert r.rotation==angle
    r.rotate_by(-angle);wait(app)
    assert r.rotation==0 and not r.rotated_pages.cache
    image=r.viewport().grab().toImage()
    red=r.point_in_view(0,QPointF(50,75))
    assert image.pixelColor(round(red.x()),round(red.y())).red()>220
    w.close()


def test_rotated_split_zoom_search_history_and_session(app,pdf,tmp_path):
    store=Store(tmp_path/'rotated-session.db')
    w=Window(store,restore=False);w.show();a=w.open_pdf(pdf);wait(app)
    w.split(0,0);wait(app);b=w.secondary
    b.rotate_by(90);rendered(app,b)
    assert a.rotation==0 and b.rotation==90 and a.document() is b.document()
    b.jump(3,QPointF(80,140));wait(app)
    before=b.state()
    b.zoom_by(1.2);wait(app)
    assert b.rotation==90 and b.zoomMode()==b.ZoomMode.Custom
    b.jump(5);wait(app);b.back();wait(app)
    assert b.pageNavigator().currentPage()==3
    b.search.setSearchString('Mellow')
    for _ in range(150):
        if b.search.rowCount()>=7:break
        wait(app,20)
    b.visit_search(6);wait(app)
    assert b.pageNavigator().currentPage()==6
    b.back();wait(app)
    assert b.pageNavigator().currentPage()==3
    saved=b.state()
    w.focus_reader(b);w.close()
    w=Window(store,restore=False);w.show();w.restore_session();wait(app,500)
    assert w.readers[0].rotation==0 and w.secondary.rotation==90
    assert w.secondary.pageNavigator().currentPage()==3
    assert w.secondary.zoomFactor()==saved['zoom']
    assert abs(w.secondary.verticalScrollBar().value()-saved['vertical'])<2
    w.close()


def test_rotated_link_preview_and_scanned_page(app,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'rotated-links.db'),restore=False);w.show()
    r=w.open_pdf(technical_pdf);wait(app)
    r.rotate_by(90);r.jump(0);rendered(app,r)
    point=r.point_in_view(0,QPointF(100,155))
    assert r.internal_link(point).page==2
    before=r.state()
    QTest.mouseClick(r.viewport(),Qt.MouseButton.LeftButton,pos=point.toPoint());wait(app)
    assert len(w.popups)==1 and r.state()==before
    assert w.popups[0].reader.pageNavigator().currentPage()==2
    w.popups[0].close();wait(app,20)
    r.jump(4);rendered(app,r)
    QApplication.clipboard().setText('keep')
    r.select_page_text(4)
    assert not r.copy_selection() and QApplication.clipboard().text()=='keep'
    assert not r.viewport().grab().isNull()
    w.close()


@pytest.mark.parametrize('vertical',[False,True])
def test_rotated_fullscreen_ruler_and_gesture_zoom(app,pdf,tmp_path,vertical):
    from test_interactions import wheel
    w=Window(Store(tmp_path/'rotate-gesture.db'),restore=False);w.show()
    a=w.open_pdf(pdf);wait(app);w.split(0,0)
    if vertical:w.orientation()
    wait(app);b=w.secondary
    b.rotate_by(90);b.jump(3);rendered(app,b)
    old=a.state()
    point=QPointF(b.viewport().width()*.5,b.viewport().height()*.4)
    hit=b.point_on_page(point)
    assert hit is not None
    wheel(b,point);wait(app,100)
    after=b.point_on_page(point)
    assert hit[0]==after[0] and abs(hit[1].x()-after[1].x())<3
    assert a.state()==old
    b.ruler=True
    w.fullscreen();wait(app,100)
    size=b.viewport().size();state=b.state()
    w.show_chrome();wait(app,40);w.toggle_chrome();wait(app,40)
    assert b.viewport().size()==size and b.state()==state
    assert not w.grab().isNull()
    w.fullscreen();wait(app,100);w.close()


def test_show_in_folder_uses_argument_list_and_reports_missing_file(app,pdf,monkeypatch):
    from mellow import platform
    commands=[]
    monkeypatch.setattr(platform.sys,'platform','win32')
    monkeypatch.setattr(platform,'explorer_executable',lambda:'C:/Windows/explorer.exe')
    monkeypatch.setattr(platform.subprocess,'Popen',lambda args:commands.append(args))
    assert platform.show_in_folder(pdf)
    assert commands==[['C:/Windows/explorer.exe','/select,',str(pdf)]]
    with pytest.raises(FileNotFoundError): platform.show_in_folder(pdf.with_name('missing.pdf'))


def test_close_during_rotated_render_releases_document_for_reopen(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'close-render.db'),restore=False);w.show()
    r=w.open_pdf(pdf);wait(app)
    r.rotate_by(90)
    r.viewport().grab()
    w.close_tab(0)
    wait(app,100)
    w.reopen_closed_tab();wait(app)
    r=w.active
    assert r.rotation==90
    rendered(app,r)
    assert sum(image.sizeInBytes() for image in r.rotated_pages.cache.values())<=32*1024*1024
    assert len(r.rotated_pages.pending)<=2
    r.select_page_text(0)
    assert r.copy_selection()
    w.close()
