"""The supplied eReader reference has one continuous, warm reading field."""
from PySide6.QtCore import QPoint,QPointF
from PySide6.QtGui import QColor,QImage
from PySide6.QtWidgets import QFrame
from PySide6.QtPdfWidgets import QPdfView
import pytest
from test_reader import app,pdf,technical_pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.theme import COLORS,INK,normalize_theme,recolor


@pytest.mark.parametrize('theme',['Sepia','Black','Dark'])
def test_paper_canvas_and_page_gap_are_one_shade(app,pdf,tmp_path,theme):
    w=Window(Store(tmp_path/'continuous.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    r.zoom_to(.4)
    wait(app)
    w.change_theme(theme)
    wait(app)
    assert r.frameShape()==QFrame.Shape.NoFrame
    image=w.grab().toImage()
    layouts=r.layout_pages()
    paper=COLORS[theme][0]
    rect=layouts[0][1]
    # Blank source paper, both outside margins, and the actual inter-page gap.
    points=[r.point_in_view(0,QPointF(300,250)).toPoint(),QPoint(2,180),
            QPoint(r.viewport().width()-3,180),QPoint(int(rect.center().x()),int(rect.bottom()+r.pageSpacing()/2))]
    for point in points:
        assert r.viewport().rect().contains(point)
        pixel=r.viewport().mapTo(w,point)
        assert image.pixelColor(pixel).name()==paper
    w.close()


@pytest.mark.parametrize('legacy',['Paper Gray','Rose','Mist','Sage'])
def test_legacy_gray_migrates_and_new_theme_is_persisted(app,pdf,tmp_path,legacy):
    store=Store(tmp_path/'migration.db')
    store.set('theme',legacy)
    w=Window(store,restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    assert normalize_theme('Paper Gray')=='Black'
    assert w.theme_name=='Black' and store.get('theme')=='Black'
    from mellow.settings import SettingsDialog
    dialog=SettingsDialog(store,w)
    assert dialog.theme.findText('Paper Gray')==-1 and dialog.theme.findText('Black')>=0
    assert dialog.theme.findText('Rose')==-1
    dialog.reject();dialog.deleteLater()
    assert r.effect.theme=='Black'
    w.close()


@pytest.mark.parametrize('theme',['Sepia','Black','Dark'])
def test_soft_palette_ink_and_preserved_diagram_colors(app,theme):
    image=QImage(3,1,QImage.Format.Format_RGBA8888)
    for i,color in enumerate(['white','black','#1255cc']): image.setPixelColor(i,0,QColor(color))
    toned=recolor(image,theme)
    assert toned.pixelColor(0,0).name()==COLORS[theme][0]
    assert toned.pixelColor(1,0).name()==INK[theme]
    if theme not in ('Dark','Black'):assert toned.pixelColor(2,0)==image.pixelColor(2,0)
    else:assert toned.pixelColor(2,0).lightness()>image.pixelColor(2,0).lightness()
    assert recolor(toned,'Light')==toned
    assert recolor(image,'Light')==image
