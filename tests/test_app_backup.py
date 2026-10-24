"""Reinstallable metadata, atomic failures and restore shutdown ownership."""
import copy
import json
import sqlite3
import pytest
from PySide6.QtWidgets import QFileDialog,QMessageBox,QApplication
from PySide6.QtCore import QCoreApplication,QEvent
from shiboken6 import isValid
from test_reader import app,pdf,wait
from mellow import backup
from mellow.app import Window
from mellow.settings import SettingsDialog
from mellow.storage import Store


@pytest.fixture(autouse=True)
def dispose_backup_windows(app):
    previous=list(QApplication.topLevelWidgets())
    yield
    for widget in QApplication.topLevelWidgets():
        if isValid(widget) and widget not in previous:
            widget.close()
            widget.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    wait(app,30)


def seeded(tmp_path,pdf):
    store=Store(tmp_path/'data'/'mellow.sqlite3')
    store.set('theme','Black')
    store.set('shortcuts',{'favorites':'Ctrl+Alt+F'})
    store.set('theme_tuning',{'Dark':dict(warmth=7,contrast=12)})
    store.set('session',dict(documents=[dict(path=str(pdf),page=3,zoom=1.4,mode=0)],home=False))
    store.add('favorite',pdf,3,'Chapter four',12,32,label='iv')
    store.add('bookmark',pdf,5,'Practice',4,8,label='6')
    store.record_history(pdf,3,12,32,state=dict(page=3,zoom=1.4,mode=0))
    store.set_document_layout(pdf,'two_continuous')
    store.set_document_cover(pdf,False)
    store.set_document_option(pdf,'crop',[1,2,3,4])
    store.set_document_option(pdf,'numbering',dict(pdf=2,book=1))
    return store


def test_roundtrip_replaces_all_metadata_in_fresh_install_without_pdf_copies(app,pdf,tmp_path):
    store=seeded(tmp_path,pdf)
    output=tmp_path/'reading.mellow-backup.json'
    before=pdf.read_bytes()
    backup.write(store,output)
    original=backup.read(output)
    store.db.close()
    # Simulate the metadata removal performed by uninstall.
    (tmp_path/'data'/'mellow.sqlite3').unlink()
    fresh=Store(tmp_path/'data'/'mellow.sqlite3')
    fresh.set('theme','Light');fresh.add('favorite',pdf,0,'Discard current data')
    backup.replace(fresh,original)
    assert backup.snapshot(fresh)==original
    assert fresh.locations('favorite')[0]['label']=='iv'
    assert fresh.document_option(pdf,'numbering')==dict(pdf=2,book=1)
    assert fresh.document_option(pdf,'crop')==(1.,2.,3.,4.)
    assert fresh.get('shortcuts')=={'favorites':'Ctrl+Alt+F'}
    assert pdf.read_bytes()==before
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_file())==sorted([pdf.name,output.name])
    fresh.db.close()


def test_settings_backup_captures_live_split_session_but_not_unsaved_preferences(app,pdf,tmp_path,monkeypatch):
    store=Store(tmp_path/'data'/'mellow.sqlite3')
    w=Window(store,restore=False);w.show();first=w.open_pdf(pdf);wait(app)
    w.split(0,0);wait(app);first.jump(2);w.secondary.jump(5);wait(app)
    w.focus_reader(w.secondary)
    dialog=SettingsDialog(store,w);dialog.theme.setCurrentText('Dark')
    dialog.backupRequested.connect(lambda:w.backup_data(dialog))
    output=tmp_path/'session.mellow-backup.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(output),''))
    monkeypatch.setattr(QMessageBox,'information',lambda *a,**k:None)
    dialog.backup_data.click()
    data=backup.read(output)
    settings={r['key']:json.loads(r['value']) for r in data['settings']}
    assert settings['theme']=='Sepia'
    assert settings['session']['documents'][0]['page']==2
    assert settings['session']['secondary']['page']==5
    assert settings['session']['active_secondary']
    assert dialog.theme.currentText()=='Dark' and not w._closing
    dialog.reject();w.close()


def test_restore_closes_without_overwriting_backup_then_reopens_saved_session(app,pdf,tmp_path,monkeypatch):
    old=seeded(tmp_path/'old',pdf)
    path=tmp_path/'reading.mellow-backup.json';backup.write(old,path);data=backup.read(path)
    store=Store(tmp_path/'new'/'mellow.sqlite3')
    w=Window(store,restore=False);w.show();r=w.open_pdf(pdf);r.jump(6);wait(app)
    dialog=SettingsDialog(store,w)
    dialog.restoreRequested.connect(lambda:w.restore_data(dialog))
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(path),''))
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.StandardButton.Yes)
    dialog.restore_data.click();wait(app,150)
    assert w._backup_restored and w._closing and not w.isVisible()
    assert backup.snapshot(store)==data
    # A late callback / repeated save may not replace the imported session.
    w.save_session()
    assert backup.snapshot(store)==data
    reopened=Window(store);reopened.show();wait(app,250)
    assert reopened.theme_name=='Black'
    assert reopened.active.pageNavigator().currentPage()==3
    assert reopened.active.zoomFactor()==1.4
    assert reopened.active.crop==(1.,2.,3.,4.)
    assert store.locations('favorite')[0]['title']=='Chapter four'
    reopened.close();old.db.close()


@pytest.mark.parametrize('cancel_picker',[False,True])
def test_restore_cancel_keeps_current_data_and_window(app,pdf,tmp_path,monkeypatch,cancel_picker):
    store=seeded(tmp_path,pdf);path=tmp_path/'valid.mellow-backup.json';backup.write(store,path)
    w=Window(store,restore=False);w.show();dialog=SettingsDialog(store,w)
    before=backup.snapshot(store)
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:('' if cancel_picker else str(path),''))
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.StandardButton.No)
    w.restore_data(dialog);wait(app,20)
    assert backup.snapshot(store)==before and not w._closing and w.isVisible()
    assert w._pending_backup_data is None
    dialog.reject();w.close()


@pytest.mark.parametrize('change',[
    lambda d:d.update(version=2),
    lambda d:d.update(format='other'),
    lambda d:d['data']['locations'][0].update(page=-1),
    lambda d:d['data']['locations'][0].update(x=float('nan')),
    lambda d:d['data']['locations'][0].update(kind='sql'),
    lambda d:next(r for r in d['data']['settings'] if r['key']=='session').update(value='{"documents":[{"path":"x","mode":99}]}'),
    lambda d:d['data']['document_options'][0].update(crop='[100,0,0,0]'),
    lambda d:d['data']['history'][0].update(state='{"past":[null]}'),
    lambda d:d['data'].update(locations={}),
])
def test_invalid_backups_are_rejected_before_current_data_changes(app,pdf,tmp_path,change):
    store=seeded(tmp_path,pdf);path=tmp_path/'invalid.json';backup.write(store,path)
    document=json.loads(path.read_text());change(document);path.write_text(json.dumps(document))
    before=backup.snapshot(store)
    with pytest.raises(ValueError):backup.read(path)
    assert backup.snapshot(store)==before
    store.db.close()


def test_transaction_rolls_back_every_table_on_restore_failure(app,pdf,tmp_path):
    store=seeded(tmp_path,pdf);before=backup.snapshot(store);data=copy.deepcopy(before)
    data['locations'][0]['title']='blocked'
    data['settings'][0]['value']='"Light"'
    store.db.execute("CREATE TEMP TRIGGER refuse_restore BEFORE INSERT ON locations WHEN NEW.title='blocked' BEGIN SELECT RAISE(ABORT,'test failure'); END")
    with pytest.raises(sqlite3.IntegrityError):backup.replace(store,data)
    assert backup.snapshot(store)==before
    store.db.close()


def test_failed_export_keeps_existing_backup_and_removes_temp_files(app,pdf,tmp_path,monkeypatch):
    store=seeded(tmp_path,pdf);path=tmp_path/'existing.json';path.write_bytes(b'previous backup')
    def fail(*args):raise OSError('Disk unavailable')
    monkeypatch.setattr(backup.os,'replace',fail)
    with pytest.raises(OSError):backup.write(store,path)
    assert path.read_bytes()==b'previous backup'
    assert not list(tmp_path.glob('.mellow-backup-*'))
    store.db.close()


def test_backup_cannot_be_saved_inside_uninstall_data_folder(app,pdf,tmp_path):
    store=seeded(tmp_path,pdf)
    for path in (tmp_path/'data'/'backup.json',tmp_path/'data'/'mellow.sqlite3'):
        with pytest.raises(ValueError,match='outside'):backup.write(store,path)
    assert store.locations('favorite')
    store.db.close()


def test_invalid_file_and_busy_tools_do_not_close_app(app,pdf,tmp_path,monkeypatch):
    store=seeded(tmp_path,pdf);w=Window(store,restore=False);w.show();dialog=SettingsDialog(store,w)
    path=tmp_path/'broken.json';path.write_bytes(b'not json')
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(path),''))
    errors=[];monkeypatch.setattr(QMessageBox,'warning',lambda *args:errors.append(args[-1]))
    before=backup.snapshot(store);w.restore_data(dialog)
    assert errors and backup.snapshot(store)==before and not w._closing
    w.file_jobs.append(object());errors.clear();w.restore_data(dialog)
    assert 'running PDF tools' in errors[0] and w._pending_backup_data is None
    w.file_jobs.clear();dialog.reject();w.close()


def test_oversized_and_truncated_files_are_rejected(tmp_path,monkeypatch):
    path=tmp_path/'bad.json';path.write_text('{"format":')
    with pytest.raises(ValueError):backup.read(path)
    monkeypatch.setattr(backup,'LIMIT',32);path.write_bytes(b' '*33)
    with pytest.raises(ValueError):backup.read(path)


def test_missing_session_file_does_not_block_other_documents(app,pdf,tmp_path,monkeypatch):
    store=seeded(tmp_path,pdf)
    saved=store.get('session')
    saved['documents'].append(dict(path=str(tmp_path/'missing.pdf'),page=0))
    store.set('session',saved)
    path=tmp_path/'missing.mellow-backup.json';backup.write(store,path)
    fresh=Store(tmp_path/'fresh'/'metadata.sqlite3');backup.replace(fresh,backup.read(path))
    notices=[];monkeypatch.setattr(Window,'error',lambda self,message:notices.append(message))
    w=Window(fresh);w.show();wait(app,200)
    assert len(w.readers)==1 and w.active.path==str(pdf)
    assert notices and 'missing.pdf' in notices[0]
    w.close();store.db.close()


def test_failed_restore_leaves_window_open_with_previous_metadata(app,pdf,tmp_path,monkeypatch):
    store=seeded(tmp_path,pdf);w=Window(store,restore=False);w.show();w.open_pdf(pdf);wait(app)
    previous=store.locations('favorite')
    w._pending_backup_data=backup.snapshot(store)
    def fail(*args):raise sqlite3.OperationalError('Cannot write metadata')
    monkeypatch.setattr(backup,'replace',fail)
    messages=[];monkeypatch.setattr(w,'error',messages.append)
    w.close();wait(app,30)
    assert not w._closing and not w._backup_restored and w.isVisible()
    assert store.locations('favorite')==previous and messages
    assert w._pending_backup_data is None
    w.close()
