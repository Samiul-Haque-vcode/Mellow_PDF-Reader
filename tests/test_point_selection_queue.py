"""Queued page-popup behavior, actual text clicks and cancellable full-book copy."""
import pytest
from PySide6.QtCore import Qt,QPointF,QTimer
from PySide6.QtWidgets import QApplication,QLineEdit,QMenu,QDialog
from PySide6.QtTest import QTest
from reportlab.pdfgen.canvas import Canvas
from test_reader import app,pdf,wait
from test_selection_and_home import text_point
from mellow.app import Window
from mellow.storage import Store
from mellow.page_preferences import MarginsDialog
from mellow.shortcuts import validate,migrate_navigation


def opened(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'points.db'),restore=False);w.resize(1100,800);w.show()
    r=w.open_pdf(pdf);r.zoom_to(1.2);wait(app,50)
    return w,r


def visible_text(r,page,index,right=False):
    point=text_point(r,page,index,right)
    bar=r.verticalScrollBar()
    bar.setValue(bar.value()+point.y()-120)
    return text_point(r,page,index,right)


@pytest.mark.parametrize('reverse',[False,True])
@pytest.mark.parametrize('rotated',[False,True])
def test_two_text_clicks_scroll_and_copy_popup(app,pdf,tmp_path,reverse,rotated):
    w,r=opened(app,pdf,tmp_path)
    if rotated:r.rotate_by(180);r.change_crop((1,1,1,1));wait(app,50)
    before=(r.zoomMode(),r.zoomFactor(),list(r._past))
    first,last=((1,15,True),(0,0,False)) if reverse else ((0,0,False),(1,15,True))
    r.start_point_selection()
    QTest.mouseClick(r.viewport(),Qt.MouseButton.LeftButton,pos=visible_text(r,*first));wait(app,10)
    assert r._two_point_mode=='end' and r._copy_popup is None
    point=visible_text(r,*last)
    QTest.mouseClick(r.viewport(),Qt.MouseButton.LeftButton,pos=point);wait(app,10)
    assert r._two_point_mode is None and r.text_selection.ranges
    popup=r._copy_popup
    assert popup and [a.text() for a in popup.actions()]==['Copy — Preserve Line Breaks','Copy — Join Paragraphs']
    expected=r.selected_text()
    assert 'Mellow chapter 1' in expected and 'Mellow chapter 2' in expected
    QTest.mouseClick(popup,Qt.MouseButton.LeftButton,pos=popup.actionGeometry(popup.actions()[0]).center())
    assert QApplication.clipboard().text()==expected and r.text_selection.ranges
    assert (r.zoomMode(),r.zoomFactor(),r._past)==before
    w.close()


def test_popup_copy_shortcut_and_escape_cancel_before_fullscreen_exit(app,pdf,tmp_path):
    w,r=opened(app,pdf,tmp_path)
    r.start_point_selection()
    QTest.mouseClick(r.viewport(),Qt.MouseButton.LeftButton,pos=visible_text(r,0,0))
    QTest.mouseClick(r.viewport(),Qt.MouseButton.LeftButton,pos=visible_text(r,0,14,True));wait(app,10)
    popup=r._copy_popup;expected=r.selected_text()
    QTest.keyClick(popup,Qt.Key.Key_C,Qt.KeyboardModifier.ControlModifier)
    assert QApplication.clipboard().text()==expected
    w.fullscreen();wait(app,50);r.start_point_selection();r.setFocus()
    QTest.keyClick(r,Qt.Key.Key_Escape)
    assert r._two_point_mode is None and w.isFullScreen()
    w.close()


def test_menu_marker_clicked_location_and_contextual_actions(app,pdf,tmp_path):
    w,r=opened(app,pdf,tmp_path)
    point=visible_text(r,0,0)
    hit=r.point_on_page(QPointF(point))
    menu=r.page_context_menu(point)
    names=[a.text() for a in menu.actions() if not a.isSeparator()]
    assert names[:4]==['Set Quick Jump Here','Return to Quick Jump','Select Between Two Points…','Trim Reading Margins…']
    assert all(name not in names for name in ['Copy selected text','Copy text as','Select page text','Preview page…','Find reference…'])
    assert not menu.actions()[1].isEnabled()
    menu.actions()[0].trigger()
    assert r.marker['anchor_page']==hit[0] and abs(r.marker['y']-hit[1].y())<.01
    assert r.marker['viewport'] is None
    r.jump(4);wait(app,30)
    menu.deleteLater();menu=r.page_context_menu(visible_text(r,4,0))
    menu.actions()[1].trigger();wait(app,30)
    assert r.pageNavigator().currentPage()==0
    assert not any(a.text() in ('Set Quick Jump','Return to Quick Jump') for a in w.reading_menu.actions())
    menu.deleteLater();w.close()


def test_selection_shortcuts_and_text_field_isolation(app,pdf,tmp_path):
    w,r=opened(app,pdf,tmp_path);r.setFocus()
    QTest.keyClick(r,Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier)
    assert list(r.text_selection.ranges)==[0]
    QTest.keyClick(r,Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier)
    assert len(r.text_selection.ranges)==8
    QTest.keyClick(r,Qt.Key.Key_C,Qt.KeyboardModifier.ControlModifier)
    assert 'chapter 1' in QApplication.clipboard().text() and 'chapter 8' in QApplication.clipboard().text()
    old=dict(r.text_selection.ranges)
    w.inline_search.text.setText('Selected in field')
    w.inline_search.text.setFocus()
    QTest.keyClick(w.inline_search.text,Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier)
    assert w.inline_search.text.selectedText()=='Selected in field' and r.text_selection.ranges==old
    w.apply_settings({'shortcuts':{'select_page':'Alt+A','select_document':'Alt+Shift+A'}})
    r.clear_selection();r.setFocus();QTest.keyClick(r,Qt.Key.Key_A,Qt.KeyboardModifier.AltModifier)
    assert list(r.text_selection.ranges)==[0]
    assert migrate_navigation({'search':'Ctrl+Shift+A'})['select_document']==''
    with pytest.raises(ValueError):validate({'search':'Ctrl+A'})
    w.close()


def test_large_book_lazy_selection_cancel_copy_and_success(app,tmp_path):
    path=tmp_path/'book.pdf';c=Canvas(str(path))
    for page in range(25):c.drawString(40,700,f'BOOK PAGE {page+1}');c.showPage()
    c.save();w,r=opened(app,path,tmp_path)
    r.select_document_text()
    assert len(r.text_selection._full)<=4 and len(r.text_selection.ranges)==25
    QApplication.clipboard().setText('keep old clipboard')
    assert r.copy_selection() and r._copy_job is not None
    assert QApplication.clipboard().text()=='keep old clipboard'
    w.escape();wait(app,20)
    assert r._copy_job is None and QApplication.clipboard().text()=='keep old clipboard'
    r.select_document_text();r.copy_selection()
    for _ in range(100):
        if r._copy_job is None:break
        wait(app,10)
    assert r._copy_job is None
    assert 'BOOK PAGE 1' in QApplication.clipboard().text() and 'BOOK PAGE 25' in QApplication.clipboard().text()
    r.copy_selection();w.close_tab(0);wait(app,20)
    assert not w.readers
    w.close()


def test_blank_pdf_no_text_feedback_and_escape(app,tmp_path):
    path=tmp_path/'scan.pdf';c=Canvas(str(path));c.showPage();c.save()
    w,r=opened(app,path,tmp_path);r.start_point_selection()
    QTest.mouseClick(r.viewport(),Qt.MouseButton.LeftButton,pos=r.viewport().rect().center())
    assert r._two_point_mode=='start' and 'text layer' in r.selection_message
    QTest.keyClick(r,Qt.Key.Key_Escape)
    assert r._two_point_mode is None and not r.text_selection.ranges
    w.close()


def test_context_margins_targets_clicked_split_and_marker_not_restored(app,pdf,tmp_path,monkeypatch):
    w,r=opened(app,pdf,tmp_path);w.split(0,0);wait(app,30);second=w.secondary
    seen=[]
    def inspect(dialog):
        seen.append(dialog)
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(MarginsDialog,'exec',inspect)
    menu=second.page_context_menu(visible_text(second,1,0))
    next(a for a in menu.actions() if a.text()=='Trim Reading Margins…').trigger()
    assert seen and w.active is second and not any(r.crop)
    second.set_quick_jump();w.save_session();store=w.store;menu.deleteLater();w.close()
    restored=Window(store,restore=False);restored.show();restored.restore_session();wait(app,50)
    assert all(reader.marker is None for reader in restored.readers+[restored.secondary] if reader)
    restored.close()


def test_escape_cancels_armed_selection_even_with_search_open(app,pdf,tmp_path):
    w,r=opened(app,pdf,tmp_path)
    w.search_dialog(initial='Mellow');r.start_point_selection()
    assert w._search_open and r._two_point_mode
    r.setFocus();QTest.keyClick(r,Qt.Key.Key_Escape)
    assert r._two_point_mode is None and not r.text_selection.ranges
    w.close()


def test_native_reference_context_navigation_and_marker_document_change(app,pdf,tmp_path):
    w,r=opened(app,pdf,tmp_path)
    point=r.point_in_view(0,QPointF(100,125)).toPoint()
    assert r.internal_link(QPointF(point)) is not None
    menu=r.page_context_menu(point)
    next(a for a in menu.actions() if a.text()=='Go to Reference').trigger();wait(app,30)
    assert r.pageNavigator().currentPage()==2
    r.back();wait(app,30);assert r.pageNavigator().currentPage()==0
    r.set_quick_jump();assert r.marker
    r.setDocument(None);assert r.marker is None
    menu.deleteLater();w.close()


def test_old_shortcut_and_backup_survive_new_document_selection_default(app,tmp_path):
    from mellow.settings import SettingsDialog
    from mellow.shortcuts import ShortcutManager
    from mellow import backup
    store=Store(tmp_path/'old-keys.db');store.set('shortcuts',{'search':'Ctrl+Shift+A'})
    manager=ShortcutManager(store.get('shortcuts'))
    assert manager.bindings['search']=='Ctrl+Shift+A' and manager.bindings['select_document']==''
    dialog=SettingsDialog(store)
    assert dialog.shortcut_edits['search'].keySequence().toString()=='Ctrl+Shift+A'
    assert dialog.shortcut_edits['select_document'].keySequence().isEmpty()
    backup.validate(backup.snapshot(store))
    dialog.reject();dialog.deleteLater()


def test_copy_popup_outside_click_and_other_split_selection_are_independent(app,pdf,tmp_path):
    w,first=opened(app,pdf,tmp_path);w.split(0,0);wait(app,30)
    second=w.secondary;second.select_page_text(2);before=second.selected_text()
    first.start_point_selection()
    QTest.mouseClick(first.viewport(),Qt.MouseButton.LeftButton,pos=visible_text(first,0,0))
    QTest.mouseClick(first.viewport(),Qt.MouseButton.LeftButton,pos=visible_text(first,0,14,True));wait(app,10)
    popup=first._copy_popup;assert popup
    # A real context popup dismisses on an outside click and leaves the other
    # pane's independent selection intact.
    QTest.mouseClick(w.toolbar.widgetForAction(w.home_action),Qt.MouseButton.LeftButton)
    wait(app,20)
    assert first._copy_popup is None and second.selected_text()==before
    w.close()


@pytest.mark.parametrize('joined',[False,True])
def test_copy_job_keeps_page_order_and_cancels_mid_extraction(app,tmp_path,joined):
    from PySide6.QtWidgets import QProgressBar
    path=tmp_path/'ordered.pdf';c=Canvas(str(path))
    for page in range(12):
        c.drawString(40,700,f'Ordered page {page+1}')
        c.drawString(40,680,'This is a sufficiently long line of ordinary prose')
        c.drawString(40,666,'continued on another line for a paragraph copy check.')
        c.showPage()
    c.save();w,r=opened(app,path,tmp_path);r.select_document_text()
    expected=r.text_selection.text(join_paragraphs=joined)
    QApplication.clipboard().setText('unchanged')
    r.copy_selection(joined);job=r._copy_job
    job.progress.findChild(QProgressBar).valueChanged.connect(lambda count:job.cancel() if count==2 else None)
    for _ in range(50):
        if r._copy_job is None:break
        wait(app,10)
    assert r._copy_job is None and QApplication.clipboard().text()=='unchanged'
    r.copy_selection(joined)
    for _ in range(100):
        if r._copy_job is None:break
        wait(app,10)
    assert r._copy_job is None and QApplication.clipboard().text()==expected
    w.close()


def test_newer_split_copy_supersedes_pending_copy(app,tmp_path):
    path=tmp_path/'split-copy.pdf';c=Canvas(str(path))
    for page in range(12):c.drawString(40,700,f'Clipboard page {page}');c.showPage()
    c.save();w,first=opened(app,path,tmp_path);w.split(0,0);wait(app,30)
    try:
        second=w.secondary
        first.select_document_text();first.copy_selection()
        second.select_document_text();second.copy_selection()
        assert first._copy_job is None and second._copy_job is not None
        QApplication.clipboard().setText('new clipboard contents')
        assert second._copy_job is None
        wait(app,30)
        assert QApplication.clipboard().text()=='new clipboard contents'
    finally:w.close()
