"""Keyboard return paths, nested dialogs and remappable focus navigation."""
import pytest
from PySide6.QtCore import Qt,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QPushButton,QMenu,QFileDialog
from test_reader import app,pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.locations import LocationsPanel
from mellow.search import SearchPanel
from mellow.pages import PagesPanel
from mellow.tool_dialog import ToolDialog


def focused(app,widget):
    widget.window().activateWindow();widget.setFocus();wait(app,30)
    assert widget.hasFocus()


def test_focus_cycle_split_home_and_remapping_preserve_reading_positions(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'focus-cycle.db'),restore=False);w.show();r=w.open_pdf(pdf);wait(app)
    w.split(0,0);wait(app);other=w.secondary
    r.jump(2);other.jump(5);wait(app)
    before=[pane.state(include_history=True) for pane in (r,other)]
    focused(app,r)
    for target in (other,w.more_button,w.toolbar.widgetForAction(w.home_action),r):
        QTest.keyClick(QApplication.focusWidget(),Qt.Key.Key_F6);wait(app,30)
        assert target.hasFocus()
    assert [pane.state(include_history=True) for pane in (r,other)]==before
    QTest.keyClick(r,Qt.Key.Key_F6,Qt.KeyboardModifier.ShiftModifier)
    assert w.toolbar.widgetForAction(w.home_action).hasFocus()
    w.apply_settings({'shortcuts':{'focus_next':'Ctrl+F6'}})
    focused(app,r)
    QTest.keyClick(r,Qt.Key.Key_F6);assert r.hasFocus()
    QTest.keyClick(r,Qt.Key.Key_F6,Qt.KeyboardModifier.ControlModifier);assert other.hasFocus()
    w.show_home();focused(app,w.home.filter)
    QTest.keyClick(w.home.filter,Qt.Key.Key_F6,Qt.KeyboardModifier.ControlModifier)
    assert w.more_button.hasFocus()
    QTest.keyClick(w.more_button,Qt.Key.Key_F6,Qt.KeyboardModifier.ControlModifier)
    assert w.home.filter.hasFocus()
    w.close()


def test_old_custom_f6_binding_survives_new_focus_defaults(app,tmp_path):
    store=Store(tmp_path/'old-f6.db');store.set('shortcuts',{'favorites':'F6','home':'Ctrl+H'})
    w=Window(store,restore=False)
    assert w.shortcuts.bindings['favorites']=='F6' and w.shortcuts.bindings['home']=='Ctrl+H'
    assert w.shortcuts.bindings['focus_next']=='' and w.shortcuts.bindings['focus_previous']=='Shift+F6'
    assert store.get('shortcuts')['focus_next']==''
    w.close()


@pytest.mark.parametrize('theme',['Light','Sepia','Black','Dark'])
def test_toolbar_keyboard_focus_is_visibly_distinct_in_each_theme(app,pdf,tmp_path,theme):
    w=Window(Store(tmp_path/('focus-paint-'+theme+'.db')),restore=False);w.show();reader=w.open_pdf(pdf)
    w.change_theme(theme);wait(app,60);button=w.toolbar.widgetForAction(w.home_action)
    focused(app,reader);before=button.grab().toImage()
    focused(app,button);after=button.grab().toImage()
    assert before!=after
    w.close()


def test_focus_cycle_uses_visible_pane_order_and_keeps_fullscreen_controls_visible(app,pdf,tmp_path,monkeypatch):
    w=Window(Store(tmp_path/'fullscreen-focus.db'),restore=False);w.show();r=w.open_pdf(pdf);w.split(0,0);wait(app)
    other=w.secondary;w.swap();wait(app)
    # Swapping places the independent secondary pane before the primary.
    focused(app,other);QTest.keyClick(other,Qt.Key.Key_F6);assert r.hasFocus()
    w.fullscreen();wait(app)
    monkeypatch.setattr(w,'pointer_in_chrome',lambda:False)
    focused(app,r);QTest.keyClick(r,Qt.Key.Key_F6);assert w.more_button.hasFocus()
    w.hide_chrome();assert w.toolbar.isVisible() and w.tabstrip.isVisible()
    QTest.keyClick(w.more_button,Qt.Key.Key_F6);assert w.toolbar.widgetForAction(w.home_action).hasFocus()
    w.hide_chrome();assert w.toolbar.isVisible()
    w.close()


def test_search_arrow_access_and_escape_returns_to_same_split_pane(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'focus-search.db'),restore=False);w.show();w.open_pdf(pdf);w.split(0,0);wait(app)
    reader=w.secondary;w.focus_reader(reader);reader.search.setSearchString('Mellow')
    for _ in range(100):
        if reader.search.rowCount()==8:break
        wait(app,20)
    panel=SearchPanel(reader,w);panel.show();wait(app,30);focused(app,panel.text)
    QTest.keyClick(panel.text,Qt.Key.Key_Down);assert panel.results.hasFocus() and panel.results.currentIndex().row()==0
    QTest.keyClick(panel.results,Qt.Key.Key_Up);assert panel.text.hasFocus()
    QTest.keyClick(panel.whole_words,Qt.Key.Key_Escape);wait(app,30)
    assert not panel.isVisible() and reader.hasFocus() and w.active is reader
    assert reader.search.searchString()=='Mellow'
    panel.deleteLater();w.close()


@pytest.mark.parametrize('kind',['favorite','bookmark'])
def test_escape_from_editor_buttons_cancels_edit_before_closing_panel(app,pdf,tmp_path,kind):
    w=Window(Store(tmp_path/(kind+'.db')),restore=False);w.show();reader=w.open_pdf(pdf);wait(app)
    panel=LocationsPanel(w,kind);panel.show();wait(app,30);panel.add_current()
    save=next(b for b in panel.editor.findChildren(QPushButton) if b.text()=='Save')
    focused(app,save);QTest.keyClick(save,Qt.Key.Key_Escape);wait(app,30)
    assert panel.isVisible() and not panel.editor.isVisible() and panel.search.hasFocus()
    assert not w.store.locations(kind)
    QTest.keyClick(panel.add_button,Qt.Key.Key_Escape);wait(app,30)
    assert not panel.isVisible() and reader.hasFocus()
    panel.deleteLater();w.close()


def test_saved_page_menu_escape_leaves_panel_and_selection_intact(app,pdf,tmp_path):
    store=Store(tmp_path/'context-focus.db');store.add('favorite',str(pdf),1,'Saved page')
    w=Window(store,restore=False);w.show();w.open_pdf(pdf);wait(app)
    panel=LocationsPanel(w,'favorite');panel.show();wait(app,30);focused(app,panel.listing)
    menus=[]
    def dismiss_menu():
        menu=QApplication.activePopupWidget()
        if isinstance(menu,QMenu):menus.append(menu);QTest.keyClick(menu,Qt.Key.Key_Escape)
        else:QTimer.singleShot(10,dismiss_menu)
    QTimer.singleShot(20,dismiss_menu)
    QTest.keyClick(panel.listing,Qt.Key.Key_F10,Qt.KeyboardModifier.ShiftModifier)
    assert menus and panel.isVisible() and panel.selected()['title']=='Saved page'
    panel.reject();panel.deleteLater();w.close()


def test_nested_file_dialog_owns_escape_and_page_panel_returns_focus(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'nested-focus.db'),restore=False);w.show();reader=w.open_pdf(pdf);wait(app)
    panel=LocationsPanel(w,'favorite');panel.show();wait(app,30)
    chooser=QFileDialog(panel);chooser.setOption(QFileDialog.Option.DontUseNativeDialog)
    chooser.setWindowModality(Qt.WindowModality.ApplicationModal);chooser.show();wait(app,30)
    QTest.keyClick(chooser,Qt.Key.Key_Escape);wait(app,30)
    assert not chooser.isVisible() and panel.isVisible()
    chooser.deleteLater();panel.reject();panel.deleteLater()
    pages=PagesPanel(reader,w);pages.show();wait(app,30)
    QTest.keyClick(pages.grid,Qt.Key.Key_Escape);wait(app,30)
    assert not pages.isVisible() and reader.hasFocus()
    pages.deleteLater();w.close()


def test_extract_range_enter_updates_preview_without_opening_file_picker(app,pdf,tmp_path,monkeypatch):
    w=Window(Store(tmp_path/'tool-focus.db'),restore=False);w.show()
    dialog=ToolDialog('extract',w,[str(pdf)]);dialog.show();opened=[]
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *_:opened.append(True) or ('',''))
    focused(app,dialog.ranges);dialog.ranges.setText('2-3');QTest.keyClick(dialog.ranges,Qt.Key.Key_Return)
    for _ in range(200):
        if dialog.current_output:break
        wait(app,20)
    assert not opened and dialog.document.pageCount()==2
    assert dialog.fit.accessibleName() and dialog.view.accessibleName()
    dialog.reject();dialog.deleteLater();w.close()
