"""Native continuous/single layouts: real PDF coordinates, gestures and sessions."""
import hashlib
from pathlib import Path
import pytest
from PySide6.QtCore import Qt,QPoint,QPointF,QModelIndex
from PySide6.QtGui import QWheelEvent,QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_reader import app,pdf,technical_pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.theme import COLORS
from mellow.geometry import page_transform


def scroll(reader,delta=-120,pixels=0,phase=Qt.ScrollPhase.NoScrollPhase,ctrl=False):
    point=QPointF(reader.viewport().rect().center())
    event=QWheelEvent(point,QPointF(reader.viewport().mapToGlobal(point.toPoint())),
        QPoint(0,pixels),QPoint(0,delta),Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier,phase,False)
    QApplication.sendEvent(reader.viewport(),event)


@pytest.mark.parametrize('rotation',[0,90,180,270])
@pytest.mark.parametrize('mode',['custom','width','page'])
def test_layout_switch_retains_source_anchor_zoom_history_and_text(app,technical_pdf,tmp_path,rotation,mode):
    w=Window(Store(tmp_path/'switch.db'),restore=False);w.show()
    r=w.open_pdf(technical_pdf);wait(app)
    if rotation:r.rotate_by(rotation);wait(app)
    if mode=='custom':r.zoom_to(1.7)
    elif mode=='width':r.setZoomMode(r.ZoomMode.FitToWidth)
    r.jump(2,QPointF(65,120));wait(app)
    old=r.state(include_history=True)
    original=hashlib.sha256(technical_pdf.read_bytes()).hexdigest()
    w.set_page_layout('single');wait(app)
    assert r.page_layout_mode=='single'
    assert [p for p,_,_ in r.layout_pages()]==[old['anchor_page']]
    assert r.pageNavigator().currentPage()==old['anchor_page']
    assert r.zoomMode().value==old['mode'] and r.zoomFactor()==old['zoom']
    assert r._past==old['past'] and r._future==old['future']
    # Native margins and a newly bounded page can clamp source coordinates.
    _,rect,scale=r.layout_pages()[0]
    source=page_transform(r,old['anchor_page']).map(QPointF(old['x'],old['y']))
    wanted=round(rect.y()+source.y()*scale)
    bar=r.verticalScrollBar()
    assert abs(bar.value()-max(bar.minimum(),min(bar.maximum(),wanted)))<=1
    r.select_page_text()
    assert r.copy_selection() and 'Figure 3.8' in QApplication.clipboard().text()
    r.clear_selection()
    point=QPointF(100,150)
    mapped=r.point_in_view(2,point)
    hit=r.point_on_page(mapped)
    assert hit and hit[0]==2 and (hit[1]-point).manhattanLength()<2
    w.set_page_layout('continuous');wait(app)
    assert len(r.layout_pages())==5 and r.page_layout_mode=='continuous'
    assert r.zoomMode().value==old['mode'] and r.zoomFactor()==old['zoom']
    assert hashlib.sha256(technical_pdf.read_bytes()).hexdigest()==original
    w.close()


@pytest.mark.parametrize('rotation',[0,90])
def test_single_page_navigation_search_link_selection_and_back(app,technical_pdf,tmp_path,rotation):
    w=Window(Store(tmp_path/'navigation.db'),restore=False);w.show()
    r=w.open_pdf(technical_pdf);wait(app)
    w.set_page_layout('single');wait(app)
    if rotation:r.rotate_by(rotation);wait(app)
    r.jump(0);wait(app)
    link=r.internal_link(r.point_in_view(0,QPointF(100,155)))
    assert link and link.page==2
    r.jump(link.page,link.point());wait(app)
    assert [p for p,_,_ in r.layout_pages()]==[2]
    r.back();wait(app)
    assert r.pageNavigator().currentPage()==0 and r.page_layout_mode=='single'
    r.search.setSearchString('4.2')
    for _ in range(100):
        wait(app,20)
        if r.search.rowCount(QModelIndex())==2:break
    r.visit_search(1);wait(app)
    assert r.pageNavigator().currentPage()==3 and r.currentSearchResultIndex()==1
    assert r.copy_action.isEnabled() is False
    r.select_page_text();assert r.copy_selection()
    assert 'central theorem' in QApplication.clipboard().text()
    assert r.point_on_page(r.point_in_view(3,QPointF(60,120)))[0]==3
    r.forward();wait(app)
    assert r.page_layout_mode=='single'
    w.close()


@pytest.mark.parametrize('rotation',[0,90])
def test_space_and_wheel_turn_single_pages_but_zoomed_content_scrolls_first(app,pdf,tmp_path,rotation):
    w=Window(Store(tmp_path/'turn.db'),restore=False);w.show()
    r=w.open_pdf(pdf);wait(app);w.set_page_layout('single');wait(app)
    if rotation:r.rotate_by(rotation);wait(app)
    r.setFocus()
    QTest.keyClick(r,Qt.Key.Key_Space);wait(app)
    assert r.pageNavigator().currentPage()==1
    QTest.keyClick(r,Qt.Key.Key_Space,Qt.KeyboardModifier.ShiftModifier);wait(app)
    assert r.pageNavigator().currentPage()==0
    scroll(r);wait(app)
    assert r.pageNavigator().currentPage()==1
    scroll(r,delta=120);wait(app)
    assert r.pageNavigator().currentPage()==0
    r.zoom_to(2);r.jump(1);wait(app)
    before=r.verticalScrollBar().value()
    scroll(r);wait(app)
    assert r.pageNavigator().currentPage()==1 and r.verticalScrollBar().value()>before
    r.verticalScrollBar().setValue(r.verticalScrollBar().maximum())
    scroll(r);wait(app)
    assert r.pageNavigator().currentPage()==2
    scroll(r,delta=120);wait(app)
    assert r.pageNavigator().currentPage()==1
    assert r.verticalScrollBar().value()==r.verticalScrollBar().maximum()
    r.jump(7);r.verticalScrollBar().setValue(r.verticalScrollBar().maximum());scroll(r);wait(app)
    assert r.pageNavigator().currentPage()==7
    r.jump(0);scroll(r,delta=120);wait(app)
    assert r.pageNavigator().currentPage()==0
    w.close()


def test_touchpad_threshold_momentum_latch_and_ctrl_zoom(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'gesture.db'),restore=False);w.show()
    r=w.open_pdf(pdf);wait(app);w.set_page_layout('single');wait(app)
    for index in range(3):scroll(r,delta=0,pixels=-15,phase=Qt.ScrollPhase.ScrollBegin if index==0 else Qt.ScrollPhase.ScrollUpdate)
    assert r.pageNavigator().currentPage()==0
    scroll(r,delta=0,pixels=-20,phase=Qt.ScrollPhase.ScrollUpdate)
    assert r.pageNavigator().currentPage()==1
    for _ in range(10):scroll(r,delta=0,pixels=-100,phase=Qt.ScrollPhase.ScrollMomentum)
    assert r.pageNavigator().currentPage()==1
    scroll(r,delta=0,phase=Qt.ScrollPhase.ScrollEnd)
    scroll(r,delta=0,pixels=-70,phase=Qt.ScrollPhase.ScrollBegin)
    assert r.pageNavigator().currentPage()==2
    scroll(r,delta=0,phase=Qt.ScrollPhase.ScrollEnd)
    point=QPointF(r.viewport().rect().center())
    before=r.point_on_page(point)
    scroll(r,delta=120,ctrl=True);wait(app)
    after=r.point_on_page(point)
    assert before[0]==after[0] and (before[1]-after[1]).manhattanLength()<2
    assert r.zoomMode()==r.ZoomMode.Custom
    w.close()


@pytest.mark.parametrize('same_pdf',[False,True])
def test_split_layout_independence_home_swap_and_session_restore(app,pdf,technical_pdf,tmp_path,same_pdf):
    store=Store(tmp_path/'split-session.db')
    w=Window(store,restore=False);w.show();primary=w.open_pdf(pdf)
    if not same_pdf:w.open_pdf(technical_pdf)
    w.split(0,0 if same_pdf else 1);wait(app)
    secondary=w.secondary;w.focus_reader(secondary);w.set_page_layout('single');wait(app)
    primary.jump(2);secondary.jump(3);wait(app)
    assert primary.page_layout_mode=='continuous' and secondary.page_layout_mode=='single'
    assert w.layout_actions['single'].isChecked()
    w.focus_reader(primary)
    assert w.layout_actions['continuous'].isChecked()
    w.focus_reader(secondary);w.swap();w.orientation();wait(app)
    before_primary,before_secondary=primary.state(),secondary.state()
    w.show_home();wait(app);w.resume_reading();wait(app)
    assert primary.state()==before_primary and secondary.state()==before_secondary
    w.close()
    reopened=Window(store,restore=True);reopened.show();wait(app,500)
    assert reopened.active is reopened.secondary
    assert reopened.readers[0].page_layout_mode=='continuous' and reopened.secondary.page_layout_mode=='single'
    assert reopened.readers[0].pageNavigator().currentPage()==2
    assert reopened.secondary.pageNavigator().currentPage()==3
    reopened.close()


def test_preference_survives_paused_history_and_relocation(app,pdf,tmp_path):
    store=Store(tmp_path/'options.db');store.set('history_paused',True)
    w=Window(store,restore=False);w.show();w.open_pdf(pdf);wait(app)
    assert w.active.page_layout_mode=='continuous'
    w.set_page_layout('single');wait(app);w.close_tab(0);wait(app)
    assert store.history()==[]
    moved=tmp_path/'moved.pdf';pdf.rename(moved)
    store.relocate(str(pdf),str(moved))
    assert store.document_layout(moved)=='single' and store.document_layout(pdf)=='continuous'
    r=w.open_pdf(moved);wait(app)
    assert r.page_layout_mode=='single'
    # Old reading states without a layout use the per-file preference.
    r.restore(dict(page=2,mode=r.ZoomMode.FitToWidth.value));wait(app)
    assert r.page_layout_mode=='single' and r.pageNavigator().currentPage()==2
    w.set_page_layout('continuous');wait(app)
    assert store.document_layout(moved)=='continuous'
    w.close()


def test_quick_layout_toggles_and_navigation_cancel_old_corrections(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'rapid.db'),restore=False);w.show();r=w.open_pdf(pdf);wait(app)
    r.jump(3);wait(app)
    w.set_page_layout('single');w.set_page_layout('continuous');wait(app)
    assert r.page_layout_mode=='continuous' and r.pageNavigator().currentPage()==3
    w.set_page_layout('single');wait(app)
    r.zoom_to(1.6,smooth=True);w.set_page_layout('continuous');wait(app)
    assert r.page_layout_mode=='continuous' and r.zoomFactor()==1.6
    r.jump(6);wait(app)
    assert r.pageNavigator().currentPage()==6
    w.close()


def test_paused_old_history_does_not_override_preferred_layout(app,pdf,tmp_path):
    store=Store(tmp_path/'old-history.db')
    w=Window(store,restore=False);w.show();r=w.open_pdf(pdf);wait(app)
    w.remember_reader(r)
    assert store.recent(pdf)['state']['layout']=='continuous'
    store.set('history_paused',True)
    w.set_page_layout('single');wait(app);w.close_tab(0);wait(app)
    w.open_recent(store.recent(pdf));wait(app)
    assert w.active.page_layout_mode=='single'
    w.close_tab(0);wait(app);w.open_pdf(pdf);wait(app)
    assert w.active.page_layout_mode=='single'
    w.close()


def test_favorite_keeps_independent_layout_then_replacing_rotated_single_document(app,pdf,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'saved-layout.db'),restore=False);w.show()
    primary=w.open_pdf(pdf);w.open_pdf(technical_pdf);w.split(0,0);wait(app)
    other=w.secondary;w.focus_reader(other);w.set_page_layout('single');wait(app)
    other.rotate_by(90);other.jump(7);wait(app)
    w.open_saved(dict(path=str(pdf),page=4));wait(app)
    assert w.active is other and other.page_layout_mode=='single' and other.rotation==90
    assert primary.page_layout_mode=='continuous' and primary.rotation==0
    w.store.set_document_layout(technical_pdf,'single')
    target=next(r for r in w.readers if r.path==str(technical_pdf))
    target.set_page_layout('single');target.rotate_by(90)
    w.open_saved(dict(path=str(technical_pdf),page=2));wait(app)
    assert other.path==str(technical_pdf) and other.pageNavigator().currentPage()==2
    assert other.page_layout_mode=='single' and other.rotation==90
    assert [page for page,_,_ in other.layout_pages()]==[2]
    w.close()


def test_single_page_fullscreen_overlay_resize_closed_tab_and_marker(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'fullscreen-layout.db'),restore=False);w.show()
    r=w.open_pdf(pdf);wait(app);w.set_page_layout('single');wait(app)
    r.zoom_to(1.5);r.jump(3,QPointF(70,150));wait(app)
    w.save_marker();r.jump(5);w.return_marker();wait(app)
    assert r.page_layout_mode=='single' and r.pageNavigator().currentPage()==3
    w.fullscreen();wait(app,400)
    assert w.isFullScreen() and r.page_layout_mode=='single'
    before=r.state();size=r.viewport().size()
    w.show_chrome();wait(app)
    assert r.viewport().size()==size and r.state()==before
    w.toggle_chrome();wait(app)
    assert r.viewport().size()==size and r.state()==before
    w.fullscreen();wait(app,400)
    old=r.state();w.resize(920,800);wait(app)
    assert r.page_layout_mode=='single' and r.pageNavigator().currentPage()==3
    assert abs(r.state()['y']-old['y'])<2
    old=r.state(include_history=True)
    w.close_tab(0);w.reopen_closed_tab();wait(app)
    assert w.active.state(include_history=True)==old
    w.close()


@pytest.mark.parametrize('rotation',[0,90])
def test_contents_panel_navigates_single_page_without_changing_layout(app,technical_pdf,tmp_path,rotation):
    from mellow.locations import LocationsPanel
    w=Window(Store(tmp_path/'contents-layout.db'),restore=False);w.show()
    r=w.open_pdf(technical_pdf);wait(app);w.set_page_layout('single');wait(app)
    if rotation:r.rotate_by(rotation);wait(app)
    panel=LocationsPanel(w,'bookmark');panel.show();wait(app)
    index=panel.outline_filter.index(2,0)
    QTest.mouseClick(panel.outline.viewport(),Qt.MouseButton.LeftButton,
                     pos=panel.outline.visualRect(index).center())
    wait(app)
    assert not panel.isVisible() and r.page_layout_mode=='single'
    assert r.pageNavigator().currentPage()==2 and r.rotation==rotation
    assert [page for page,_,_ in r.layout_pages()]==[2]
    r.back();wait(app)
    assert r.pageNavigator().currentPage()==0 and r.page_layout_mode=='single'
    w.close()


def test_scrolling_after_pending_zoom_uses_enlarged_page_before_turning(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'zoom-scroll.db'),restore=False);w.show()
    r=w.open_pdf(pdf);wait(app);w.set_page_layout('single');wait(app)
    scroll(r,delta=120,ctrl=True)
    assert r._zoom_target is not None
    scroll(r)
    wait(app,100)
    assert r.pageNavigator().currentPage()==0 and r.zoomMode()==r.ZoomMode.Custom
    assert r._zoom_target is None and r.verticalScrollBar().value()>0
    saved=r.state();wait(app,80)
    assert r.state()==saved
    w.close()
