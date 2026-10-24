"""The scrollbar context menu stays small and belongs to the clicked pane."""
import pytest
from PySide6.QtCore import Qt,QPoint,QTimer
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QApplication,QMenu
from PySide6.QtTest import QTest
from test_reader import app,pdf,wait
from mellow.app import Window
from mellow.pages import PagesPanel
from mellow.storage import Store


@pytest.mark.parametrize('orientation',['vertical','horizontal'])
@pytest.mark.parametrize('rotated',[False,True])
def test_scrollbar_menu_order_and_real_edges(app,pdf,tmp_path,orientation,rotated):
    w=Window(Store(tmp_path/'edges.db'),restore=False);w.resize(900,700);w.show()
    r=w.open_pdf(pdf);r.zoom_to(2.5)
    if rotated:r.rotate_by(90)
    wait(app,80)
    bar=r.verticalScrollBar() if orientation=='vertical' else r.horizontalScrollBar()
    assert bar.contextMenuPolicy()==Qt.ContextMenuPolicy.CustomContextMenu and bar.maximum()>bar.minimum()
    bar.setValue((bar.minimum()+bar.maximum())//2)
    menu=r.scrollbar_menu(bar)
    assert [a.text() for a in menu.actions()]==['Start','Scroll here','Page preview','End']
    menu.actions()[0].trigger();wait(app,20)
    assert bar.value()==bar.minimum()
    menu.deleteLater();menu=r.scrollbar_menu(bar)
    assert not menu.actions()[0].isEnabled()
    menu.actions()[-1].trigger();wait(app,20)
    assert bar.value()==bar.maximum()
    menu.deleteLater();menu=r.scrollbar_menu(bar)
    assert not menu.actions()[-1].isEnabled()
    assert w.pages_action not in w.reading_menu.actions()
    menu.deleteLater();w.close()


def test_native_context_event_opens_preview_for_clicked_split_pane(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'split-context.db'),restore=False);w.resize(1200,800);w.show()
    first=w.open_pdf(pdf);w.split(0,0);wait(app,60)
    second=w.secondary;second.jump(3);w.focus_reader(first);wait(app,30)
    before=first.state(include_history=True);seen=[]
    bar=second.verticalScrollBar()
    def close_preview():
        panels=[d for d in w.findChildren(PagesPanel) if d.isVisible()]
        seen.extend(panels)
        for panel in panels:
            assert panel.reader is second and panel.start_page==3
            panel.reject()
    def choose_preview():
        menu=QApplication.activePopupWidget()
        assert isinstance(menu,QMenu)
        assert [a.text() for a in menu.actions()]==['Start','Scroll here','Page preview','End']
        QTimer.singleShot(50,close_preview)
        QTest.mouseClick(menu,Qt.MouseButton.LeftButton,pos=menu.actionGeometry(menu.actions()[2]).center())
    QTimer.singleShot(40,choose_preview)
    point=QPoint(bar.width()//2,bar.height()//2)
    QApplication.sendEvent(bar,QContextMenuEvent(QContextMenuEvent.Reason.Mouse,point,bar.mapToGlobal(point)))
    assert len(seen)==1 and seen[0].grid.released
    assert w.active is second and first.state(include_history=True)==before
    assert second.pageNavigator().currentPage()==3
    w.close()


def test_closing_source_tab_during_preview_unwinds_cleanly(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'close-preview.db'),restore=False);w.show();w.open_pdf(pdf);wait(app,30)
    seen=[]
    def close_source():
        seen.extend(d for d in w.findChildren(PagesPanel) if d.isVisible())
        w.close_tab(0)
    QTimer.singleShot(40,close_source)
    w.page_thumbnails();wait(app,20)
    assert len(seen)==1 and not w.readers and w.active is None
    w.close()


@pytest.mark.parametrize('orientation',['vertical','horizontal'])
def test_scroll_here_uses_original_track_position_and_cancels_pending_zoom(app,pdf,tmp_path,orientation):
    from PySide6.QtWidgets import QStyle,QStyleOptionSlider
    w=Window(Store(tmp_path/'scroll-here.db'),restore=False);w.resize(900,700);w.show()
    r=w.open_pdf(pdf);r.zoom_to(2.5);wait(app,80)
    bar=r.verticalScrollBar() if orientation=='vertical' else r.horizontalScrollBar()
    option=QStyleOptionSlider();bar.initStyleOption(option)
    groove=bar.style().subControlRect(QStyle.ComplexControl.CC_ScrollBar,option,QStyle.SubControl.SC_ScrollBarGroove,bar)
    slider=bar.style().subControlRect(QStyle.ComplexControl.CC_ScrollBar,option,QStyle.SubControl.SC_ScrollBarSlider,bar)
    point=groove.center()
    if orientation=='vertical':point.setY(groove.top()+round((groove.height()-slider.height())*.75)+slider.height()//2)
    else:point.setX(groove.left()+round((groove.width()-slider.width())*.75)+slider.width()//2)
    menu=r.scrollbar_menu(bar,point)
    r.zoom_by(1.2,smooth=True)
    assert r._zoom_target is not None
    menu.actions()[1].trigger();wait(app,40)
    assert r._zoom_target is None
    fraction=(bar.value()-bar.minimum())/(bar.maximum()-bar.minimum())
    assert abs(fraction-.75)<.02
    menu.deleteLater();w.close()
