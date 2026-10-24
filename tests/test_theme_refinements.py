"""Real source rasters, display-only tones and visible overlays in every theme."""
import hashlib
import itertools
import math
import pytest
from reportlab.pdfgen.canvas import Canvas
from PySide6.QtCore import Qt,QPointF
from PySide6.QtGui import QColor,QImage
from test_reader import app,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.theme import recolor,COLORS,canvas_color,overlay_colors
from mellow.references import Target


def luminance(color):
    channels=[value/255 for value in color.getRgb()[:3]]
    return sum((value/12.92 if value<=.04045 else ((value+.055)/1.055)**2.4)*weight
               for value,weight in zip(channels,(.2126,.7152,.0722)))


def contrast(ink,paper):return (luminance(ink)+.05)/(luminance(paper)+.05)


@pytest.mark.parametrize('theme',['Dark','Black'])
@pytest.mark.parametrize('warmth',[-50,0,50])
@pytest.mark.parametrize('strength',[-30,0,30])
def test_dark_chromatic_ink_has_adaptive_contrast_and_readable_colors_stay_exact(app,theme,warmth,strength):
    values=list(itertools.product(range(0,256,32),repeat=3))+[(88,126,149),(31,64,87)]
    image=QImage(len(values),1,QImage.Format.Format_RGBA8888)
    for index,rgb in enumerate(values):image.setPixelColor(index,0,QColor(*rgb))
    dark=recolor(image,theme,True,warmth,strength);paper=QColor(canvas_color(theme,warmth,strength))
    lifted=0
    for index,rgb in enumerate(values):
        if max(rgb)-min(rgb)<35:continue
        source=image.pixelColor(index,0);toned=dark.pixelColor(index,0)
        if contrast(source,paper)>=4.5:assert toned==source
        else:
            assert contrast(toned,paper)>=4.5
            assert all(a<=b for a,b in zip(rgb,toned.getRgb()[:3]))
            lifted+=1
    assert lifted
    transparent=QImage(1,1,QImage.Format.Format_RGBA8888);transparent.setPixelColor(0,0,QColor(31,64,87,120))
    assert recolor(transparent,theme,True,warmth,strength)==transparent
    assert recolor(image,'Light',True,warmth,strength)==image
    assert recolor(image,'Original',False,warmth,strength)==image


@pytest.fixture
def colors_pdf(tmp_path):
    path=tmp_path/'theme-colors.pdf';c=Canvas(str(path),pagesize=(420,540))
    c.setFillColorRGB(31/255,64/255,87/255);c.setFont('Helvetica-Bold',18)
    c.drawString(30,490,'Bold colored heading')
    c.setFillColorRGB(0,0,0);c.setFont('Helvetica',12)
    c.drawString(30,455,'Searchable scientific text and selection.')
    c.setFillColorRGB(88/255,126/255,149/255);c.rect(30,280,95,85,fill=1,stroke=0)
    c.setFillColorRGB(68/255,170/255,221/255);c.rect(150,280,95,85,fill=1,stroke=0)
    c.save();return path


def ready(app,reader):
    for _ in range(100):
        reader.viewport().update();wait(app,20)
        tasks=reader.rotated_pages.tasks() if reader.custom_rendering else []
        if not reader.custom_rendering or tasks and all(key in reader.rotated_pages.cache for key,_,_ in tasks):return
    pytest.fail('Source PDF raster was not ready')


def pixel(reader,point):
    pos=reader.point_in_view(0,point).toPoint()
    image=reader.grab().toImage()
    pos+=reader.viewport().pos()
    assert image.rect().contains(pos)
    return image.pixelColor(pos)


@pytest.mark.parametrize('theme',list(COLORS))
@pytest.mark.parametrize('rotation',[0,90])
def test_real_pdf_bold_diagrams_search_and_selection_in_all_themes(app,colors_pdf,tmp_path,theme,rotation):
    digest=hashlib.sha256(colors_pdf.read_bytes()).hexdigest()
    w=Window(Store(tmp_path/(theme+str(rotation)+'.db')),restore=False);w.resize(950,760);w.show()
    reader=w.open_pdf(colors_pdf);reader.set_page_layout('single');reader.set_rotation(rotation);w.change_theme(theme)
    ready(app,reader);wait(app,100)
    source=QColor(88,126,149);bright=QColor(68,170,221)
    low=pixel(reader,QPointF(65,215));high=pixel(reader,QPointF(185,215))
    paper=pixel(reader,QPointF(370,250))
    assert paper==QColor(COLORS[theme][0])
    assert high==bright
    if theme in ('Dark','Black'):
        assert contrast(low,paper)>=4.5
        if contrast(source,paper)<4.5:assert low!=source
        else:assert low==source
    else:assert low==source
    # The bold heading uses exactly the same compositor as the color blocks.
    bounds=reader.document().getSelectionAtIndex(0,0,len('Bold colored heading')).boundingRectangle()
    pos=reader.point_in_view(0,bounds.center()).toPoint()+reader.viewport().pos()
    image=reader.grab().toImage()
    heading=[image.pixelColor(pos.x()+x,pos.y()+y) for x in range(-8,9) for y in range(-5,6)
             if image.rect().contains(pos.x()+x,pos.y()+y)]
    assert any(color!=paper for color in heading)
    reader.search.setSearchString('scientific')
    for _ in range(100):
        if reader.search.rowCount()==1:break
        wait(app,20)
    reader.visit_search(0);reader.select_page_text(0);wait(app,80)
    before_overlay=reader.grab().toImage();result=reader.search.resultAtIndex(0)
    rect=result.rectangles()[0]
    point=reader.point_in_view(0,rect.topLeft()).toPoint()+reader.viewport().pos()
    outline=overlay_colors(theme)[2]
    assert any(before_overlay.pixelColor(point.x()+x,point.y()+y)==outline for x in range(-4,5) for y in range(-4,5)
               if before_overlay.rect().contains(point.x()+x,point.y()+y))
    reader.search.setSearchString('');wait(app,40);selected=reader.grab().toImage()
    reader.clear_selection();wait(app,40)
    assert selected!=reader.grab().toImage()
    w.preview(reader,Target(0));wait(app,80)
    assert w.popups[-1].reader.effect.theme=='Light' and not w.popups[-1].reader.effect.isEnabled()
    w.close();wait(app,20)
    assert hashlib.sha256(colors_pdf.read_bytes()).hexdigest()==digest
