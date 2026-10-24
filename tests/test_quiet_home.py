"""Home has one opening control; tabs retain their own reader-only opener."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog,QLabel
from PySide6.QtTest import QTest
from test_reader import app,pdf,wait
from mellow.app import Window
from mellow.storage import Store


def test_home_opening_controls_and_reading_roundtrip(app,pdf,tmp_path,monkeypatch):
    calls=[]
    monkeypatch.setattr(QFileDialog,'getOpenFileNames',lambda *args:(calls.append(1) or [],''))
    w=Window(Store(tmp_path/'quiet.db'),restore=False);w.show();wait(app)
    assert w.home.opened.isVisible() and not w.add_tab_button.isVisible()
    assert w.brand_mark.isVisible() and not w.brand_mark.pixmap().isNull()
    labels=[label.text() for label in w.home.findChildren(QLabel)]
    assert not any('Ctrl+' in text or 'While reading' in text for text in labels)
    QTest.mouseClick(w.home.opened,Qt.MouseButton.LeftButton)
    assert len(calls)==1
    QTest.keyClick(w,Qt.Key.Key_O,Qt.KeyboardModifier.ControlModifier)
    assert len(calls)==2
    r=w.open_pdf(pdf);wait(app)
    r.jump(3);wait(app)
    assert w.add_tab_button.isVisible()
    w.show_home();wait(app)
    assert not w.add_tab_button.isVisible() and w.home.opened.isVisible()
    w.home.resume.click();wait(app)
    assert w.add_tab_button.isVisible() and r.pageNavigator().currentPage()==3
    w.close_tab(0);wait(app)
    assert w._on_home and not w.add_tab_button.isVisible()
    w.close()
