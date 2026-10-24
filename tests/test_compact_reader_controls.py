"""Requested compact reader controls use real PDFs and shared pane actions."""
from pathlib import Path
import pytest
from PySide6.QtCore import Qt,QModelIndex,QTimer,QPoint
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest,QSignalSpy
from test_reader import app,pdf,wait
from mellow.app import Window
from mellow.storage import Store


def found(app,reader):
    for _ in range(80):
        if reader.search.rowCount(QModelIndex())==8:return
        wait(app,20)
    pytest.fail('PDF matches did not arrive')


def test_more_menu_is_once_at_left_of_tabs_and_available_on_home(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'menu.db'),restore=False);w.show();w.open_pdf(pdf);wait(app)
    assert w.more_button.parentWidget() is w.tabstrip
    assert w.tabstrip.layout().itemAt(0).widget() is w.brand_mark
    assert w.tabstrip.layout().itemAt(1).widget() is w.more_button
    assert w.more_button.defaultAction() is w.more_action
    assert w.more_button.menu() is w.more_menu
    assert 'more' not in w.toolbar.entries and 'search' not in w.toolbar.entries
    w.show_home();wait(app)
    assert w.more_button.isVisible() and not w.toolbar.isVisible()
    shown=QSignalSpy(w.more_menu.aboutToShow)
    QTimer.singleShot(30,w.more_menu.close)
    QTest.mouseClick(w.more_button,Qt.MouseButton.LeftButton)
    wait(app,10)
    assert shown.count()==1
    w.close()


def test_rotation_buttons_share_shortcuts_and_only_rotate_focused_pane(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'rotate.db'),restore=False);w.resize(1500,850);w.show()
    first=w.open_pdf(pdf);wait(app);w.split(0,0);wait(app)
    second=w.secondary;w.focus_reader(second)
    before=first.state(include_history=True)
    left,right=w.rotation_actions
    for action in (left,right):
        assert action not in w.reading_menu.actions() and not action.icon().isNull()
        assert w.toolbar.widgetForAction(action).isVisible()
    w.toolbar.widgetForAction(left).click();wait(app)
    assert second.rotation==270 and first.state(include_history=True)==before
    w.toolbar.widgetForAction(right).click();wait(app)
    assert second.rotation==0 and first.rotation==0
    w.apply_settings({'shortcuts':{'rotate_right':'Alt+R'}})
    second.setFocus();QTest.keyClick(second,Qt.Key.Key_R,Qt.KeyboardModifier.AltModifier);wait(app)
    assert second.rotation==90 and first.rotation==0
    w.show_home()
    assert not left.isEnabled() and not right.isEnabled()
    w.close()


def test_find_is_persistent_with_next_previous_and_independent_split_queries(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'find.db'),restore=False);w.show();first=w.open_pdf(pdf);wait(app)
    assert w.inline_search.text.isVisible() and not w._search_open
    size=first.viewport().size()
    QTest.mouseClick(w.inline_search.text,Qt.MouseButton.LeftButton)
    QTest.keyClicks(w.inline_search.text,'Mellow');found(app,first)
    assert w._search_open and first.viewport().size()==size
    QTest.keyClick(w.inline_search.text,Qt.Key.Key_Return)
    assert w.inline_search.status.text()=='1 of 8'
    QTest.keyClick(w.inline_search.text,Qt.Key.Key_Return,Qt.KeyboardModifier.ShiftModifier)
    assert w.inline_search.status.text()=='8 of 8'
    w.inline_search.next.click();assert w.inline_search.status.text()=='1 of 8'
    QTest.keyClick(w.inline_search.text,Qt.Key.Key_Escape)
    assert w.inline_search.text.isVisible() and first.hasFocus() and not w._search_open
    assert first.search.searchString()=='Mellow'
    w.split(0,0);wait(app);second=w.secondary;second.setFocus();wait(app)
    assert w.inline_search.reader is second and w.inline_search.text.text()==''
    w.inline_search.text.setText('Equation');found(app,second)
    w.inline_search.next.click();assert second.currentSearchResultIndex()==0
    first.setFocus();wait(app)
    assert w.inline_search.text.text()=='Mellow' and first.currentSearchResultIndex()==0
    assert second.search.searchString()=='Equation'
    w.close()


@pytest.mark.parametrize('labels',[False,True])
@pytest.mark.parametrize('width',[440,560,900,1280])
def test_find_and_page_controls_fit_without_second_row(app,pdf,tmp_path,labels,width):
    w=Window(Store(tmp_path/'fit.db'),restore=False);w.show();r=w.open_pdf(pdf);wait(app)
    w.apply_settings({'toolbar_labels':labels});w.resize(width,760);wait(app)
    for widget in (w.inline_search.text,w.inline_search.previous,w.inline_search.next,w.inline_search.results,w.page,w.more_button):
        assert widget.isVisible()
    find=w.inline_search
    def assert_controls_fit():
        details=dict(width=w.toolbar.width(),find=find.geometry().getRect(),compact=find._compact,
                     minimum=find.minimumWidth(),hint=find.sizeHint().width(),collapsed=sorted(w.toolbar.collapsed))
        assert find.geometry().right()<=w.toolbar.width(),details
        for control in (find.text,find.previous,find.next,find.results,w.page):
            left=control.mapTo(w.toolbar,QPoint()).x()
            assert 0<=left and left+control.width()<=w.toolbar.width(),details
        for control in (find.text,find.previous,find.next,find.results,w.page,*w.toolbar.buttons.values()):
            if not control.isVisible():continue
            top=control.mapTo(w.toolbar,QPoint()).y()
            assert 0<=top and top+control.height()<=w.toolbar.height(),details
    assert_controls_fit()
    assert w.toolbar.height()==32
    w.search_dialog(initial='Mellow');found(app,r);wait(app)
    assert find.text.isVisible() and w.page.isVisible()
    assert_controls_fit()
    w.close()


def test_caption_tabs_default_and_explicit_standard_caption_choice(app,tmp_path,monkeypatch):
    from mellow import caption
    from mellow.settings import SettingsDialog
    monkeypatch.setattr(caption,'supported',lambda:True)
    scheme=app.styleHints().colorScheme()
    store=Store(tmp_path/'caption-default.db')
    w=Window(store,restore=False);w.show();wait(app)
    assert w.caption_tabs.enabled and store.get('caption_tabs') is None
    dialog=SettingsDialog(store);assert dialog.caption_tabs.isChecked()
    dialog.caption_tabs.setChecked(False)
    w.apply_settings(dialog.values());w.close()
    reopened=Window(store,restore=False);reopened.show();wait(app)
    assert not reopened.caption_tabs.enabled
    reopened.close();app.styleHints().setColorScheme(scheme)
