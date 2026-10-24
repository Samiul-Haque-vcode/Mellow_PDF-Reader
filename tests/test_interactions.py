"""Interaction regressions for real reading views, including split panes."""
import sqlite3
import pytest
from PySide6.QtCore import QPoint,QPointF,Qt
from PySide6.QtGui import QWheelEvent,QNativeGestureEvent,QPointingDevice,QImage,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from test_reader import app,pdf,technical_pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.settings import SettingsDialog
from mellow.theme import recolor


def wheel(reader,point,delta=120,ctrl=True,pixels=0):
    mods=Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
    event=QWheelEvent(point,QPointF(reader.viewport().mapToGlobal(point.toPoint())),
                      QPoint(0,pixels),QPoint(0,delta),Qt.MouseButton.NoButton,mods,
                      Qt.ScrollPhase.ScrollUpdate,False)
    QApplication.sendEvent(reader.viewport(),event)
    return event


def anchor(reader,point):
    hit=reader.point_on_page(point)
    assert hit is not None
    return hit


@pytest.mark.parametrize('fit',['page','width','custom'])
@pytest.mark.parametrize('layout',['continuous','single'])
def test_ctrl_wheel_anchors_document_under_pointer(app,pdf,tmp_path,fit,layout):
    w=Window(Store(tmp_path/f'{fit}.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    r.set_page_layout(layout)
    if fit=='width': r.setZoomMode(r.ZoomMode.FitToWidth)
    elif fit=='custom':
        r.setZoomMode(r.ZoomMode.Custom)
        r.setZoomFactor(1.4)
    r.jump(3)
    wait(app)
    point=QPointF(r.viewport().width()*.56,r.viewport().height()*.45)
    page,location=anchor(r,point)
    before=r.effective_zoom()
    wheel(r,point)
    wait(app,80)
    assert r.zoomMode()==r.ZoomMode.Custom
    assert r.zoomFactor()>before
    after_page,after_location=anchor(r,point)
    assert after_page==page
    assert abs(after_location.y()-location.y())<2
    # Horizontal anchoring can clamp when the page fits inside the viewport.
    if r.horizontalScrollBar().maximum()>0:
        assert abs(after_location.x()-location.x())<2
    w.close()


@pytest.mark.parametrize('vertical',[False,True])
def test_zoom_only_changes_pane_under_pointer(app,pdf,tmp_path,vertical):
    w=Window(Store(tmp_path/'split.db'),restore=False)
    w.show()
    a=w.open_pdf(pdf)
    wait(app)
    w.split(0,0)
    if vertical: w.orientation()
    wait(app)
    b=w.secondary
    a.jump(2)
    b.jump(5)
    wait(app)
    before=a.state()
    b_before=b.effective_zoom()
    point=QPointF(b.viewport().rect().center())
    page,location=anchor(b,point)
    wheel(b,point,pixels=30,delta=0)
    wait(app,100)
    assert w.active is b
    assert b.zoomFactor()>b_before
    assert a.state()['zoom']==before['zoom']
    assert a.state()['vertical']==before['vertical']
    after_page,after_location=anchor(b,point)
    assert after_page==page and abs(after_location.y()-location.y())<2
    assert w.fit.currentText().endswith('%')
    w.close()


def test_native_pinch_and_regular_wheel(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'pinch.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    r.jump(2)
    wait(app)
    point=QPointF(r.viewport().rect().center())
    page,location=anchor(r,point)
    before=r.effective_zoom()
    event=QNativeGestureEvent(Qt.NativeGestureType.ZoomNativeGesture,QPointingDevice.primaryPointingDevice(),
                              2,point,point,QPointF(r.viewport().mapToGlobal(point.toPoint())),
                              .18,QPointF(0,0),1)
    QApplication.sendEvent(r.viewport(),event)
    wait(app,100)
    assert r.zoomFactor()>before
    after_page,after_location=anchor(r,point)
    assert after_page==page and abs(after_location.y()-location.y())<2
    zoom=r.zoomFactor()
    y=r.verticalScrollBar().value()
    wheel(r,point,delta=-120,ctrl=False)
    wait(app,80)
    assert r.zoomFactor()==zoom and r.verticalScrollBar().value()>y
    w.close()


def test_gesture_burst_coalesces_and_limits_zoom(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'burst.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    r.jump(3)
    wait(app)
    before=r.effective_zoom()
    changes=[]
    r.zoomFactorChanged.connect(changes.append)
    point=QPointF(r.viewport().rect().center())
    for _ in range(15): wheel(r,point,delta=8)
    assert not changes
    wait(app,100)
    assert len(changes)==1
    assert r.zoomFactor()==pytest.approx(before*1.15)
    r.zoom_to(100)
    wait(app,30)
    assert r.zoomFactor()==8
    r.zoom_to(.001)
    wait(app,30)
    assert r.zoomFactor()==.1
    w.close()


def test_home_preserves_and_resumes_split(app,pdf,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'home.db'),restore=False)
    w.show()
    a=w.open_pdf(pdf)
    w.open_pdf(technical_pdf)
    wait(app)
    w.split(0,1)
    wait(app)
    a.jump(3)
    w.secondary.jump(2)
    wait(app)
    secondary=w.secondary
    before_a,before_b=a.state(),secondary.state()
    w.focus_reader(secondary)
    w.show_home()
    wait(app)
    assert w.pages.currentWidget() is w.home and w._on_home
    assert not w.page.isEnabled()
    assert len(w.docs)==2 and w.secondary is secondary
    assert w.home.listing.count()==2
    w.resume_reading()
    wait(app)
    assert not w._on_home and w.pages.currentWidget() is w.splitter
    assert w.active is secondary
    assert a.state()['vertical']==before_a['vertical']
    assert secondary.state()['vertical']==before_b['vertical']
    w.close()


def test_recent_closed_document_reopens_at_saved_zoom_and_position(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'recent.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    r.setZoomMode(r.ZoomMode.Custom)
    r.setZoomFactor(1.5)
    r.jump(4)
    wait(app)
    r.verticalScrollBar().setValue(r.verticalScrollBar().value()+125)
    wait(app)
    saved=r.state()
    w.close_tab(0)
    wait(app)
    assert w._on_home and not w.readers
    row=w.store.history()[0]
    assert row['page']==4
    w.open_recent(row)
    wait(app)
    reopened=w.active
    assert not w._on_home
    assert reopened.zoomFactor()==1.5
    assert reopened.verticalScrollBar().value()==saved['vertical']
    w.close()


def test_home_recent_locate_and_filter(app,pdf,technical_pdf,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    w=Window(Store(tmp_path/'locate.db'),restore=False)
    w.show()
    w.store.record_history(pdf,3)
    missing=tmp_path/'missing.pdf'
    w.store.record_history(missing,2)
    w.show_home()
    w.home.filter.setText('missing')
    assert sum(not w.home.listing.item(i).isHidden() for i in range(2))==1
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *args,**kwargs:(str(technical_pdf),''))
    w.open_recent(w.store.recent(missing))
    wait(app)
    assert w.active.path==str(technical_pdf)
    assert w.active.pageNavigator().currentPage()==2
    assert w.store.recent(missing) is None
    w.close()


def test_settings_cancel_and_apply_and_home_startup(app,pdf,tmp_path):
    store=Store(tmp_path/'prefs.db')
    w=Window(store,restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    dialog=SettingsDialog(store,w)
    dialog.theme.setCurrentText('Light')
    dialog.reject()
    assert store.get('theme')=='Sepia'
    dialog=SettingsDialog(store,w)
    dialog.theme.setCurrentText('Light')
    dialog.fit.setCurrentText('Fit Width')
    dialog.speed.setCurrentText('Gentle')
    dialog.startup.setCurrentIndex(1)
    dialog.preserve.setChecked(False)
    dialog.height.setValue(45)
    w.apply_settings(dialog.values())
    assert w.theme_name=='Light' and not r.effect.isEnabled()
    assert r.zoom_speed==.65 and r.ruler_height==45
    w.close()
    restarted=Window(store,restore=True)
    restarted.show()
    wait(app)
    assert restarted._on_home and not restarted.readers
    assert restarted.home.listing.count()==1
    recent=restarted.store.history()[0]
    restarted.open_recent(recent)
    wait(app)
    assert restarted.active.path==str(pdf)
    restarted.close()


def test_history_schema_migration_and_reopen_does_not_erase_position(tmp_path,pdf):
    path=tmp_path/'legacy.db'
    db=sqlite3.connect(path)
    db.executescript('CREATE TABLE history(path TEXT PRIMARY KEY,page INTEGER,x REAL,y REAL,visited TEXT);')
    db.execute("INSERT INTO history VALUES(?,4,0,10,'2026-10-19')",(str(pdf),))
    db.commit()
    db.close()
    store=Store(path)
    assert store.recent(pdf)['page']==4
    store.record_history(pdf)
    assert store.recent(pdf)['page']==4
    store.record_history(pdf,5,0,90,state=dict(path=str(pdf),page=5,zoom=1.6))
    store.relocate(str(pdf),str(tmp_path/'moved.pdf'))
    moved=store.recent(tmp_path/'moved.pdf')
    assert moved['state']['zoom']==1.6 and moved['state']['path']==str(tmp_path/'moved.pdf')


def test_light_and_sepia_preserve_alpha_and_colored_diagrams(app):
    image=QImage(4,1,QImage.Format.Format_RGBA8888)
    colors=[QColor('white'),QColor('black'),QColor('#1255cc'),QColor(15,15,15,80)]
    for i,color in enumerate(colors): image.setPixelColor(i,0,color)
    assert recolor(image,'Light')==image
    assert recolor(image,'Original')==image
    toned=recolor(image,'Sepia')
    assert toned.pixelColor(0,0).name()=='#faf1d9'
    assert toned.pixelColor(1,0).name()=='#634f38'
    assert toned.pixelColor(2,0)==colors[2]
    assert toned.pixelColor(3,0)==colors[3]


def test_toolbar_does_not_rewrite_page_entry_on_every_scroll(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'sync.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    changed=[]
    w.page.lineEdit().textChanged.connect(changed.append)
    w.page.lineEdit().setFocus()
    w.page.setCurrentText('#6')
    for _ in range(15):
        r.verticalScrollBar().setValue(r.verticalScrollBar().value()+3)
    wait(app,80)
    assert w.page.currentText()=='#6'
    assert changed==['#6']
    w.go_page()
    wait(app)
    assert r.pageNavigator().currentPage()==5
    w.close()


def test_qt_pinch_event_and_navigation_during_pending_zoom(app,pdf,tmp_path):
    from PySide6.QtWidgets import QPinchGesture,QGestureEvent
    w=Window(Store(tmp_path/'qt-pinch.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    r.jump(2)
    wait(app)
    before=r.effective_zoom()
    point=QPointF(r.viewport().rect().center())
    gesture=QPinchGesture()
    gesture.setCenterPoint(point)
    gesture.setLastScaleFactor(1)
    gesture.setScaleFactor(1.25)
    event=QGestureEvent([gesture])
    QApplication.sendEvent(r.viewport(),event)
    wait(app,80)
    assert r.zoomFactor()==pytest.approx(before*1.25)
    wheel(r,point)
    r.jump(5)
    wait(app,80)
    assert r.pageNavigator().currentPage()==5
    w.close()


def test_home_session_and_closing_tabs_on_home(app,pdf,technical_pdf,tmp_path):
    store=Store(tmp_path/'home-session.db')
    w=Window(store,restore=False)
    w.show()
    w.open_pdf(pdf)
    w.open_pdf(technical_pdf)
    wait(app)
    w.show_home()
    w.close_tab(1)
    wait(app)
    assert w._on_home and len(w.readers)==1
    w.close()
    restarted=Window(store,restore=True)
    restarted.show()
    wait(app)
    assert restarted._on_home and len(restarted.readers)==1
    restarted.tab_clicked(restarted.tabs.currentIndex())
    wait(app)
    assert not restarted._on_home and restarted.active is restarted.readers[0]
    assert restarted.page.isEnabled()
    restarted.close()


@pytest.mark.parametrize('theme,paper,canvas',[('Light','#ffffff','#f2f2f2'),('Sepia','#faf1d9','#faf1d9')])
def test_page_tones_do_not_recolor_canvas_or_scrollbars(app,technical_pdf,tmp_path,theme,paper,canvas):
    w=Window(Store(tmp_path/'tone-canvas.db'),restore=False)
    w.show()
    r=w.open_pdf(technical_pdf)
    wait(app)
    w.change_theme(theme)
    wait(app)
    image=w.grab().toImage()
    point=r.point_in_view(0,QPointF(300,250)).toPoint()
    page_pixel=r.viewport().mapTo(w,point)
    canvas_pixel=r.viewport().mapTo(w,QPoint(2,200))
    assert image.pixelColor(page_pixel).name()==paper
    assert image.pixelColor(canvas_pixel).name()==canvas
    w.close()


def test_default_fit_applies_to_new_files_and_cancelling_zoom_on_close(app,pdf,technical_pdf,tmp_path):
    from PySide6.QtCore import QCoreApplication,QEvent
    w=Window(Store(tmp_path/'new-fit.db'),restore=False)
    w.show()
    first=w.open_pdf(pdf)
    wait(app)
    old_mode=first.zoomMode()
    w.apply_settings(dict(default_fit='Fit Width',zoom_speed='Fast'))
    assert first.zoomMode()==old_mode and first.zoom_speed==1.5
    second=w.open_pdf(technical_pdf)
    wait(app)
    assert second.zoomMode()==second.ZoomMode.FitToWidth
    point=QPointF(second.viewport().rect().center())
    wheel(second,point)
    w.close_tab(1)
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    wait(app,80)
    assert len(w.readers)==1 and w.active is first
    w.close()
