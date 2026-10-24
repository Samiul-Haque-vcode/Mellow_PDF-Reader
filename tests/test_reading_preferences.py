"""Reversible source-coordinate crops and local book numbering on real PDFs."""
import hashlib,sqlite3
from pathlib import Path
import pytest
from reportlab.pdfgen.canvas import Canvas
from PySide6.QtCore import QPointF,QModelIndex,Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from test_reader import app,pdf,technical_pdf,wait
from test_remaining_queue import tiles_ready
from mellow.app import Window
from mellow.storage import Store
from mellow.geometry import source_rect,page_transform
from mellow.page_preferences import MarginsDialog,NumberingDialog
from mellow.reading_options import page_index
from mellow.locations import LocationsPanel
from mellow.document_info import document_fields


@pytest.fixture
def crop_pdf(tmp_path):
    path=tmp_path/'crop.pdf';c=Canvas(str(path),pagesize=(600,800))
    for i in range(3):
        c.bookmarkPage(f'p{i}',fit='XYZ',left=0,top=800,zoom=0)
        c.addOutlineEntry(f'Chapter {i+1}',f'p{i}',0)
        c.setFillColorRGB(1,0,0);c.rect(80,610,100,90,fill=1,stroke=0)
        c.setFillColorRGB(0,0,1);c.rect(370,180,100,90,fill=1,stroke=0)
        c.setFillColorRGB(0,0,0);c.drawString(100,480,f'Reading chapter {i+1} alpha beta')
        c.linkRect('Next chapter','p2',(100,450,250,475),thickness=0)
        c.showPage()
    c.save();return path


@pytest.mark.parametrize('angle',[0,90,180,270])
@pytest.mark.parametrize('layout',['continuous','single','two','two_continuous'])
def test_crop_renders_correct_source_regions_at_every_rotation_and_layout(app,crop_pdf,tmp_path,angle,layout):
    w=Window(Store(tmp_path/'crop.db'),restore=False);w.show();r=w.open_pdf(crop_pdf)
    w.change_theme('Light');wait(app,80)
    w.set_page_layout(layout);r.set_rotation(angle);w.apply_margins((10,8,12,14))
    r.setZoomMode(r.ZoomMode.FitInView);r.jump(0);wait(app,100);tiles_ready(app,r)
    assert r.custom_rendering and source_rect(r,0).width()==468
    image=r.viewport().grab().toImage()
    for point,color in [(QPointF(120,140),'red'),(QPointF(410,570),'blue')]:
        pos=r.point_in_view(0,point);hit=r.point_on_page(pos)
        assert hit and hit[0]==0 and (hit[1]-point).manhattanLength()<.1
        pixel=image.pixelColor(pos.toPoint())
        if color=='red':assert pixel.red()>220 and pixel.blue()<40
        else:assert pixel.blue()>220 and pixel.red()<40
    crop=source_rect(r,0);mapped=page_transform(r,0).mapRect(crop)
    assert abs(mapped.x())<.01 and abs(mapped.y())<.01
    w.close()


def test_crop_links_search_selection_zoom_and_reset_leave_source_unchanged(app,crop_pdf,tmp_path):
    original=hashlib.sha256(crop_pdf.read_bytes()).hexdigest()
    w=Window(Store(tmp_path/'reading.db'),restore=False);w.show();r=w.open_pdf(crop_pdf);wait(app,80)
    w.apply_margins((8,6,9,10));r.setZoomMode(r.ZoomMode.FitToWidth);r.jump(0);wait(app,100)
    point=r.point_in_view(0,QPointF(120,338));target=r.internal_link(point)
    assert target and target.page==2
    before=r.state();popup=w.preview(r,target);wait(app,150)
    assert r.state()==before and popup.reader.crop==(0,0,0,0)
    popup.close();r.jump(2);r.back();wait(app,100)
    assert r.pageNavigator().currentPage()==0 and r.crop==(8,6,9,10)
    r.search.setSearchString('alpha')
    for _ in range(60):
        if r.search.rowCount(QModelIndex())==3:break
        wait(app,20)
    r.visit_search(1);wait(app,100)
    assert r.pageNavigator().currentPage()==1 and r.currentSearchResultIndex()==1
    bounds=r.text_selection.full(1).bounds()[0].boundingRect()
    QTest.mouseDClick(r.viewport(),Qt.MouseButton.LeftButton,pos=r.point_in_view(1,QPointF(bounds.left()+12,bounds.center().y())).toPoint())
    assert r.copy_selection() and 'Reading' in QApplication.clipboard().text()
    r.clear_selection()
    point=QPointF(r.viewport().rect().center());hit=r.point_on_page(point)
    assert hit
    r.zoom_by(1.2,point);wait(app,100);after=r.point_on_page(point)
    assert after[0]==hit[0] and (after[1]-hit[1]).manhattanLength()<2
    w.apply_margins((0,0,0,0));wait(app,80)
    assert not r.custom_rendering and not r.rotated_pages.cache
    assert r.currentSearchResultIndex()==1 and not w.reset_margins_action.isEnabled()
    assert hashlib.sha256(crop_pdf.read_bytes()).hexdigest()==original
    w.close()


def test_crop_never_restores_a_hidden_target_into_the_preceding_page(app,crop_pdf,tmp_path):
    w=Window(Store(tmp_path/'hidden-target.db'),restore=False);w.show();r=w.open_pdf(crop_pdf);wait(app,60)
    r.jump(1);wait(app,60);assert r.state()['anchor_page']==1
    w.apply_margins((10,15,10,15));wait(app,80)
    assert r.state()['anchor_page']==1
    r.jump(2,QPointF(100,10));wait(app,60)
    assert r.state()['anchor_page']==2
    w.close()


def test_crop_is_independent_in_split_and_survives_home_session_and_relocation(app,pdf,tmp_path):
    store=Store(tmp_path/'session.db');w=Window(store,restore=False);w.show();a=w.open_pdf(pdf);wait(app,70)
    w.split(0,0);wait(app,70);b=w.secondary;w.focus_reader(b)
    w.apply_margins((12,5,8,9));b.jump(5);a.jump(2);wait(app,120)
    assert a.crop==(0,0,0,0) and b.crop==(12,5,8,9)
    before=[a.state(),b.state()];w.show_home();wait(app,70);w.resume_reading();wait(app,100)
    assert [a.state(),b.state()]==before
    sources=list(w.docs);w.close()
    assert all(not doc.source_file.isOpen() for doc in sources)
    saved_session=store.get('session');w.close();assert store.get('session')==saved_session
    w=Window(store,restore=True);w.show();wait(app,300)
    assert w.readers[0].crop==(0,0,0,0) and w.secondary.crop==(12,5,8,9)
    assert w.secondary.pageNavigator().currentPage()==5
    w.exit_split();w.close_tab(0)
    # Home can briefly open the just-closed PDF to render its Recent thumbnail.
    for _ in range(100):
        wait(app,20)
        if not w.home.thumbnail.timer.isActive() and not w.home.thumbnail.source.isOpen():break
    assert not w.home.thumbnail.source.isOpen()
    store.set('history_paused',True)
    moved=tmp_path/'moved.pdf';pdf.rename(moved);store.relocate(str(pdf),str(moved))
    r=w.open_pdf(moved);wait(app,100)
    assert r.crop==(12,5,8,9)
    w.apply_margins((0,0,0,0));w.close_tab(0);w.open_recent(store.recent(moved));wait(app,100)
    assert w.active.crop==(0,0,0,0)
    w.close()


def test_book_numbering_changes_labels_but_not_destinations_and_resets_native(app,technical_pdf,tmp_path):
    store=Store(tmp_path/'numbers.db');w=Window(store,restore=False);w.show();r=w.open_pdf(technical_pdf);wait(app,80)
    original=hashlib.sha256(technical_pdf.read_bytes()).hexdigest()
    store.add('favorite',technical_pdf,3,'The theorem');store.add('bookmark',technical_pdf,3,'Study here')
    w.split(0,0);wait(app,80);w.focus_reader(w.secondary);w.secondary.jump(3);wait(app,80)
    w.remember_reader(w.secondary);w.apply_numbering(dict(pdf=2,book=10));wait(app,80)
    assert r.page_label(0)=='i' and r.page_label(2)=='10' and w.page.currentText()=='11'
    assert w.page_total.text()=='PDF 4/5'
    assert r.page_label(3)==w.secondary.page_label(3)=='11'
    assert dict(document_fields(w.secondary))['Current page']=='11 (PDF page 4)'
    assert store.locations('favorite')[0]['label']=='11'
    assert store.locations('bookmark')[0]['label']=='11'
    assert store.recent(technical_pdf)['state']['label']=='11'
    w.navigate_page_text('10');wait(app,80);assert w.secondary.pageNavigator().currentPage()==2
    w.navigate_page_text('#4');wait(app,80);assert w.secondary.pageNavigator().currentPage()==3
    w.navigate_page_text('i');wait(app,80);assert w.secondary.pageNavigator().currentPage()==0
    panel=LocationsPanel(w,'bookmark');panel.show();wait(app,50);panel.search.setText('11')
    assert not panel.listing.item(0).isHidden()
    panel.reject();w.apply_numbering(None);wait(app,80)
    assert r.page_label(0)=='i' and r.page_label(2)=='1'
    assert store.locations('favorite')[0]['label']=='2'
    assert hashlib.sha256(technical_pdf.read_bytes()).hexdigest()==original
    w.close()


def test_numeric_front_matter_has_unambiguous_physical_labels_and_persists(app,pdf,tmp_path):
    store=Store(tmp_path/'labels.db');w=Window(store,restore=False);w.show();r=w.open_pdf(pdf);wait(app,60)
    w.apply_numbering(dict(pdf=3,book=1))
    assert r.page_label(0)=='#1' and r.page_label(3)=='1'
    assert page_index(r.document(),'1')==3 and page_index(r.document(),'#1')==0
    w.navigate_page_text('3');wait(app,60);assert r.pageNavigator().currentPage()==5
    sources=list(w.docs);w.close();assert all(not doc.source_file.isOpen() for doc in sources)
    w=Window(store,restore=True);w.show();wait(app,200)
    assert w.active.page_label(3)=='1' and w.active.pageNavigator().currentPage()==5
    w.close_tab(0);moved=tmp_path/'relocated.pdf';pdf.rename(moved);store.relocate(str(pdf),str(moved))
    r=w.open_pdf(moved);wait(app,80);assert r.page_label(3)=='1'
    w.close()


def test_preference_dialog_cancel_reset_and_source_preview(app,crop_pdf,tmp_path):
    w=Window(Store(tmp_path/'dialog.db'),restore=False);w.show();r=w.open_pdf(crop_pdf);wait(app,60)
    d=MarginsDialog(r,w);d.show();d.edits[0].setValue(15);wait(app,200)
    assert d.preview.image is not None and d.preview.margins[0]==15
    d.reject();assert r.crop==(0,0,0,0) and d.preview.request is None
    d=MarginsDialog(r,w);d.edits[0].setValue(15);d.reset_button.click();assert d.margins()==(0,0,0,0);d.reject()
    d=NumberingDialog(r,w);d.pdf_page.setValue(2);d.book_page.setValue(5);d.reject()
    assert r.page_label(1)=='2'
    d=NumberingDialog(r,w);d.pdf_page.setValue(2);d.book_page.setValue(5)
    assert d.mapping()==dict(pdf=1,book=5)
    d.reset_button.click();assert d.mapping() is None;d.reject();w.close()


def test_document_option_migration_and_invalid_values(tmp_path):
    path=tmp_path/'legacy.db';db=sqlite3.connect(path)
    db.execute('CREATE TABLE document_options(path TEXT PRIMARY KEY,page_layout TEXT NOT NULL)');db.commit();db.close()
    store=Store(path);pdf=tmp_path/'book.pdf'
    store.set_document_layout(pdf,'two');store.set_document_cover(pdf,False)
    store.set_document_option(pdf,'crop',[2,3,4,5]);store.set_document_option(pdf,'numbering',dict(pdf=10,book=1))
    assert store.document_layout(pdf)=='two' and not store.document_cover(pdf)
    assert store.document_option(pdf,'crop')==(2,3,4,5)
    for invalid in ([0,0,0,float('nan')],[0,0,0,41],[True,0,0,0]):
        with pytest.raises(ValueError):store.set_document_option(pdf,'crop',invalid)
    with pytest.raises(ValueError):store.set_document_option(pdf,'numbering',dict(pdf=-1,book=1))
    assert store.document_option(pdf,'numbering')==dict(pdf=10,book=1)


def test_crop_high_zoom_mixed_dimensions_fullscreen_and_marker(app,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'large.db'),restore=False);w.show();r=w.open_pdf(technical_pdf);wait(app,70)
    w.apply_margins((4,3,5,6));r.rotate_by(90);r.zoom_to(8);r.jump(2,QPointF(100,180));wait(app,100);tiles_ready(app,r)
    assert len(r.rotated_pages.pending)<=2
    assert sum(im.sizeInBytes() for im in r.rotated_pages.cache.values())<=32*1024*1024
    assert all(max(im.width(),im.height())<=768 for im in r.rotated_pages.cache.values())
    r.zoom_to(1.5);r.jump(2,QPointF(100,180));wait(app,80);w.save_marker()
    r.jump(3);w.return_marker();wait(app,80)
    assert r.pageNavigator().currentPage()==2 and r.crop==(4,3,5,6)
    before=r.state();w.fullscreen();wait(app,200);w.fullscreen();wait(app,200)
    after=r.state()
    assert after['crop']==before['crop'] and after['rotation']==before['rotation']
    assert after['anchor_page']==before['anchor_page'] and abs(after['y']-before['y'])<2
    w.close()
