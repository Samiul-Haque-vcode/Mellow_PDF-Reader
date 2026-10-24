"""Section-local drafts, real fullscreen timing and responsive reader controls."""
import pytest
from PySide6.QtCore import Qt,QPoint
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QDialogButtonBox
from PySide6.QtPdfWidgets import QPdfView
from test_reader import app,pdf,technical_pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.settings import SettingsDialog
from mellow.config import fullscreen_hide_delay


def test_settings_sections_drafts_and_resets_are_independent(app,tmp_path):
    store=Store(tmp_path/'drafts.db')
    d=SettingsDialog(store)
    assert [d.tabs.tabText(i) for i in range(d.tabs.count())]==['General','Reading','Appearance','Shortcuts']
    assert d.tabs.widget(2).isAncestorOf(d.hide_delay)
    assert d.tabs.widget(2).isAncestorOf(d.preview)
    assert d.tabs.widget(2).isAncestorOf(d.caption_tabs)
    assert d.tabs.widget(1).isAncestorOf(d.speed)
    save=d.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert not save.isEnabled() and not d.dirty_note.text()
    d.theme.setCurrentText('Dark');d.warmth.setValue(12)
    d.labels.setChecked(True);d.hide_delay.setValue(1200);d.height.setValue(45)
    d.auto_scroll_speed.setValue(70)
    d.shortcut_edits['home'].setKeySequence(QKeySequence('Ctrl+H'))
    assert save.isEnabled() and d.dirty_note.text()=='Unsaved changes'
    d.reset_buttons['reading'].click()
    assert d.auto_scroll_speed.value()==24 and d.height.value()==28
    assert d.theme.currentText()=='Dark' and d.warmth.value()==12
    assert d.hide_delay.value()==1200 and d.labels.isChecked()
    d.startup.setCurrentIndex(1)
    d.reset_buttons['general'].click()
    assert d.startup.currentIndex()==0 and d.record_history.isChecked()
    assert d.hide_delay.value()==1200 and d.labels.isChecked()
    d.reset_buttons['appearance'].click()
    assert d.theme.currentText()=='Sepia' and d.warmth.value()==0 and not d.labels.isChecked()
    assert d.shortcut_values()['home']=='Ctrl+H'
    d.reset_buttons['shortcuts'].click()
    assert not save.isEnabled() and not d.dirty_note.text()
    d.autohide.setChecked(False);assert not d.hide_delay.isEnabled()
    d.reject()
    assert store.get('fullscreen_hide_delay') is None and store.get('theme') is None


def test_settings_saved_hide_delay_and_conflict_section(app,pdf,tmp_path):
    store=Store(tmp_path/'delay.db');w=Window(store,restore=False);w.show();w.open_pdf(pdf);wait(app)
    d=SettingsDialog(store,w);d.hide_delay.setValue(1100)
    assert w.chrome_timer.interval()==600 and store.get('fullscreen_hide_delay') is None
    d.shortcut_edits['home'].setKeySequence(QKeySequence('Ctrl+O'))
    d.accept()
    assert d.tabs.currentWidget() is d.shortcuts_page and d.error.text()
    d.reset_shortcuts();d.accept();w.apply_settings(d.values())
    assert w.chrome_timer.interval()==1100 and store.get('fullscreen_hide_delay')==1100
    reopened=SettingsDialog(store,w)
    assert reopened.hide_delay.value()==1100 and not reopened.dirty_note.text()
    reopened.reject();w.close()


@pytest.mark.parametrize('value,expected',[(None,600),('bad',600),(True,600),(-1,200),(99999,5000),('900',900)])
def test_hide_delay_storage_validation(value,expected):
    assert fullscreen_hide_delay(value)==expected


def test_fullscreen_hide_delay_affects_actual_timer(app,pdf,tmp_path,monkeypatch):
    w=Window(Store(tmp_path/'timer.db'),restore=False);w.show();r=w.open_pdf(pdf);wait(app)
    monkeypatch.setattr(w,'pointer_in_chrome',lambda:False)
    monkeypatch.setattr(w,'editing_chrome',lambda:False)
    w.apply_settings({'fullscreen_hide_delay':1100})
    w.fullscreen();wait(app,60);r.setFocus();w.show_chrome()
    assert w.chrome_timer.isActive() and w.chrome_timer.interval()==1100
    wait(app,250);assert w.toolbar.isVisible()
    w.apply_settings({'fullscreen_hide_delay':200});w.show_chrome()
    wait(app,330);assert not w.toolbar.isVisible()
    w.fullscreen();wait(app,60);assert w.toolbar.isVisible()
    w.close()


def test_home_tools_resize_and_existing_workspaces(app,tmp_path):
    w=Window(Store(tmp_path/'home.db'),restore=False);w.show();w.resize(1080,760);wait(app)
    h=w.home
    assert h.opened.objectName()=='primary' and h.empty.text()=='Open a PDF to begin.'
    assert len({b.width() for b in h.tools.values()})==1
    assert {b.height() for b in h.tools.values()}=={52}
    assert len({b.mapTo(h,QPoint()).y() for b in h.tools.values()})==1
    opened=[];h.toolRequested.connect(opened.append)
    # Observe real routing without entering the existing modal tool workspace.
    h.toolRequested.disconnect(w.home_tool)
    for key,button in h.tools.items():
        button.click();assert opened[-1]==key
    w.resize(480,760);wait(app)
    assert len({b.mapTo(h,QPoint()).y() for b in h.tools.values()})==3
    for b in h.tools.values():assert b.width()>250
    w.resize(1080,760);wait(app)
    assert len({b.width() for b in h.tools.values()})==1
    w.close()


def test_focused_pane_zoom_menu_and_narrow_controls(app,pdf,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'toolbar.db'),restore=False);w.show()
    first=w.open_pdf(pdf);w.open_pdf(technical_pdf);w.split(0,1);wait(app)
    w.focus_reader(first);first.setZoomMode(QPdfView.ZoomMode.FitToWidth);w.sync();wait(app)
    assert w.fit.currentText()=='Fit Width' and w.fit_actions['Fit Width'].isChecked()
    second=w.secondary;w.focus_reader(second);second.zoom_to(1.25);wait(app);w.sync()
    assert w.fit.currentText()=='125%' and not any(a.isChecked() for a in w.fit_actions.values())
    w.fit_actions['Actual Size'].trigger();wait(app);w.sync()
    assert abs(second.zoomFactor()-1)<.001 and w.fit_actions['Actual Size'].isChecked()
    w.fit_actions['Actual Size'].trigger();wait(app)
    assert w.fit_actions['Actual Size'].isChecked()
    assert first.zoomMode()==QPdfView.ZoomMode.FitToWidth
    w.resize(440,760);wait(app)
    assert w.toolbar.height()==32 and w.toolbar.collapsed and w.toolbar.toolTip().startswith('In Menu:')
    assert w.page.isVisible() and w.inline_search.text.isVisible()
    assert 'PDF pages' in w.page.accessibleName() and 'Zoom:' in w.fit.accessibleName()
    w.close()
