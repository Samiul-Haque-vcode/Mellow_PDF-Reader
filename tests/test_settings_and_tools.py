"""Real output previews, configurable shortcuts and metadata-only Home actions."""
import hashlib
from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication,QDialog,QToolButton
from PySide6.QtTest import QTest
from pypdf import PdfReader
from PIL import Image
from test_reader import app,pdf,technical_pdf,wait
from mellow.app import Window
from mellow.settings import SettingsDialog
from mellow.storage import Store
from mellow.tool_dialog import ToolDialog
from mellow.shortcuts import validate
from mellow import utilities


def settle(app,dialog):
    for _ in range(300):
        wait(app,20)
        if not dialog._job and not dialog.timer.isActive() and not dialog._pending: return
    pytest.fail('PDF preview worker did not settle')


def test_shortcut_conflicts_cancel_reset_and_persistence(app,pdf,tmp_path):
    store=Store(tmp_path/'keys.db')
    w=Window(store,restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    dialog=SettingsDialog(store,w)
    dialog.shortcut_edits['home'].setKeySequence(QKeySequence('Ctrl+O'))
    dialog.accept()
    assert dialog.result()!=QDialog.DialogCode.Accepted
    assert 'assigned to both' in dialog.error.text()
    assert store.get('shortcuts') is None
    dialog.reset_shortcuts()
    assert dialog.shortcut_values()['home']=='Alt+Home'
    dialog.shortcut_edits['home'].setKeySequence(QKeySequence('Ctrl+H'))
    dialog.shortcut_edits['copy'].setKeySequence(QKeySequence('Ctrl+Shift+C'))
    dialog.shortcut_edits['next'].clear()
    dialog.labels.setChecked(True)
    dialog.accept()
    assert dialog.result()==QDialog.DialogCode.Accepted
    w.apply_settings(dialog.values())
    assert w.home_action.shortcut().toString()=='Ctrl+H'
    assert w.toolbar.toolButtonStyle()==Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    assert not hasattr(w.home,'hint')  # shortcut hints belong in Settings/tooltips
    assert 'Ctrl+H' in w.home_action.toolTip()
    r.select_page_text(0)
    r.setFocus()
    QTest.keyClick(r,Qt.Key.Key_C,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier)
    assert 'Mellow chapter 1' in QApplication.clipboard().text()
    # Newly created independent panes inherit the changed copy key.
    w.split(0,0)
    assert w.secondary.copy_action.shortcut().toString()=='Ctrl+Shift+C'
    r.setFocus()
    QTest.keyClick(r,Qt.Key.Key_H,Qt.KeyboardModifier.ControlModifier)
    assert w._on_home
    w.close()
    w=Window(store,restore=False)
    assert w.home_action.shortcut().toString()=='Ctrl+H'
    assert w.shortcuts.bindings['next']==''
    w.close()


@pytest.mark.parametrize('key,value',[('open','Ctrl+V'),('home','Esc'),('search','A'),('open','Ctrl+C')])
def test_reserved_shortcuts_are_rejected(key,value):
    with pytest.raises(ValueError): validate({key:value})


def test_cancelled_settings_and_invalid_apply_leave_store_unchanged(app,tmp_path):
    w=Window(Store(tmp_path/'cancel-keys.db'),restore=False)
    dialog=SettingsDialog(w.store,w)
    dialog.shortcut_edits['home'].setKeySequence(QKeySequence('Ctrl+H'))
    dialog.reject()
    assert w.home_action.shortcut().toString()=='Alt+Home'
    with pytest.raises(ValueError): w.apply_settings({'theme':'Dark','shortcuts':{'home':'Ctrl+O'}})
    assert w.theme_name=='Sepia' and w.store.get('theme')=='Sepia'
    dialog.filter.setText('pane')
    assert dialog.shortcut_edits['swap'].isHidden() is False
    assert dialog.shortcut_edits['open'].isHidden()
    w.close()


def test_split_toolbar_tracks_focused_pane_and_disables_commands(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'panel.db'),restore=False)
    w.show()
    w.open_pdf(pdf)
    wait(app)
    assert all(not action.isEnabled() for action in w.split_actions)
    w.split(0,0)
    wait(app)
    assert all(action.isEnabled() for action in w.split_actions)
    w.focus_reader(w.secondary)
    assert w.pane_indicator.text()=='Right pane'
    w.swap()
    assert w.pane_indicator.text()=='Left pane'
    w.orientation()
    wait(app)
    assert w.pane_indicator.text()=='Top pane'
    w.exit_split()
    assert not w.pane_indicator.isVisible()
    assert all(not action.isEnabled() for action in w.split_actions)
    w.close()


def test_extract_preview_invalid_ranges_and_exact_saved_output(app,pdf,tmp_path):
    original=hashlib.sha256(Path(pdf).read_bytes()).hexdigest()
    d=ToolDialog('extract',paths=[str(pdf)])
    d.show()
    d.ranges.setText('2-3,7')
    settle(app,d)
    assert d.document.pageCount()==3
    assert 'chapter 2' in d.document.getAllText(0).text()
    assert 'chapter 7' in d.document.getAllText(2).text()
    d.page.setValue(3)
    assert d.view.pageNavigator().currentPage()==2
    d.ranges.setText('100-102')
    assert not d.save_button.isEnabled()
    settle(app,d)
    assert d.current_output is None and 'Preview failed:' in d.status.text()
    d.ranges.setText('2-3')
    settle(app,d)
    expected=Path(d.current_output).read_bytes()
    assert not d.save_to(pdf)
    output=tmp_path/'extract-output.pdf'
    assert d.save_to(output)
    settle(app,d)
    assert d.saved_path==str(output) and d._disposed
    assert output.read_bytes()==expected
    assert hashlib.sha256(Path(pdf).read_bytes()).hexdigest()==original
    assert len(PdfReader(output).pages)==2


def test_merge_preview_reorder_remove_and_cleanup(app,pdf,technical_pdf,tmp_path):
    d=ToolDialog('merge',paths=[str(pdf),str(technical_pdf)])
    d.show()
    settle(app,d)
    assert d.document.pageCount()==13
    assert 'chapter 1' in d.document.getAllText(0).text()
    d.listing.setCurrentRow(1)
    d.move(-1)
    settle(app,d)
    assert d.paths()[0]==str(technical_pdf)
    assert 'chapter 1' not in d.document.getAllText(0).text()
    assert 'chapter 1' in d.document.getAllText(5).text()
    assert len(list(Path(d._temp.name).glob('preview-*.pdf')))==1
    d.remove_selected()
    settle(app,d)
    assert d.document.pageCount()==8
    root=d._temp.name
    assert d.preview_file.isOpen()
    d.reject()
    assert not d.preview_file.isOpen()
    assert d.view.document() is None
    assert not Path(root).exists()


def test_images_preview_size_order_and_failed_input(app,tmp_path):
    paths=[]
    for name,color in [('red','red'),('blue','blue')]:
        path=tmp_path/(name+'.png')
        Image.new('RGB',(180,100),color).save(path)
        paths.append(str(path))
    d=ToolDialog('images',paths=paths)
    d.show()
    settle(app,d)
    assert d.document.pageCount()==2
    first=d.document.render(0,d.view.viewport().size())
    assert first.pixelColor(first.width()//2,first.height()//2).red()>200
    d.listing.setCurrentRow(1)
    d.move(-1)
    d.size.setCurrentText('Letter')
    settle(app,d)
    assert round(d.document.pagePointSize(0).width())==612
    first=d.document.render(0,d.view.viewport().size())
    assert first.pixelColor(first.width()//2,first.height()//2).blue()>200
    d.add_paths([str(tmp_path/'missing.png')])
    settle(app,d)
    assert not d.save_button.isEnabled() and 'Cannot read image' in d.status.text()
    d.reject()


def test_cancel_in_flight_and_stale_preview_requests(app,pdf,tmp_path,monkeypatch):
    from threading import Event
    started=Event()
    original=utilities.extract
    def slow_extract(source,output,ranges,cancel,progress):
        started.set()
        cancel.wait(.12)
        utilities.check_cancel(cancel)
        original(source,output,ranges,cancel,progress)
    monkeypatch.setattr(utilities,'extract',slow_extract)
    d=ToolDialog('extract',paths=[str(pdf)])
    d.timer.stop()
    d.build_preview()
    assert started.wait(1)
    d.ranges.setText('5-6')
    settle(app,d)
    assert d.document.pageCount()==2 and 'chapter 5' in d.document.getAllText(0).text()
    d.ranges.setText('2-4')
    d.timer.stop()
    d.build_preview()
    root=d._temp.name
    d.reject()
    settle(app,d)
    assert d._disposed and not Path(root).exists()


def test_home_sort_empty_filter_and_remove_never_deletes_pdf(app,pdf,technical_pdf,tmp_path):
    store=Store(tmp_path/'home-refined.db')
    store.record_history(pdf,2)
    store.record_history(technical_pdf,3)
    store.add('favorite',str(pdf),2,'Saved page')
    w=Window(store,restore=False)
    w.show()
    w.show_home()
    w.home.sort.setCurrentIndex(1)
    texts=[w.home.listing.item(i).text().casefold() for i in range(w.home.listing.count())]
    assert texts==sorted(texts)
    w.home.filter.setText('no-such-title')
    assert w.home.empty.isVisible() and 'No recent PDFs match' in w.home.empty.text()
    assert w.home.recent_count.text()=='0 / 2'
    w.remove_recent(str(pdf))
    assert Path(pdf).exists() and store.recent(pdf) is None
    assert len(store.locations('favorite'))==1 and w.home.listing.count()==1
    w.home.filter.clear()
    assert w.home.recent_count.text()=='1'
    w.close()


def test_parent_close_waits_for_utility_cancellation(app,pdf,tmp_path,monkeypatch):
    from threading import Event
    started=Event()
    def slow_extract(source,output,ranges,cancel,progress):
        started.set()
        cancel.wait(1)
        utilities.check_cancel(cancel)
    monkeypatch.setattr(utilities,'extract',slow_extract)
    w=Window(Store(tmp_path/'close-worker.db'),restore=False)
    w.show()
    d=ToolDialog('extract',w,[str(pdf)])
    d.show()
    d.timer.stop()
    d.build_preview()
    assert started.wait(1)
    w.close()
    assert w.isVisible()  # Do not destroy a QThread that is still running.
    settle(app,d)
    assert d._disposed
    w.close()
    assert not w.isVisible()


def test_failed_save_can_retry_without_losing_preview(app,pdf,tmp_path):
    d=ToolDialog('extract',paths=[str(pdf)])
    d.show()
    settle(app,d)
    preview=d.current_output
    assert d.save_to(tmp_path/'missing-folder'/'result.pdf')
    settle(app,d)
    assert 'Save failed:' in d.status.text()
    assert not d._disposed and d.current_output==preview
    assert d.save_button.isEnabled() and d.inputs.isEnabled()
    result=tmp_path/'recovered.pdf'
    assert d.save_to(result)
    settle(app,d)
    assert result.exists() and d._disposed
