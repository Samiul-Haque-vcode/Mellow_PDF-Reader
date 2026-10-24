"""Navigation batch: actual keys, responsive controls and read-only metadata."""
from mellow.dialogs import DismissibleInputDialog
import hashlib
from pathlib import Path
import pytest
from PySide6.QtCore import Qt, QModelIndex, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QInputDialog
from test_reader import app, pdf, technical_pdf, wait
from mellow.app import Window
from mellow.storage import Store
from mellow.document_info import DocumentInfoDialog, document_fields
from mellow.shortcuts import validate


def finish_search(app,reader,total=8):
    for _ in range(80):
        if reader.search.rowCount(QModelIndex())>=total: break
        wait(app,25)
    assert reader.search.rowCount(QModelIndex())>=total


def test_tab_keys_wrap_preserve_state_and_resume_from_home(app,pdf,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'tabs.db'),restore=False);w.show()
    first=w.open_pdf(pdf);second=w.open_pdf(technical_pdf);wait(app)
    first.restore(dict(page=3,zoom=1.4,mode=0));second.restore(dict(page=2,zoom=1.2,mode=0));wait(app)
    saved=[r.state(include_history=True) for r in (first,second)]
    QTest.keyClick(second,Qt.Key.Key_Tab,Qt.KeyboardModifier.ControlModifier)
    wait(app)
    assert w.active is first and w.tabs.currentIndex()==0
    assert first.state(include_history=True)==saved[0]
    QTest.keyClick(first,Qt.Key.Key_Backtab,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier)
    wait(app)
    assert w.active is second and second.state(include_history=True)==saved[1]
    w.show_home()
    QTest.keyClick(w.home.filter,Qt.Key.Key_Tab,Qt.KeyboardModifier.ControlModifier)
    wait(app)
    assert not w._on_home and w.active is first
    w.close_tab(1)
    assert not w.tab_next_action.isEnabled() and not w.tab_previous_action.isEnabled()
    state=first.state()
    w.cycle_tab(1)
    assert first.state()==state
    w.close()


def test_tab_cycle_exits_split_like_tab_click_and_flushes_zoom(app,pdf,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'split-tabs.db'),restore=False);w.show()
    first=w.open_pdf(pdf);second=w.open_pdf(technical_pdf);wait(app)
    w.split(0,1);wait(app)
    first.zoom_by(1.2,smooth=True)
    target=first._zoom_target
    first.setFocus()
    QTest.keyClick(first,Qt.Key.Key_Tab,Qt.KeyboardModifier.ControlModifier)
    wait(app)
    assert w.active is second and w.secondary is None
    w.cycle_tab(-1);wait(app)
    assert w.active is first and first.zoomFactor()==target
    w.apply_settings({'shortcuts':{'tab_next':'Ctrl+Shift+N','tab_previous':''}})
    first.setFocus()
    QTest.keyClick(first,Qt.Key.Key_N,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier)
    wait(app)
    assert w.active is second
    assert w.tab_previous_action.shortcut().isEmpty()
    with pytest.raises(ValueError): validate({'tab_next':'Ctrl+O'})
    w.close()


def test_existing_custom_tab_binding_is_migrated_without_reset(app,tmp_path):
    store=Store(tmp_path/'old-keys.db')
    store.set('shortcuts',{'favorites':'Ctrl+Tab','home':'Ctrl+H'})
    w=Window(store,restore=False)
    assert w.shortcuts.bindings['favorites']=='Ctrl+Tab'
    assert w.shortcuts.bindings['home']=='Ctrl+H'
    assert w.shortcuts.bindings['tab_next']==''
    assert w.shortcuts.bindings['tab_previous']=='Ctrl+Shift+Tab'
    assert store.get('shortcuts')['tab_next']==''
    validate(store.get('shortcuts'))
    w.close()


@pytest.mark.parametrize('labels',[False,True])
def test_responsive_toolbar_keeps_shortcuts_and_menu_fallbacks(app,pdf,tmp_path,labels):
    w=Window(Store(tmp_path/'responsive.db'),restore=False);w.show()
    r=w.open_pdf(pdf);wait(app)
    w.apply_settings({'toolbar_labels':labels})
    w.resize(520,760);wait(app)
    assert 'zoom' in w.toolbar.collapsed and not w.fit.isVisible()
    w.populate_overflow()
    assert w.home_action not in w.more_menu.actions() and w.open_action not in w.more_menu.actions()
    assert w.back_action in w.overflow_menu.actions()
    assert w.info_action in w.document_menu.actions()
    assert [action.text() for action in w.more_menu.actions() if action.menu()]==['Document','Reading','Page layout','PDF Tools','More reading controls']
    before=r.effective_zoom()
    QTest.keyClick(r,Qt.Key.Key_Equal,Qt.KeyboardModifier.ControlModifier)
    wait(app)
    assert r.zoomFactor()>before
    assert r.zoomMode()==r.ZoomMode.Custom
    assert w.zoom_in_action.isVisible() and w.zoom_in_action.isEnabled()
    assert w.more_button.isVisible()
    assert w.page.isVisible() and w.page_total.text()=='/ 8'
    w.back_action.trigger()  # Overflow and shortcuts keep the shared action.
    w.resize(1600,850);wait(app)
    # Windows can clamp the requested top-level width to its available screen;
    # text labels and native fonts also change the space each group requires.
    required=24+sum(max(0,entry['widget'].sizeHint().width())+4
                    for entry in w.toolbar.entries.values() if entry['available'])
    if required<=w.toolbar.width(): assert not w.toolbar.collapsed
    assert 'zoom' not in w.toolbar.collapsed and w.fit.isVisible()
    assert w.toolbar.collapsed<=set(('history','ruler','bookmarks','favorites','theme','split','fullscreen','rotation'))
    assert w.toolbar.widgetForAction(w.fullscreen_action).isVisible()
    w.close()


def test_menu_page_zoom_and_query_updates_remain_available_when_controls_collapse(app,pdf,tmp_path,monkeypatch):
    w=Window(Store(tmp_path/'fallbacks.db'),restore=False);w.show()
    r=w.open_pdf(pdf);wait(app)
    w.search_dialog(initial='Mellow');finish_search(app,r)
    w.inline_search.step(1)
    w.inline_search.text.setCursorPosition(2)
    QTest.keyClicks(w.inline_search.text,'X')
    assert w.inline_search.text.text()=='MeXllow'
    assert w.inline_search.text.cursorPosition()==3
    w.inline_search.text.setText('chapter');finish_search(app,r)
    assert r.search.searchString()=='chapter' and w.inline_search.text.text()=='chapter'
    r.search.setSearchString('Equation')
    assert w.inline_search.text.text()=='Equation'
    w.apply_settings({'toolbar_labels':True})
    w.resize(300,760);wait(app)
    assert w.width()>=440 and w.inline_search.previous.isVisible() and w.inline_search.next.isVisible()
    assert w.more_button.isVisible()
    monkeypatch.setattr(DismissibleInputDialog,'getText',lambda *args,**kwargs:('#4',True))
    w.page_prompt();wait(app)
    assert r.pageNavigator().currentPage()==3
    monkeypatch.setattr(DismissibleInputDialog,'getDouble',lambda *args,**kwargs:(175,True))
    w.zoom_prompt();wait(app)
    assert r.zoomFactor()==1.75
    w.close()


def test_tab_keys_in_modal_settings_leave_document_tabs_alone(app,pdf,technical_pdf,tmp_path):
    from mellow.settings import SettingsDialog
    w=Window(Store(tmp_path/'modal-tabs.db'),restore=False);w.show()
    w.open_pdf(pdf);w.open_pdf(technical_pdf);wait(app)
    selected=w.tabs.currentIndex()
    dialog=SettingsDialog(w.store,w)
    observed=[]
    def switch_settings():
        QTest.keyClick(dialog.tabs,Qt.Key.Key_Tab,Qt.KeyboardModifier.ControlModifier)
        observed.append((dialog.tabs.currentIndex(),w.tabs.currentIndex()))
        dialog.reject()
    QTimer.singleShot(40,switch_settings)
    dialog.exec()
    assert observed==[(1,selected)]
    w.close()


def test_document_metadata_is_displayed_as_plain_text(app,tmp_path):
    from reportlab.pdfgen.canvas import Canvas
    path=tmp_path/'metadata.pdf'
    canvas=Canvas(str(path));canvas.setTitle('<b>Literal title</b>');canvas.setAuthor('A & B')
    canvas.drawString(40,700,'Document metadata');canvas.save()
    w=Window(Store(tmp_path/'metadata.db'),restore=False);w.show()
    r=w.open_pdf(path);wait(app)
    dialog=DocumentInfoDialog(r,w)
    assert dialog.labels['Title'].text()=='<b>Literal title</b>'
    assert dialog.labels['Title'].textFormat()==Qt.TextFormat.PlainText
    assert dialog.fields['Author']=='A & B'
    assert not dialog.labels['Title'].openExternalLinks()
    dialog.reject();w.close()


def test_toolbar_page_totals_follow_focused_document_and_printed_labels(app,pdf,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'totals.db'),restore=False);w.show()
    first=w.open_pdf(pdf);w.open_pdf(technical_pdf);wait(app)
    w.split(0,1);wait(app)
    w.secondary.jump(1);w.focus_reader(w.secondary);wait(app)
    assert w.page.currentText()=='ii' and w.page_total.text()=='/ 5'
    assert w.page_total.toolTip()=='PDF page 2 of 5'
    w.focus_reader(first);wait(app)
    assert w.page_total.text()=='/ 8'
    assert not w.previous_action.isEnabled()
    w.close()


@pytest.mark.parametrize('fit',['custom','width','page'])
def test_resizing_split_preserves_source_anchors_and_navigation_history(app,pdf,technical_pdf,tmp_path,fit):
    from pypdf import PdfWriter
    # Leave enough following pages to restore the anchor at the viewport top;
    # near the end of a short PDF the native scroll range must clamp instead.
    mixed=tmp_path/'extended-technical.pdf'
    writer=PdfWriter()
    for _ in range(3): writer.append(technical_pdf)
    writer.write(mixed);writer.close()
    w=Window(Store(tmp_path/'resize.db'),restore=False);w.show()
    first=w.open_pdf(pdf);w.open_pdf(mixed);wait(app)
    w.split(0,1);wait(app)
    readers=[first,w.secondary]
    for i,r in enumerate(readers):
        r.setZoomMode(r.ZoomMode.Custom)
        r.setZoomFactor(1.2+i*.2)
        if fit!='custom': r.setZoomMode(r.ZoomMode.FitToWidth if fit=='width' else r.ZoomMode.FitInView)
        r.jump(2+i)
    wait(app)
    for r in readers: r.verticalScrollBar().setValue(r.verticalScrollBar().value()+40)
    saved=[r.state(include_history=True) for r in readers]
    for width,height in [(550,760),(1250,920),(700,850)]:
        w.resize(width,height);wait(app)
        for r,before in zip(readers,saved):
            now=r.state(include_history=True)
            assert now['anchor_page']==before['anchor_page']
            assert abs(now['y']-before['y'])<3
            assert now['past']==before['past'] and now['future']==before['future']
    w.close()


def test_inline_search_keys_counter_focus_switch_and_close(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'inline.db'),restore=False);w.show()
    first=w.open_pdf(pdf);wait(app);w.split(0,0);wait(app)
    second=w.secondary
    second.setFocus()
    QTest.keyClick(second,Qt.Key.Key_F,Qt.KeyboardModifier.ControlModifier)
    assert QApplication.activeModalWidget() is None
    assert w.inline_search.reader is second and w.inline_search.text.hasFocus()
    QTest.keyClicks(w.inline_search.text,'Mellow')
    finish_search(app,second)
    QTest.keyClick(w.inline_search.text,Qt.Key.Key_Return)
    assert w.inline_search.status.text()=='1 of 8'
    w.inline_search.previous.click()
    assert w.inline_search.status.text()=='8 of 8'
    assert first.search.searchString()==''
    first.setFocus();wait(app)
    assert w.inline_search.reader is first and w.inline_search.text.text()==''
    w.inline_search.text.setText('chapter')
    finish_search(app,first)
    second.setFocus();wait(app)
    assert w.inline_search.reader is second and w.inline_search.text.text()=='Mellow'
    w.inline_search.text.setFocus()
    QTest.keyClick(w.inline_search.text,Qt.Key.Key_Escape)
    assert not w._search_open and w.active is second
    assert second.search.searchString()=='Mellow'
    w.close()


def test_inline_search_narrow_fullscreen_home_and_closed_document_cleanup(app,pdf,tmp_path,monkeypatch):
    w=Window(Store(tmp_path/'inline-fullscreen.db'),restore=False);w.show()
    r=w.open_pdf(pdf);wait(app)
    w.fullscreen();wait(app,100)
    original=r.state(include_history=True);size=r.viewport().size()
    QTest.keyClick(r,Qt.Key.Key_F,Qt.KeyboardModifier.ControlModifier)
    wait(app)
    assert w.toolbar.isVisible() and r.viewport().size()==size
    assert r.state(include_history=True)==original
    monkeypatch.setattr(w,'pointer_in_chrome',lambda:False)
    w.hide_chrome()
    assert w.toolbar.isVisible()  # Search editing pauses auto-hide.
    w.inline_search.text.setText('Mellow');finish_search(app,r)
    w.fullscreen();wait(app,100)
    w.resize(500,760);wait(app)
    assert w.inline_search.text.isVisible() and w.inline_search.previous.isVisible() and w.inline_search.next.isVisible()
    assert w.more_button.isVisible()
    w.show_home()
    assert w.inline_search.reader is None
    w.resume_reading();wait(app)
    assert w.inline_search.reader is r and w.inline_search.text.text()=='Mellow'
    w.close_tab(0);wait(app)
    assert w.inline_search.reader is None and not w.inline_search._connections
    w.close()


def test_document_information_uses_focused_source_and_is_read_only(app,technical_pdf,tmp_path,monkeypatch):
    before=hashlib.sha256(technical_pdf.read_bytes()).hexdigest()
    w=Window(Store(tmp_path/'info.db'),restore=False);w.show()
    first=w.open_pdf(technical_pdf);wait(app);w.split(0,0);wait(app)
    w.secondary.jump(1);w.secondary.rotate_by(90);w.focus_reader(w.secondary);wait(app)
    inspected=[]
    def inspect(dialog):
        inspected.append(dialog.fields)
        assert dialog.fields['Current page']=='ii (PDF page 2)'
        assert dialog.fields['Pages']=='5'
        assert '800.0 × 500.0 pt' in dialog.fields['Page size']
        assert dialog.labels['Full path'].textFormat()==Qt.TextFormat.PlainText
        assert dialog.labels['Full path'].textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(DocumentInfoDialog,'exec',inspect)
    w.info_action.trigger()
    assert inspected and inspected[0]['Full path']==str(technical_pdf)
    assert first.pageNavigator().currentPage()==0
    assert hashlib.sha256(technical_pdf.read_bytes()).hexdigest()==before
    original_stat=Path.stat
    def missing(path,*args,**kwargs):
        if str(path)==str(technical_pdf): raise FileNotFoundError()
        return original_stat(path,*args,**kwargs)
    monkeypatch.setattr(Path,'stat',missing)
    assert 'Unavailable' in dict(document_fields(w.secondary))['File size']
    monkeypatch.setattr(Path,'stat',original_stat)
    w.close()


def test_quick_split_menu_uses_focused_view_and_history_pause_matches_settings(app,pdf,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'quick-split.db'),restore=False);w.show()
    first=w.open_pdf(pdf);w.open_pdf(technical_pdf);wait(app)
    opened=[]
    def dismiss_menu():
        opened.append(w.split_menu.isVisible())
        w.split_menu.close()
    QTimer.singleShot(40,dismiss_menu)
    QTest.mouseClick(w.toolbar.widgetForAction(w.split_menu_action),Qt.MouseButton.LeftButton)
    wait(app,60)
    assert opened==[True]
    w.populate_split_choices()
    assert len(w.split_choices.actions())==2
    assert 'independent view' in w.split_choices.actions()[1].text()
    w.split_choices.actions()[0].trigger();wait(app)
    assert w.secondary.path==str(pdf) and w.readers[w.tabs.currentIndex()].path==str(technical_pdf)
    w.focus_reader(w.secondary);w.secondary.jump(4);wait(app)
    w.populate_split_choices();w.split_choices.actions()[0].trigger();wait(app)
    assert w.active.path==str(pdf) and w.active.pageNavigator().currentPage()==4
    assert w.secondary.path==str(pdf) and w.secondary.pageNavigator().currentPage()==4
    w.sync_menu();w.history_pause_action.setChecked(True)
    assert w.store.get('history_paused')
    w.apply_settings({'history_paused':False});w.sync_menu()
    assert not w.history_pause_action.isChecked()
    w.close()
