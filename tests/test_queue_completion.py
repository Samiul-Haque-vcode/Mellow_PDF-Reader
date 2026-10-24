"""Real reader integration for the remaining menu, preferences and reading aids."""
import pytest
from PySide6.QtCore import Qt,QPointF,QPoint
from PySide6.QtGui import QWheelEvent,QNativeGestureEvent,QPointingDevice
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtTest import QTest
from reportlab.pdfgen.canvas import Canvas
from test_reader import app,pdf,technical_pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.settings import SettingsDialog
from mellow import backup


def opened(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'complete.db'),restore=False);w.resize(1400,850);w.show()
    r=w.open_pdf(pdf);wait(app,80)
    return w,r


def settled_lens(app,r):
    for _ in range(150):
        if r.aids.overlay is not None and r.aids.overlay.image is not None and r.aids.pending is None:return
        wait(app,10)
    pytest.fail('Lens did not render the PDF region')


def test_settings_menu_and_toolbar_have_single_theme_and_ruler_location(app,pdf,tmp_path):
    w,r=opened(app,pdf,tmp_path)
    w.populate_overflow()
    names=[a.text() for a in w.more_menu.actions() if a.isVisible() and not a.isSeparator()]
    assert names==['Document','Reading','Page layout','PDF Tools','Settings','About / Credits…']
    assert w.ruler_action in w.reading_menu.actions()
    assert w.toolbar.widgetForAction(w.ruler_action) is None and 'theme' not in w.toolbar.entries
    assert not hasattr(w,'themes')
    d=SettingsDialog(w.store,w)
    assert [d.tabs.tabText(i) for i in range(d.tabs.count())]==['General','Reading','Appearance','Shortcuts']
    assert d.tabs.widget(0).isAncestorOf(d.backup_data) and d.tabs.widget(0).isAncestorOf(d.record_history)
    assert d.tabs.widget(1).isAncestorOf(d.copy_format) and d.tabs.widget(1).isAncestorOf(d.height)
    assert d.tabs.widget(2).isAncestorOf(d.theme) and d.tabs.widget(2).isAncestorOf(d.hide_delay)
    assert list(d.shortcut_groups)==['Documents and Tabs','Navigation and Zoom','Text Selection and Copying','Quick Jump','Split Reading','Window and Fullscreen','PDF Tools']
    d.theme.setCurrentText('Dark');d.copy_format.setCurrentIndex(1);d.default_layout.setCurrentIndex(2);d.reject()
    assert w.theme_name=='Sepia' and w.store.get('copy_format') is None
    d.deleteLater();w.close()


def test_narrow_toolbar_commands_remain_reachable_without_permanent_duplicates(app,pdf,tmp_path):
    w,r=opened(app,pdf,tmp_path);w.resize(440,800);wait(app,50)
    w.populate_overflow()
    assert w.overflow_menu.menuAction().isVisible()
    entries=w.overflow_menu.actions()
    for key,action in [('rotation',w.rotation_actions[0]),('favorites',w.favorites_action),('fullscreen',w.fullscreen_action)]:
        if key in w.toolbar.collapsed:assert action in entries
    w.resize(1800,850);wait(app,50);w.populate_overflow()
    assert not w.overflow_menu.menuAction().isVisible()
    w.ruler_action.trigger();assert r.ruler
    w.show_home();w.populate_overflow();assert not w.overflow_menu.menuAction().isVisible()
    w.close()


def test_defaults_copy_format_existing_document_precedence_and_backup(app,pdf,technical_pdf,tmp_path):
    w,r=opened(app,pdf,tmp_path)
    w.set_page_layout('single');r.zoom_to(1.25);w.remember_reader(r)
    d=SettingsDialog(w.store,w);d.default_layout.setCurrentIndex(2);d.fit.setCurrentText('Fit Width');d.copy_format.setCurrentIndex(1)
    w.apply_settings(d.values());d.reject();d.deleteLater()
    assert r.page_layout_mode=='single' and r.zoomFactor()==1.25
    other=w.open_pdf(technical_pdf);wait(app,40)
    assert other.page_layout_mode=='two' and other.zoomMode()==QPdfView.ZoomMode.FitToWidth
    other.select_page_text();other.copy_action.trigger()
    assert QApplication.clipboard().text()==other.text_selection.text(True)
    assert w.store.document_layout(pdf)=='single'
    data=backup.snapshot(w.store);backup.validate(data)
    assert w.store.get('copy_format')=='paragraphs'
    w.close()


def test_history_clear_confirmation_keeps_favorites_and_cancel_isolated(app,pdf,tmp_path,monkeypatch):
    w,r=opened(app,pdf,tmp_path);w.store.add('favorite',str(pdf),0,'Keep')
    d=SettingsDialog(w.store,w)
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.StandardButton.No)
    w.clear_reading_history(d);assert w.store.history()
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.StandardButton.Yes)
    w.clear_reading_history(d)
    assert not w.store.history() and w.store.get('history_paused') and not d.record_history.isChecked()
    assert w.store.locations('favorite') and pdf.is_file()
    d.reset_general();assert d.record_history.isChecked() and w.store.get('history_paused')
    d.reject();d.deleteLater();w.close()


def test_zoom_lock_blocks_all_controls_and_preserves_other_split(app,pdf,tmp_path):
    w,first=opened(app,pdf,tmp_path);w.split(0,0);wait(app,40);second=w.secondary
    w.focus_reader(first);first.set_quick_jump();w.lock_zoom_action.trigger();wait(app,40)
    before=first.zoomFactor()
    assert first.zoom_locked and first.zoomMode()==QPdfView.ZoomMode.Custom
    first.zoom_by(2);first.zoom_to(4);first.setZoomFactor(5);first.setZoomMode(QPdfView.ZoomMode.FitToWidth);w.set_fit(1)
    point=QPointF(first.viewport().rect().center())
    event=QWheelEvent(point,QPointF(first.viewport().mapToGlobal(point.toPoint())),QPoint(),QPoint(0,120),Qt.MouseButton.NoButton,Qt.KeyboardModifier.ControlModifier,Qt.ScrollPhase.NoScrollPhase,False)
    QApplication.sendEvent(first.viewport(),event)
    native=QNativeGestureEvent(Qt.NativeGestureType.ZoomNativeGesture,QPointingDevice.primaryPointingDevice(),2,point,point,QPointF(first.viewport().mapToGlobal(point.toPoint())),.2,QPointF(),1)
    QApplication.sendEvent(first.viewport(),native)
    first.restore(first.marker);wait(app,40)
    assert first.zoomFactor()==before and not w.fit.isEnabled() and not w.zoom_in_action.isEnabled()
    second.zoom_to(1.6);wait(app,20);assert abs(second.zoomFactor()-1.6)<.001
    w.focus_reader(second);w.update_controls();assert not w.lock_zoom_action.isChecked() and w.fit.isEnabled()
    w.focus_reader(first);w.lock_zoom_action.trigger();first.zoom_to(2);wait(app,20)
    assert not first.zoom_locked and first.zoomFactor()==2
    w.close()


def test_nested_outline_navigation_and_history(app,tmp_path):
    path=tmp_path/'chapters.pdf';c=Canvas(str(path))
    for page in range(5):
        c.drawString(40,700,f'Chapter test page {page}')
        c.bookmarkPage(str(page))
        c.addOutlineEntry('Chapter' if page in (0,3) else 'Nested section',str(page),0 if page in (0,3) else 1)
        c.showPage()
    c.save();w,r=opened(app,path,tmp_path)
    for _ in range(50):
        if r.aids.index_ready:break
        wait(app,10)
    assert [target[0] for target in r.aids.targets]==list(range(5))
    for page in (1,2,3,4):
        assert r.aids.chapter_step(1);wait(app,20);assert r.pageNavigator().currentPage()==page
    assert not r.aids.chapter_step(1)
    assert r.aids.chapter_step(-1);wait(app,20);assert r.pageNavigator().currentPage()==3
    r.back();wait(app,20);assert r.pageNavigator().currentPage()==4
    w.close()


@pytest.mark.parametrize('angle',[0,90,180,270])
def test_lens_renders_real_colored_region_without_navigation_and_releases(app,tmp_path,angle):
    path=tmp_path/'lens.pdf';c=Canvas(str(path));c.setFillColorRGB(1,0,0);c.rect(60,600,100,100,fill=1,stroke=0);c.showPage();c.save()
    w,r=opened(app,path,tmp_path);w.resize(760,700);w.move(0,0);w.raise_();w.activateWindow()
    r.set_rotation(angle);r.change_crop((1,1,1,1));wait(app,40)
    try:
        before=r.state(include_history=True)
        point=r.point_in_view(0,QPointF(110,190)).toPoint()
        # Keep the actual source point inside the viewport at every rotation.
        r.horizontalScrollBar().setValue(r.horizontalScrollBar().value()+point.x()-r.viewport().width()//2)
        r.verticalScrollBar().setValue(r.verticalScrollBar().value()+point.y()-r.viewport().height()//2)
        point=r.point_in_view(0,QPointF(110,190)).toPoint();before=r.state(include_history=True)
        r.aids.set_lens_enabled(True);QTest.mouseMove(r.viewport(),point);settled_lens(app,r)
        image=r.aids.overlay.image;center=image.pixelColor(image.width()//2,image.height()//2)
        assert center.red()>220 and center.green()<40 and center.blue()<40
        assert image.sizeInBytes()<2*1024*1024 and r.state(include_history=True)==before
        r.setFocus();QTest.keyClick(r,Qt.Key.Key_Escape)
        assert not r.aids.lens_enabled and r.aids.renderer is None and not r.aids.timer.isActive()
    finally:w.close()


def test_no_outline_and_lens_tab_close_cleanup(app,pdf,tmp_path):
    path=tmp_path/'no-outline.pdf';c=Canvas(str(path));c.drawString(40,700,'No chapters');c.showPage();c.save()
    w,r=opened(app,path,tmp_path);wait(app,20)
    assert r.aids.index_ready and r.aids.chapter_target(1) is None
    r.aids.set_lens_enabled(True);QTest.mouseMove(r.viewport(),r.point_in_view(0,QPointF(80,140)).toPoint())
    w.close_tab(0);wait(app,20)
    assert not w.readers
    w.close()


def test_changed_defaults_do_not_reset_existing_view_when_saving_crop_or_cover(app,pdf,technical_pdf,tmp_path):
    w,r=opened(app,pdf,tmp_path)
    w.store.set('default_layout','two')
    other=w.open_pdf(technical_pdf);wait(app,30)
    assert other.page_layout_mode=='two'
    w.apply_settings({'default_layout':'single'})
    w.apply_margins((1,1,1,1));w.set_cover(False)
    assert other.page_layout_mode=='two' and w.store.document_layout(technical_pdf)=='two'
    w.remember_reader(other)
    w.close_tab(w.readers.index(other));other=w.open_pdf(technical_pdf);wait(app,30)
    assert other.page_layout_mode=='two' and not other.cover_separate
    w.close()
