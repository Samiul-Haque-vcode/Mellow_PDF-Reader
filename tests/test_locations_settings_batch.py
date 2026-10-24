"""Real saved destinations, native outlines, transient panels and local preferences."""
import json
import sqlite3
import pytest
from pathlib import Path
from PySide6.QtCore import Qt,QPoint,QPointF,QModelIndex,QTimer
from PySide6.QtGui import QColor,QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QFileDialog,QDialog
from test_reader import app,pdf,technical_pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.settings import SettingsDialog
from mellow.locations import LocationsPanel
from mellow.home import GROUP_ROLE,page_details
from mellow.theme import COLORS


@pytest.mark.parametrize('kind',['bookmark','favorite'])
def test_saved_panel_inline_add_row_actions_and_outside_dismiss(app,pdf,tmp_path,kind):
    store=Store(tmp_path/(kind+'.db'))
    store.add(kind,pdf,1,'First saved page')
    store.add(kind,pdf,2,'Second saved page')
    w=Window(store,restore=False);w.show();r=w.open_pdf(pdf);wait(app)
    panel=LocationsPanel(w,kind);panel.position_near(w.more_button);panel.show();wait(app)
    if panel.tabs:panel.tabs.setCurrentIndex(1)
    assert not panel.isModal() and not hasattr(panel,'more')
    assert panel.add_button.mapTo(panel,QPoint()).x()>panel.search.mapTo(panel,QPoint()).x()
    assert abs(panel.add_button.mapTo(panel,panel.add_button.rect().center()).y()-
               panel.search.mapTo(panel,panel.search.rect().center()).y())<5
    assert not panel.add_button.icon().isNull()
    panel.add_button.click();assert panel.editor.isVisible()
    panel.title_edit.setText('Added from plus');panel.save_edit()
    assert len(store.locations(kind))==3
    item=next(panel.listing.item(i) for i in range(panel.listing.count())
              if panel.listing.item(i).data(Qt.ItemDataRole.UserRole)['title']=='Second saved page')
    panel.listing.scrollToItem(item);wait(app,20)
    delegate=panel.listing.itemDelegate()
    edit,remove=delegate.action_rects(panel.listing.visualItemRect(item),panel.listing.indexFromItem(item))
    assert edit.top()<remove.top()
    QTest.mouseClick(panel.listing.viewport(),Qt.MouseButton.LeftButton,pos=edit.center())
    assert panel.editor.isVisible() and panel.title_edit.text()=='Second saved page'
    panel.title_edit.setText('Renamed by pencil');panel.save_edit()
    assert any(row['title']=='Renamed by pencil' for row in store.locations(kind))
    item=panel.listing.currentItem()
    edit,remove=delegate.action_rects(panel.listing.visualItemRect(item),panel.listing.indexFromItem(item))
    QTest.mouseClick(panel.listing.viewport(),Qt.MouseButton.LeftButton,pos=remove.center())
    assert len(store.locations(kind))==2
    assert not any(row['title']=='Renamed by pencil' for row in store.locations(kind))
    assert r.pageNavigator().currentPage()==0
    QTest.mouseClick(r.viewport(),Qt.MouseButton.LeftButton,pos=r.viewport().rect().bottomRight()-QPoint(10,10))
    wait(app,50)
    assert not panel.isVisible() and not panel._filter_installed
    w.close()


def test_settings_sample_section_defaults_and_cancel_are_isolated(app,tmp_path):
    store=Store(tmp_path/'settings.db')
    store.set('theme','Dark');store.set('toolbar_labels',True)
    store.set('history_paused',True);store.set('ruler_height',49)
    dialog=SettingsDialog(store)
    assert dialog.preview.image.pixelColor(0,0)==QColor(COLORS['Dark'][0])
    for theme in COLORS:
        dialog.theme.setCurrentText(theme)
        assert dialog.preview.image.pixelColor(0,0)==QColor(COLORS[theme][0])
    original=dialog.preview.original.pixelColor(320,80)
    dialog.theme.setCurrentText('Sepia')
    assert dialog.preview.image.pixelColor(320,80)==original
    dialog.preserve.setChecked(False)
    assert dialog.preview.image.pixelColor(320,80)!=original
    dialog.shortcut_edits['home'].setKeySequence(QKeySequence('Ctrl+H'))
    dialog.reset_appearance()
    dialog.reset_reading()
    assert dialog.height.value()==28 and dialog.preserve.isChecked()
    assert not dialog.labels.isChecked() and not dialog.record_history.isChecked()
    assert dialog.shortcut_values()['home']=='Ctrl+H'
    dialog.reset_general()
    assert not dialog.labels.isChecked() and dialog.record_history.isChecked()
    assert dialog.shortcut_values()['home']=='Ctrl+H'
    dialog.reject()
    assert store.get('theme')=='Dark' and store.get('toolbar_labels')
    assert store.get('history_paused') and store.get('ruler_height')==49


def test_shortcut_categories_filter_empty_and_conflict_recovery(app,tmp_path):
    dialog=SettingsDialog(Store(tmp_path/'filter.db'))
    dialog.filter.setText('Split Reading')
    assert not dialog.shortcut_groups['Split Reading'][0].isHidden()
    assert dialog.shortcut_groups['Documents and Tabs'][0].isHidden()
    assert not dialog.shortcut_edits['swap'].isHidden()
    dialog.filter.setText('no such command')
    assert not dialog.no_commands.isHidden()
    dialog.shortcut_edits['home'].setKeySequence(QKeySequence('Ctrl+O'))
    dialog.accept()
    assert dialog.result()!=QDialog.DialogCode.Accepted
    assert 'assigned to both' in dialog.error.text() and not dialog.error.isHidden()
    assert dialog.filter.text()=='' and not dialog.shortcut_edits['home'].isHidden()
    dialog.reset_shortcuts()
    assert dialog.error.isHidden()
    dialog.accept()
    assert dialog.result()==QDialog.DialogCode.Accepted


def test_old_database_label_migration_backup_and_validation(tmp_path):
    path=tmp_path/'legacy.db'
    db=sqlite3.connect(path)
    db.execute('CREATE TABLE locations(id INTEGER PRIMARY KEY,kind TEXT,path TEXT,page INTEGER,title TEXT,x REAL,y REAL)')
    db.execute("INSERT INTO locations VALUES(1,'favorite','/missing.pdf',1,'Intro',0,30)")
    db.commit();db.close()
    store=Store(path)
    assert store.locations('favorite')[0]['label'] is None
    store.update_labels('/missing.pdf',{1:'ii'})
    backup=tmp_path/'backup.json'
    store.export_favorites(backup)
    target=Store(tmp_path/'import.db')
    target.import_favorites(backup)
    row=target.locations('favorite')[0]
    assert row['label']=='ii' and row['page']==1 and row['y']==30
    assert page_details(row)=='Page ii · PDF page 2'
    old=dict(row);old.pop('label')
    backup.write_text(json.dumps([old]))
    target.import_favorites(backup)
    assert target.locations('favorite')[0]['label'] is None
    assert page_details(target.locations('favorite')[0])=='PDF page 2'
    backup.write_text(json.dumps([row,dict(row,label=123)]))
    try: target.import_favorites(backup)
    except ValueError: pass
    else: raise AssertionError('Invalid label was accepted')
    assert len(target.locations('favorite'))==2
    target.db.close();store.db.close()


def test_loaded_pdf_hydrates_legacy_labels_and_home_keeps_them_after_restart(app,technical_pdf,tmp_path):
    store=Store(tmp_path/'labels.db')
    store.add('favorite',technical_pdf,1,'Preface',20,45)
    store.add('bookmark',technical_pdf,2,'First chapter')
    w=Window(store,restore=False);w.show()
    w.open_pdf(technical_pdf);wait(app)
    assert store.locations('favorite')[0]['label']=='ii'
    assert store.locations('bookmark',str(technical_pdf))[0]['label']=='1'
    w.show_home();wait(app)
    assert 'Page ii · PDF page 2' in w.home.favorites.item(0).text()
    w.close()
    w=Window(store,restore=False)
    assert not w.docs and 'Page ii · PDF page 2' in w.home.favorites.item(0).text()
    w.close()


def test_favorites_group_filter_rename_remove_and_escape(app,pdf,technical_pdf,tmp_path):
    store=Store(tmp_path/'favorites.db')
    store.add('favorite',technical_pdf,1,'Preface')
    store.add('favorite',pdf,1,'Second')
    store.add('favorite',pdf,0,'First')
    w=Window(store,restore=False);w.show();w.open_pdf(pdf);wait(app)
    panel=LocationsPanel(w,'favorite');panel.show();wait(app)
    assert panel.listing.count()==3
    assert [panel.listing.item(i).data(GROUP_ROLE) for i in range(3)]==[pdf.name,'',technical_pdf.name]
    panel.search.setText('second')
    assert panel.selected()['title']=='Second'
    assert panel.listing.item(1).data(GROUP_ROLE)==pdf.name
    panel.rename_selected()
    panel.title_edit.setText('Renamed second')
    QTest.keyClick(panel.title_edit,Qt.Key.Key_Return)
    assert panel.selected()['title']=='Renamed second' and not panel.editor.isVisible()
    assert [action.text() for action in panel.actions_menu().actions() if not action.isSeparator()]==['Open saved page','Rename…','Remove']
    panel.remove_selected()
    assert len(store.locations('favorite'))==2
    panel.search.setText('not found')
    assert panel.empty.isVisible() and panel.selected() is None
    panel.add_current();assert panel.editor.isVisible()
    QTest.keyClick(panel.title_edit,Qt.Key.Key_Escape)
    assert not panel.editor.isVisible() and panel.isVisible()
    QTest.keyClick(panel.search,Qt.Key.Key_Escape)
    assert not panel.isVisible()
    w.close()


def test_save_favorite_uses_source_anchor_and_enter_targets_focused_split(app,pdf,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'split.db'),restore=False);w.show()
    primary=w.open_pdf(pdf);w.open_pdf(technical_pdf);w.split(0,1);wait(app)
    other=w.secondary
    other.jump(1,QPointF(10,20));w.focus_reader(other);wait(app)
    anchor=other.state()
    before=primary.state()
    panel=LocationsPanel(w,'favorite');panel.show();wait(app)
    panel.add_button.click()
    panel.title_edit.setText('Useful page')
    QTest.keyClick(panel.title_edit,Qt.Key.Key_Return)
    row=w.store.locations('favorite')[0]
    assert row['page']==anchor.get('anchor_page',anchor['page'])
    assert row['label']==other.document().pageLabel(row['page'])
    assert (row['x'],row['y'])==(anchor['x'],anchor['y'])
    other.jump(3);wait(app)
    panel.listing.setFocus()
    QTest.keyClick(panel.listing,Qt.Key.Key_Return);wait(app)
    assert not panel.isVisible() and w.active is other
    assert other.pageNavigator().currentPage()==row['page']
    assert primary.state()['page']==before['page']
    assert primary.state()['vertical']==before['vertical']
    w.close()


def test_contents_search_labels_location_and_personal_bookmark_scope(app,pdf,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'outlines.db'),restore=False);w.show()
    w.open_pdf(pdf);r=w.open_pdf(technical_pdf);wait(app)
    w.store.add('bookmark',pdf,0,'Other document')
    panel=LocationsPanel(w,'bookmark');panel.show();wait(app)
    assert panel.tabs.tabText(0)=='Contents' and panel.tabs.tabText(1)=='My bookmarks'
    assert panel.outline_model.rowCount()==5 and panel.listing.count()==0
    panel.search.setText('Page ii')
    assert panel.outline_filter.rowCount()==1
    panel.search.setText('nothing')
    assert panel.outline_empty.isVisible()
    panel.search.clear()
    panel.add_button.click()
    assert panel.tabs.currentIndex()==1
    panel.title_edit.setText('Personal opening');panel.save_edit()
    assert panel.listing.count()==1 and panel.selected()['path']==str(technical_pdf)
    panel.tabs.setCurrentIndex(0)
    panel.search.setText('Chapter 3')
    panel.outline.setCurrentIndex(panel.outline_filter.index(0,0))
    QTest.keyClick(panel.outline,Qt.Key.Key_Return);wait(app)
    assert not panel.isVisible() and r.pageNavigator().currentPage()==2
    assert r.state()['y']>=0
    assert len(w.store.locations('bookmark',str(pdf)))==1
    w.close()


def test_missing_favorite_locate_updates_all_related_paths(app,pdf,tmp_path,monkeypatch):
    store=Store(tmp_path/'missing.db');old=str(tmp_path/'missing.pdf')
    store.add('favorite',old,2,'Favorite')
    store.add('bookmark',old,3,'Bookmark')
    store.record_history(old,2)
    store.set('session',dict(documents=[dict(path=old,page=2)],active_path=old))
    w=Window(store,restore=False);w.show()
    panel=LocationsPanel(w,'favorite');panel.show();wait(app)
    assert 'Locate File…' in [action.text() for action in panel.actions_menu().actions()]
    def choose_file(*args):
        child=QDialog(panel);child.setModal(True);child.show();wait(app,30)
        assert panel.isVisible() and QApplication.activeModalWidget() is child
        child.reject();child.deleteLater()
        return str(pdf),'PDF (*.pdf)'
    monkeypatch.setattr(QFileDialog,'getOpenFileName',choose_file)
    panel.locate_selected()
    assert panel.selected()['path']==str(pdf)
    assert store.locations('bookmark')[0]['path']==str(pdf)
    assert store.recent(pdf)['page']==2
    assert store.get('session')['documents'][0]['path']==str(pdf)
    panel.open_selected();wait(app)
    assert w.active.path==str(pdf) and w.active.pageNavigator().currentPage()==2
    w.close()


def run_modal_panel(window,kind,callback):
    errors=[]
    def interact():
        panel=next((p for p in window.findChildren(LocationsPanel) if p.isVisible()),None)
        try:
            assert isinstance(panel,LocationsPanel)
            callback(panel)
        except Exception as error: errors.append(error)
        finally:
            if isinstance(panel,LocationsPanel) and panel.isVisible(): panel.reject()
    QTimer.singleShot(80,interact)
    window.locations(kind)
    wait(QApplication.instance(),120)
    if errors: raise errors[0]


def test_home_manage_opens_anchored_panel_and_closes_cleanly(app,tmp_path):
    w=Window(Store(tmp_path/'home-popup.db'),restore=False);w.show();wait(app)
    visited=[]
    def check(panel):
        assert panel.empty.isVisible() and not panel.add_button.isEnabled()
        assert panel.screen().availableGeometry().contains(panel.geometry())
        visited.append(panel)
    run_modal_panel(w,'favorite',check)
    assert visited and not visited[0]._filter_installed
    w.close()


def test_modal_bookmark_panel_navigates_focused_pane_and_closes_with_enter(app,pdf,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'modal-split.db'),restore=False);w.show()
    primary=w.open_pdf(pdf);w.open_pdf(technical_pdf);w.split(0,1);wait(app)
    secondary=w.secondary;w.focus_reader(secondary)
    before=primary.state()
    def navigate(panel):
        assert panel.reader is secondary
        panel.search.setText('Chapter 3')
        QTest.keyClick(panel.search,Qt.Key.Key_Down)
        QTest.keyClick(panel.outline,Qt.Key.Key_Return)
        assert not panel.isVisible()
    run_modal_panel(w,'bookmark',navigate);wait(app)
    assert w.active is secondary and secondary.pageNavigator().currentPage()==2
    assert primary.state()==before
    w.close()


def test_hierarchical_contents_filter_retains_parent_and_keyboard_opens_child(app,tmp_path):
    from reportlab.pdfgen.canvas import Canvas
    path=tmp_path/'hierarchy.pdf'
    canvas=Canvas(str(path),pagesize=(600,800))
    canvas.bookmarkPage('part');canvas.addOutlineEntry('Part one','part',0)
    canvas.drawString(40,700,'Part one');canvas.showPage()
    canvas.bookmarkPage('child',fit='XYZ',left=20,top=650,zoom=1)
    canvas.addOutlineEntry('A nested theorem','child',1)
    canvas.drawString(40,650,'A nested theorem');canvas.showPage()
    canvas.save()
    w=Window(Store(tmp_path/'nested.db'),restore=False);w.show()
    reader=w.open_pdf(path);wait(app)
    panel=LocationsPanel(w,'bookmark');panel.show();wait(app)
    panel.search.setText('nested theorem')
    parent=panel.outline_filter.index(0,0)
    assert panel.outline_filter.rowCount()==1
    assert panel.outline_filter.rowCount(parent)==1
    child=panel.outline_filter.index(0,0,parent)
    panel.outline.setCurrentIndex(child)
    QTest.keyClick(panel.outline,Qt.Key.Key_Return);wait(app)
    assert reader.pageNavigator().currentPage()==1
    assert not panel.isVisible()
    w.close()


def test_search_down_moves_to_filtered_destination_without_reading_shortcuts(app,pdf,tmp_path):
    store=Store(tmp_path/'keyboard.db');store.add('favorite',pdf,3,'A saved page')
    w=Window(store,restore=False);w.show();reader=w.open_pdf(pdf);wait(app)
    panel=LocationsPanel(w,'favorite');panel.show();wait(app)
    QTest.keyClick(panel.search,Qt.Key.Key_Down)
    assert panel.listing.hasFocus()
    assert reader.pageNavigator().currentPage()==0
    QTest.keyClick(panel.listing,Qt.Key.Key_Return);wait(app)
    assert reader.pageNavigator().currentPage()==3
    w.close()
