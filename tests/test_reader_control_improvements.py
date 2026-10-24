"""Real click behavior for dismissible dialogs, thumbnails and toolbar scrolling."""
import pytest
from PySide6.QtCore import Qt,QTimer,QSize
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog,QComboBox,QApplication,QLineEdit,QWidget
from test_reader import app,pdf,technical_pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.dialogs import DismissibleDialog
from mellow.settings import SettingsDialog
from mellow.document_info import DocumentInfoDialog
from mellow.about import AboutDialog
from mellow.page_preferences import MarginsDialog,NumberingDialog
from mellow.tool_dialog import ToolDialog
from mellow.pages import PagesPanel
from test_page_thumbnails_and_arrangement import thumbnails_ready


def opened(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'controls.db'),restore=False);w.resize(1600,800);w.show()
    r=w.open_pdf(pdf);wait(app,50)
    return w,r


@pytest.mark.parametrize('kind',['settings','information','about','margins','numbering','tools','pages'])
def test_menu_dialog_outside_click_cancels_and_releases(app,pdf,tmp_path,kind):
    w,r=opened(app,pdf,tmp_path)
    constructors={'settings':lambda:SettingsDialog(w.store,w),'information':lambda:DocumentInfoDialog(r,w),
        'about':lambda:AboutDialog(w),'margins':lambda:MarginsDialog(r,w),
        'numbering':lambda:NumberingDialog(r,w),'tools':lambda:ToolDialog('extract',w,[str(pdf)]),
        'pages':lambda:PagesPanel(r,w)}
    d=constructors[kind]();d.show();wait(app,30)
    if kind=='settings':d.auto_scroll_speed.setValue(95)
    # A click on the header outside the dialog dismisses without opening Home.
    QWidget.move(d,w.mapToGlobal(w.rect().center()))
    QTest.mouseClick(w.toolbar.widgetForAction(w.home_action),Qt.MouseButton.LeftButton)
    wait(app,30)
    assert not d.isVisible() and d.result()==QDialog.DialogCode.Rejected
    assert not w._on_home and not d._outside_filter
    if kind=='settings':assert w.auto_scroll.speed==24 and w.store.get('auto_scroll_speed',24)==24
    if kind=='pages':assert d.grid.released and not d.grid.pending
    if kind=='tools':assert d._disposed
    d.deleteLater();w.close()


def test_exec_receives_outside_click_without_blocking_parent(app,pdf,tmp_path):
    w,r=opened(app,pdf,tmp_path)
    d=DocumentInfoDialog(r,w)
    def outside():
        assert QApplication.activeModalWidget() is None
        QWidget.move(d,w.mapToGlobal(w.rect().center()))
        QTest.mouseClick(w.toolbar.widgetForAction(w.home_action),Qt.MouseButton.LeftButton)
    QTimer.singleShot(40,outside)
    assert d.exec()==QDialog.DialogCode.Rejected
    assert not w._on_home and not d._outside_filter
    d.deleteLater();w.close()


def test_child_picker_and_combo_do_not_dismiss_parent(app,pdf,tmp_path):
    w,r=opened(app,pdf,tmp_path)
    d=SettingsDialog(w.store,w);d.show();wait(app,20)
    child=QDialog(d);child.setWindowModality(Qt.WindowModality.WindowModal)
    edit=QLineEdit(child);child.move(d.frameGeometry().bottomRight());child.show();wait(app,20)
    QTest.mouseClick(edit,Qt.MouseButton.LeftButton)
    assert d.isVisible() and child.isVisible()
    child.reject();wait(app,20)
    combo=d.findChild(QComboBox);combo.showPopup();wait(app,20)
    popup=combo.view();QTest.mouseClick(popup.viewport(),Qt.MouseButton.LeftButton,pos=popup.visualRect(popup.model().index(0,0)).center())
    assert d.isVisible()
    d.reject();child.deleteLater();d.deleteLater();w.close()


def test_toolbar_auto_scroll_can_start_pause_and_target_focused_split(app,pdf,tmp_path):
    w,r=opened(app,pdf,tmp_path)
    r.setZoomFactor(1.5);wait(app,30)
    button=w.toolbar.widgetForAction(w.auto_scroll_action)
    assert button.isVisible() and not button.icon().isNull()
    QTest.mouseClick(button,Qt.MouseButton.LeftButton)
    assert w.auto_scroll.running and button.isChecked() and button.accessibleName()=='Pause auto-scroll'
    QTest.mouseClick(button,Qt.MouseButton.LeftButton)
    assert not w.auto_scroll.running and not button.isChecked()
    w.split(0,0);wait(app,40);w.focus_reader(w.secondary)
    before=r.state(include_history=True)
    QTest.mouseClick(button,Qt.MouseButton.LeftButton)
    assert w.auto_scroll.reader is w.secondary and w.auto_scroll.running
    assert r.state(include_history=True)==before
    w.toolbar.resize(440,w.toolbar.height());w.toolbar.reflow()
    assert 'auto_scroll' in w.toolbar.collapsed and w.auto_scroll_action.isEnabled()
    w.auto_scroll_action.trigger();assert not w.auto_scroll.running
    w.close()


def test_thumbnail_resize_jump_and_current_indicator_preserve_reader_until_open(app,technical_pdf,tmp_path):
    w,r=opened(app,technical_pdf,tmp_path);r.jump(2);wait(app,40)
    before=r.state(include_history=True)
    d=PagesPanel(r,w);d.show();thumbnails_ready(app,d.grid)
    assert d.page_number.value()==3 and 'Current' in d.grid.pages.index(2,0).data()
    old=max(image.width() for image in d.grid.cache.values())
    d.thumbnail_size.setCurrentText('Large');wait(app,30);thumbnails_ready(app,d.grid)
    assert d.grid.gridSize()==QSize(216,282)
    assert max(image.width() for image in d.grid.cache.values())>old
    assert len(d.grid.pending)<=2
    d.page_number.setValue(5);wait(app,20)
    assert d.grid.currentIndex().row()==4 and r.state(include_history=True)==before
    QTest.keyClick(d.page_number.lineEdit(),Qt.Key.Key_Return);wait(app,30)
    assert r.pageNavigator().currentPage()==4 and not d.isVisible() and d.grid.released
    r.back();wait(app,30);assert r.pageNavigator().currentPage()==2
    d.deleteLater();w.close()


@pytest.mark.parametrize('mode',['text','int','double'])
def test_small_input_prompt_outside_cancel_and_accept(app,pdf,tmp_path,mode):
    from mellow.dialogs import DismissibleInputDialog
    w,r=opened(app,pdf,tmp_path)
    def call():
        if mode=='text':return DismissibleInputDialog.getText(w,'Test prompt','Value:',text='#4')
        if mode=='int':return DismissibleInputDialog.getInt(w,'Test prompt','Value:',4,1,8)
        return DismissibleInputDialog.getDouble(w,'Test prompt','Value:',175,10,800,1)
    def dismiss():
        dialog=next(d for d in w.findChildren(DismissibleInputDialog) if d.isVisible())
        QWidget.move(dialog,w.mapToGlobal(w.rect().center()))
        QTest.mouseClick(w.toolbar.widgetForAction(w.home_action),Qt.MouseButton.LeftButton)
    QTimer.singleShot(30,dismiss)
    value,accepted=call();assert not accepted and not w._on_home
    def accept():
        dialog=next(d for d in w.findChildren(DismissibleInputDialog) if d.isVisible())
        dialog.accept()
    QTimer.singleShot(30,accept)
    value,accepted=call()
    assert accepted and value=={'text':'#4','int':4,'double':175}[mode]
    w.close()


def test_main_window_modal_error_keeps_pending_settings(app,pdf,tmp_path):
    w,r=opened(app,pdf,tmp_path)
    d=SettingsDialog(w.store,w);d.show();wait(app,20)
    d.auto_scroll_speed.setValue(95)
    error=QDialog(w);error.setWindowModality(Qt.WindowModality.ApplicationModal)
    edit=QLineEdit(error);error.move(d.frameGeometry().bottomRight());error.show();wait(app,20)
    QTest.mouseClick(edit,Qt.MouseButton.LeftButton)
    assert d.isVisible() and d.auto_scroll_speed.value()==95
    error.reject();wait(app,20)
    assert d.isVisible()
    d.reject();error.deleteLater();d.deleteLater();w.close()
