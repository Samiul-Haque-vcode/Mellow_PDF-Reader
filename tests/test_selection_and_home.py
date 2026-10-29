"""User flows for copied PDF text, Home tools and Favorites."""
from pathlib import Path
import pytest
from PySide6.QtCore import Qt,QPoint,QPointF,QEvent,QCoreApplication
from PySide6.QtGui import QMouseEvent,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from test_reader import app,pdf,technical_pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.icons import application_icon,icon,ASSETS


def text_point(reader,page,index,right=False):
    part=reader.document().getSelectionAtIndex(page,index,1)
    rect=part.bounds()[0].boundingRect()
    point=QPointF(rect.right()+.5 if right else rect.left(),rect.center().y())
    return reader.point_in_view(page,point).toPoint()


def mouse_move(reader,point):
    event=QMouseEvent(QEvent.Type.MouseMove,QPointF(point),QPointF(reader.viewport().mapToGlobal(point)),
                      Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(reader.viewport(),event)


def drag(reader,first,last):
    QTest.mousePress(reader.viewport(),Qt.MouseButton.LeftButton,pos=first)
    mouse_move(reader,last)
    QTest.mouseRelease(reader.viewport(),Qt.MouseButton.LeftButton,pos=last)


def test_drag_copy_and_word_selection(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'selection.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    start=text_point(r,0,0)
    end=text_point(r,0,13,True)
    drag(r,start,end)
    wait(app,40)
    assert r.selected_text().strip()=='Mellow chapter'
    QTest.keyClick(r,Qt.Key.Key_C,Qt.KeyboardModifier.ControlModifier)
    assert QApplication.clipboard().text().strip()=='Mellow chapter'
    r.clear_selection()
    QTest.mouseDClick(r.viewport(),Qt.MouseButton.LeftButton,pos=text_point(r,0,2))
    assert r.selected_text()=='Mellow'
    QTest.keyClick(r,Qt.Key.Key_C,Qt.KeyboardModifier.ControlModifier)
    assert QApplication.clipboard().text()=='Mellow'
    w.close()


@pytest.mark.parametrize('reverse',[False,True])
def test_multiline_cross_page_selection(app,pdf,tmp_path,reverse):
    w=Window(Store(tmp_path/'cross-page.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    first,last=text_point(r,0,0),text_point(r,1,15,True)
    if reverse: first,last=last,first
    # This tests page-coordinate ranges even when the pointer is past the viewport.
    drag(r,first,last)
    wait(app,30)
    copied=r.selected_text()
    assert 'Mellow chapter 1' in copied
    assert 'Mellow chapter 2' in copied
    assert r.copy_selection() and QApplication.clipboard().text()==copied
    w.close()


def test_copy_is_independent_in_split_and_line_edit(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'split-copy.db'),restore=False)
    w.show()
    a=w.open_pdf(pdf)
    wait(app)
    w.split(0,0)
    wait(app)
    b=w.secondary
    a.select_page_text(0)
    b.select_page_text(5)
    a.setFocus()
    QTest.keyClick(a,Qt.Key.Key_C,Qt.KeyboardModifier.ControlModifier)
    assert 'chapter 1' in QApplication.clipboard().text()
    b.setFocus()
    QTest.keyClick(b,Qt.Key.Key_C,Qt.KeyboardModifier.ControlModifier)
    assert 'chapter 6' in QApplication.clipboard().text()
    assert 'chapter 1' in a.selected_text()
    w.page.lineEdit().setFocus()
    w.page.setCurrentText('#7')
    w.page.lineEdit().selectAll()
    QTest.keyClick(w.page.lineEdit(),Qt.Key.Key_C,Qt.KeyboardModifier.ControlModifier)
    assert QApplication.clipboard().text()=='#7'
    w.close()


@pytest.mark.parametrize('theme',['Light','Sepia','Black','Dark'])
def test_selection_survives_theme_and_zoom_and_can_clear(app,pdf,tmp_path,theme):
    w=Window(Store(tmp_path/'selection-theme.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    r.select_page_text(0)
    text=r.selected_text()
    w.change_theme(theme)
    r.zoom_by(1.2)
    wait(app)
    assert r.selected_text()==text
    assert not w.grab().isNull()
    QTest.keyClick(r,Qt.Key.Key_Escape)
    assert r.selected_text()=='' and not r.copy_action.isEnabled()
    w.close()


def test_image_only_page_does_not_replace_clipboard(app,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'scan.db'),restore=False)
    w.show()
    r=w.open_pdf(technical_pdf)
    wait(app)
    QApplication.clipboard().setText('keep existing text')
    r.select_page_text(4)
    assert r.selected_text()=='' and not r.copy_action.isEnabled()
    assert not r.copy_selection()
    assert QApplication.clipboard().text()=='keep existing text'
    w.close()


def test_unicode_pdf_text_copy(app,tmp_path):
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import reportlab
    sample='Résumé — café λ + x² = α ∫ f(x) dx + a₁ − β'
    candidates=[('C:/Windows/Fonts/cambria.ttc',1),('C:/Windows/Fonts/cambria.ttc',0),
                ('C:/Windows/Fonts/cambria.ttf',0),('C:/Windows/Fonts/calibri.ttf',0),
                ('C:/Windows/Fonts/segoeui.ttf',0),('C:/Windows/Fonts/times.ttf',0),
                ('C:/Windows/Fonts/arial.ttf',0),('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',0)]
    supported=None
    for filename,index in candidates:
        if not Path(filename).is_file():continue
        try:font=TTFont('MellowUnicode',filename,subfontIndex=index)
        except Exception:continue
        if all(char.isspace() or font.face.charToGlyph.get(ord(char),0) for char in sample):
            supported=font;break
    if supported is None:pytest.skip('A font with all fixture glyphs, including subscript one, is required')
    pdfmetrics.registerFont(supported)
    path=tmp_path/'unicode.pdf'
    canvas=Canvas(str(path))
    canvas.setFont('MellowUnicode',14)
    canvas.drawString(40,700,sample)
    canvas.save()
    w=Window(Store(tmp_path/'unicode.db'),restore=False)
    w.show()
    r=w.open_pdf(path)
    wait(app)
    r.select_page_text(0)
    assert r.copy_selection()
    text=QApplication.clipboard().text()
    assert 'café' in text and 'λ' in text and 'x²' in text
    assert '∫' in text and 'a₁' in text and '−' in text
    w.close()


def test_dragging_link_selects_text_without_preview(app,technical_pdf,tmp_path):
    w=Window(Store(tmp_path/'link-selection.db'),restore=False)
    w.show()
    r=w.open_pdf(technical_pdf)
    wait(app)
    all_text=r.document().getAllText(0).text()
    start=all_text.index('Linked')
    drag(r,text_point(r,0,start),text_point(r,0,start+16,True))
    assert 'Linked Figure' in r.selected_text()
    assert not w.popups
    w.close()


def test_home_favorites_search_and_open_saved_location(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'favorite-home.db'),restore=False)
    w.store.add('favorite',str(pdf),3,'Important equation')
    w.show()
    w.show_home()
    assert w.home.favorites.count()==1
    assert 'Important equation' in w.home.favorites.item(0).text()
    w.home.filter.setText('equation')
    assert not w.home.favorites.item(0).isHidden()
    w.home.open_favorite(w.home.favorites.item(0))
    wait(app)
    assert not w._on_home and w.active.pageNavigator().currentPage()==3
    assert w.toolbar.isVisible()
    w.show_home()
    assert not w.toolbar.isVisible() and w.tabstrip.isVisible()
    w.close()


def test_extract_tool_from_home_without_open_document(app,pdf,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QMessageBox,QDialog
    from mellow.tool_dialog import ToolDialog
    from pypdf import PdfReader
    w=Window(Store(tmp_path/'extract-home.db'),restore=False)
    w.show()
    output=tmp_path/'extracted.pdf'
    def preview_then_save(dialog):
        dialog.add_paths([str(pdf)])
        dialog.ranges.setText('2-3')
        for _ in range(200):
            wait(app,20)
            if dialog.current_output and not dialog._job: break
        assert dialog.document.pageCount()==2
        assert dialog.save_to(output)
        for _ in range(200):
            wait(app,20)
            if dialog.saved_path and not dialog._job: break
        assert dialog._disposed
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(ToolDialog,'exec',preview_then_save)
    monkeypatch.setattr(QMessageBox,'question',lambda *args,**kwargs:QMessageBox.StandardButton.No)
    w.home_tool('extract')
    assert output.exists() and len(PdfReader(output).pages)==2
    assert w._on_home and not w.readers
    w.close()


def test_brand_assets_and_toolbar_actions(app,tmp_path):
    from PIL import Image
    assert not application_icon().pixmap(64,64).isNull()
    assert not icon('copy').isNull()
    assert len(Image.open(ASSETS/'mellow.ico').info['sizes'])>=6
    w=Window(Store(tmp_path/'brand.db'),restore=False)
    assert not w.windowIcon().isNull()
    assert w.home.tools.keys()=={'extract','merge','images'}
    assert all(not action.icon().isNull() for action in w._toolbar_icon_names)
    w.close()


def test_drag_autoscroll_stops_and_shift_click_extends(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'scroll-selection.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    r.setZoomMode(r.ZoomMode.Custom)
    r.setZoomFactor(1)
    r.jump(0)
    wait(app)
    start=text_point(r,0,0)
    QTest.mousePress(r.viewport(),Qt.MouseButton.LeftButton,pos=start)
    outside=r.viewport().rect().bottomRight()+QPoint(0,24)
    mouse_move(r,outside)
    before=r.verticalScrollBar().value()
    wait(app,140)
    assert r.verticalScrollBar().value()>before
    QTest.mouseRelease(r.viewport(),Qt.MouseButton.LeftButton,pos=outside)
    assert not r._selection_timer.isActive()
    r.jump(0)
    wait(app)
    QTest.mouseClick(r.viewport(),Qt.MouseButton.LeftButton,pos=text_point(r,0,0))
    QTest.mouseClick(r.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.ShiftModifier,pos=text_point(r,0,13,True))
    assert r.selected_text().strip()=='Mellow chapter'
    w.close()
