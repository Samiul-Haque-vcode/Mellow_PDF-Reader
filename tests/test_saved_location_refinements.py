"""Real PDF recovery, atomic metadata migration and nonblocking duplicate notices."""
import hashlib
import sqlite3
from pathlib import Path
import pytest
from pypdf import PdfWriter
from PySide6.QtCore import Qt,QEvent
from PySide6.QtWidgets import QFileDialog,QInputDialog,QApplication
from test_reader import app,pdf,technical_pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.locations import LocationsPanel
from mellow.saved_locations import destination_counts,destination_key


def snapshot(store):
    return list(store.db.iterdump())


def seed(store,old,other=None):
    store.add('favorite',old,2,'Favorite',3,40,label='iii')
    store.add('bookmark',old,3,'Bookmark',8,90,label='iv')
    store.set_document_layout(old,'two')
    store.set_document_cover(old,False)
    store.set_document_option(old,'crop',(2,3,4,5))
    store.set_document_option(old,'numbering',dict(pdf=1,book=1))
    state=dict(path=str(old),page=5,x=0,y=12,past=[dict(path=str(old),page=1)],
               future=[dict(path=str(other or old),page=0)],title=str(old))
    store.record_history(old,5,state=state)
    store.set('session',dict(documents=[state],secondary=dict(state,page=3),active_path=str(old),
                             active_secondary=True,sizes=[700,300],orientation=2))
    return state


def test_relocation_preserves_all_destinations_preferences_and_nested_paths(tmp_path,pdf,technical_pdf):
    store=Store(tmp_path/'migration.db');old=tmp_path/'missing.pdf'
    before=seed(store,old,technical_pdf)
    digest=hashlib.sha256(pdf.read_bytes()).hexdigest()
    store.relocate(str(old),str(pdf))
    assert store.recent(old) is None and store.recent(pdf)['page']==5
    for kind,page,x,y,label in [('favorite',2,3,40,'iii'),('bookmark',3,8,90,'iv')]:
        row=store.locations(kind)[0]
        assert (row['path'],row['page'],row['x'],row['y'],row['label'])==(str(pdf),page,x,y,label)
    assert store.document_layout(pdf)=='two' and not store.document_cover(pdf)
    assert store.document_option(pdf,'crop')==(2,3,4,5)
    assert store.document_option(pdf,'numbering')==dict(pdf=1,book=1)
    state=store.recent(pdf)['state']
    assert state['past'][0]['path']==str(pdf) and state['future'][0]['path']==str(technical_pdf)
    assert state['title']==str(old)  # user text is never rewritten
    session=store.get('session')
    assert session['active_path']==str(pdf) and session['secondary']['past'][0]['path']==str(pdf)
    assert session['active_secondary'] and session['sizes']==[700,300] and session['orientation']==2
    assert before['path']==str(old) and hashlib.sha256(pdf.read_bytes()).hexdigest()==digest


@pytest.mark.parametrize('target_data',['history','options','favorite','session'])
def test_relocation_never_overwrites_a_known_target(tmp_path,pdf,target_data):
    store=Store(tmp_path/'collision.db');old=tmp_path/'missing.pdf';seed(store,old)
    if target_data=='history':store.record_history(pdf,1)
    elif target_data=='options':store.set_document_layout(pdf,'single')
    elif target_data=='favorite':store.add('favorite',pdf,0,'Different document')
    else:
        session=store.get('session');session['documents'].append(dict(path=str(pdf),page=0));store.set('session',session)
    before=snapshot(store)
    with pytest.raises(ValueError,match='already has saved reading data'):store.relocate(str(old),str(pdf))
    assert snapshot(store)==before


def test_relocation_rolls_back_if_a_later_metadata_write_fails(tmp_path,pdf):
    store=Store(tmp_path/'rollback.db');old=tmp_path/'missing.pdf';seed(store,old)
    store.db.executescript("CREATE TRIGGER fail_history_move BEFORE UPDATE OF path ON history BEGIN SELECT RAISE(ABORT,'simulated write failure'); END;")
    before=snapshot(store)
    with pytest.raises(sqlite3.IntegrityError,match='simulated write failure'):store.relocate(str(old),str(pdf))
    assert snapshot(store)==before


@pytest.mark.parametrize('kind',['bookmark','favorite'])
def test_duplicate_notice_long_titles_and_intentional_save(app,pdf,tmp_path,kind):
    store=Store(tmp_path/'duplicates.db');w=Window(store,restore=False);w.show();r=w.open_pdf(pdf);wait(app)
    state=r.state();page=state.get('anchor_page',state['page'])
    title='A detailed mathematical result '+('with a long title '*10)+'<b>literal</b>'
    original=store.add(kind,pdf,page,title,state['x'],state['y'])
    store.add(kind,pdf,page,'Different line',state['x'],state['y']+30)
    store.add(kind,pdf,page+1,'Different page',state['x'],state['y'])
    store.add('favorite' if kind=='bookmark' else 'bookmark',pdf,page,'Separate collection',state['x'],state['y'])
    panel=LocationsPanel(w,kind);panel.show();wait(app,40);panel.add_button.click()
    assert panel.duplicate_hint.isVisible() and 'Already saved:' in panel.duplicate_hint.text()
    assert '&lt;b&gt;literal&lt;/b&gt;' in panel.duplicate_hint.toolTip()
    panel.title_edit.setText('Intentional duplicate');panel.save_edit()
    assert panel.selected()['title']=='Intentional duplicate' and panel.selected()['id']!=original
    rows=store.locations(kind);assert len(rows)==4
    same=store.matching_locations(kind,pdf,page,state['x'],state['y'])
    assert len(same)==2
    flagged=[panel.listing.item(i) for i in range(panel.listing.count()) if '2 saved here' in panel.listing.item(i).text()]
    assert len(flagged)==2
    long_item=next(panel.listing.item(i) for i in range(panel.listing.count())
                   if panel.listing.item(i).data(Qt.ItemDataRole.UserRole)['id']==original)
    assert title in long_item.data(Qt.ItemDataRole.AccessibleTextRole)
    assert '&lt;b&gt;literal&lt;/b&gt;' in long_item.toolTip()
    assert panel.title_elide==Qt.TextElideMode.ElideRight
    panel.search.setText(Path(pdf).name)
    assert all(not panel.listing.item(i).isHidden() for i in range(panel.listing.count()))
    panel.search.clear();panel.listing.setCurrentItem(long_item);panel.rename_selected()
    assert panel.title_edit.text()==title  # the editor receives the unelided original
    panel.cancel_edit();panel.remove_selected()
    assert not any('saved here' in panel.listing.item(i).text() for i in range(panel.listing.count()))
    panel.reject();w.show_home();wait(app,40)
    if kind=='favorite':assert 'Intentional duplicate' in w.home.favorites.item(0).toolTip()
    w.close()


def test_duplicate_keys_keep_pages_documents_and_positions_independent(tmp_path):
    row=dict(kind='favorite',path=str(tmp_path/'one.pdf'),page=0,x=12.111,y=30.001)
    duplicate=dict(row,title='Another name',x=12.112,y=30.002)
    alternatives=[dict(row,page=1),dict(row,path=str(tmp_path/'two.pdf')),dict(row,y=31),dict(row,kind='bookmark')]
    counts=destination_counts([row,duplicate]+alternatives)
    assert counts[destination_key(row)]==2 and all(counts[destination_key(r)]==1 for r in alternatives)
    assert destination_key(dict(row,y=float('nan'))) is None


@pytest.mark.parametrize('entry',['recent','favorite'])
def test_locate_from_home_keeps_requested_destination_and_closed_tab_paths(app,pdf,tmp_path,monkeypatch,entry):
    store=Store(tmp_path/'home-relocate.db');old=tmp_path/'missing.pdf';seed(store,old)
    w=Window(store,restore=False);w.show();wait(app,30)
    w.closed_tabs=[dict(state=dict(path=str(old),page=1,past=[dict(path=str(old),page=0)]),index=0)]
    saved=store.recent(old) if entry=='recent' else store.locations('favorite')[0]
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(pdf),'PDF (*.pdf)'))
    reader=w.open_recent(saved);wait(app,200)
    assert reader is not None and reader.path==str(pdf)
    assert reader.pageNavigator().currentPage()==(5 if entry=='recent' else 2)
    assert w.closed_tabs[0]['state']['path']==str(pdf) and w.closed_tabs[0]['state']['past'][0]['path']==str(pdf)
    assert store.locations('bookmark')[0]['path']==str(pdf)
    assert w.home.favorites.item(0).data(Qt.ItemDataRole.UserRole)['path']==str(pdf)
    w.close()


def test_invalid_cancelled_and_conflicting_locate_leave_metadata_untouched(app,pdf,tmp_path,monkeypatch):
    store=Store(tmp_path/'invalid.db');old=tmp_path/'missing.pdf';seed(store,old)
    w=Window(store,restore=False);w.show();wait(app,20);errors=[]
    monkeypatch.setattr(w,'error',lambda message:errors.append(str(message)))
    before=snapshot(store)
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:('',''))
    assert w.open_recent(store.recent(old)) is None and snapshot(store)==before
    invalid=tmp_path/'not-really.pdf';invalid.write_text('This is not a PDF.')
    assert w.relocate_pdf(old,invalid) is None and 'not a readable PDF' in errors[-1]
    assert snapshot(store)==before
    assert w.relocate_pdf(old,tmp_path/'absent.pdf') is None and snapshot(store)==before
    store.set_document_layout(pdf,'single');before=snapshot(store)
    assert w.relocate_pdf(old,pdf) is None and 'already has saved reading data' in errors[-1]
    assert snapshot(store)==before
    w.close()


def test_relocation_rejects_open_source_and_target_without_losing_state(app,pdf,technical_pdf,tmp_path,monkeypatch):
    store=Store(tmp_path/'open-reader.db');w=Window(store,restore=False);w.show();w.open_pdf(pdf);wait(app,40)
    errors=[];monkeypatch.setattr(w,'error',lambda message:errors.append(str(message)))
    before=snapshot(store)
    assert w.relocate_pdf(pdf,technical_pdf) is None and 'Close the tab' in errors[-1]
    assert snapshot(store)==before
    old=tmp_path/'missing.pdf';store.add('favorite',old,2,'Saved')
    before=snapshot(store)
    assert w.relocate_pdf(old,pdf) is None and 'already open' in errors[-1]
    assert snapshot(store)==before
    w.close()


def test_locate_panel_survives_native_picker_deactivation_without_qt_modal(app,pdf,tmp_path,monkeypatch):
    store=Store(tmp_path/'native-picker.db');old=tmp_path/'missing.pdf'
    store.add('favorite',old,1,'Saved page')
    w=Window(store,restore=False);w.show();panel=LocationsPanel(w,'favorite');panel.show();wait(app,30)
    def native_picker(*args,**kwargs):
        assert QApplication.activeModalWidget() is None
        monkeypatch.setattr(QApplication,'activeWindow',lambda:w)
        QApplication.sendEvent(panel,QEvent(QEvent.Type.WindowDeactivate));wait(app,30)
        assert panel.isVisible() and panel._locating
        return str(pdf),''
    monkeypatch.setattr(QFileDialog,'getOpenFileName',native_picker)
    panel.locate_selected()
    assert panel.isVisible() and not panel._locating and panel.selected()['path']==str(pdf)
    panel.reject();w.close()


def test_locate_in_split_pane_and_protected_pdf_validation(app,pdf,technical_pdf,tmp_path,monkeypatch):
    store=Store(tmp_path/'split-recovery.db');old=tmp_path/'missing.pdf'
    store.add('favorite',old,3,'Requested page')
    target=tmp_path/'moved.pdf';target.write_bytes(pdf.read_bytes())
    w=Window(store,restore=False);w.show();first=w.open_pdf(pdf);w.open_pdf(technical_pdf);w.split(0,1);wait(app)
    primary=first.state();w.focus_reader(w.secondary)
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(target),''))
    result=w.open_saved(store.locations('favorite')[0]);wait(app,200)
    assert result is w.secondary and result.path==str(target) and result.pageNavigator().currentPage()==3
    assert first.state()['page']==primary['page'] and first.state()['vertical']==primary['vertical']
    w.close()
    writer=PdfWriter();writer.append(str(pdf));writer.encrypt('secret')
    encrypted=tmp_path/'encrypted.pdf'
    with encrypted.open('wb') as out:writer.write(out)
    protected_store=Store(tmp_path/'encrypted.db');protected_store.add('favorite',old,1,'Protected page')
    other=Window(protected_store,restore=False);other.show();wait(app,20)
    passwords=[]
    def password(*args,**kwargs):
        passwords.append(True);return 'secret',True
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(encrypted),''))
    monkeypatch.setattr(QInputDialog,'getText',password)
    opened=other.open_saved(protected_store.locations('favorite')[0]);wait(app,100)
    assert opened is not None and opened.path==str(encrypted) and opened.pageNavigator().currentPage()==1
    assert len(passwords)==1
    assert protected_store.locations('favorite')[0]['path']==str(encrypted)
    other.close()
