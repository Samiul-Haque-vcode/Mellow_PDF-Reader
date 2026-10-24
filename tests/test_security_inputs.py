"""Untrusted PDF URL handlers and imported Favorites metadata boundaries."""
import json
import pytest
from PySide6.QtCore import QUrl,QPointF,Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtTest import QTest
from reportlab.pdfgen.canvas import Canvas
from test_reader import app,wait
from mellow.platform import open_external_link
from mellow.storage import Store
from mellow.app import Window

@pytest.mark.parametrize('value',['file:///C:/Windows/System32/calc.exe','javascript:alert(1)','data:text/html,test','ms-settings:privacy','ftp://example.com/a','https://user:password@example.com/','https:///missing-host','mailto:person@example.com?attach=file:///secret.pdf','mailto:person@example.com?ATTACHMENT=secret','mailto:person%0A@example.com','relative.pdf'])
def test_untrusted_link_schemes_never_reach_os(app,monkeypatch,value):
    calls=[];monkeypatch.setattr(QDesktopServices,'openUrl',lambda url:calls.append(url) or True)
    assert not open_external_link(QUrl(value)) and not calls

@pytest.mark.parametrize('value',['https://example.com/paper?q=test#figure','http://example.com','mailto:person@example.com?subject=Paper'])
def test_normal_web_and_email_links_remain_available(app,monkeypatch,value):
    calls=[];monkeypatch.setattr(QDesktopServices,'openUrl',lambda url:calls.append(url.toString()) or True)
    assert open_external_link(QUrl(value)) and calls==[QUrl(value).toString()]

@pytest.mark.parametrize('value',['file:///C:/Windows/System32/calc.exe','https://example.com/paper'])
def test_actual_pdf_link_click_uses_policy(app,tmp_path,monkeypatch,value):
    path=tmp_path/'link.pdf';c=Canvas(str(path));c.drawString(50,700,'External reference')
    c.linkURL(value,(50,680,250,730),relative=0);c.showPage();c.save()
    w=Window(Store(tmp_path/'state.db'),restore=False);w.show();r=w.open_pdf(path);wait(app,50)
    calls=[];monkeypatch.setattr(QDesktopServices,'openUrl',lambda url:calls.append(url.toString()) or True)
    try:
        QTest.mouseClick(r.viewport(),Qt.MouseButton.LeftButton,pos=r.point_in_view(0,QPointF(100,140)).toPoint())
        assert bool(calls)==value.startswith('https:')
    finally:w.close()

@pytest.mark.parametrize('change',[{'page':True},{'page':10**30},{'x':float('nan')},{'y':float('inf')},{'x':1e100},{'x':True},{'path':'bad\x00.pdf'},{'path':''},{'title':'x'*100001},{'label':'x'*100001}])
def test_favorites_reject_invalid_entries_without_partial_import(tmp_path,change):
    store=Store(tmp_path/'state.db');store.add('favorite','/keep.pdf',0,'Keep')
    before=store.locations('favorite');row=dict(path='/book.pdf',page=0,title='Book',x=0,y=0)
    path=tmp_path/'import.json';path.write_text(json.dumps([row,dict(row,**change)]))
    with pytest.raises(ValueError):store.import_favorites(path)
    assert store.locations('favorite')==before
    store.db.close()

def test_oversized_favorites_are_rejected_before_parsing(tmp_path):
    path=tmp_path/'huge.json'
    with path.open('wb') as out:out.truncate(32*1024*1024+1)
    store=Store(tmp_path/'state.db')
    with pytest.raises(ValueError,match='32 MB'):store.import_favorites(path)
    assert not store.locations('favorite');store.db.close()

@pytest.mark.parametrize('result',[0,32768])
def test_windows_directory_lookup_fails_closed(monkeypatch,result):
    import ctypes
    from types import SimpleNamespace
    from mellow.platform import explorer_executable
    monkeypatch.setattr(ctypes,'WinDLL',lambda *a,**k:SimpleNamespace(GetWindowsDirectoryW=lambda *a:result),raising=False)
    with pytest.raises(OSError):explorer_executable()
