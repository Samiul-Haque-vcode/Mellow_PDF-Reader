"""Caption interaction, first-frame entry and low-contrast scientific headings."""
import pytest
from PySide6.QtCore import Qt,QPoint,QSize
from PySide6.QtGui import QColor,QImage
from PySide6.QtTest import QTest,QSignalSpy
from test_reader import app,pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.theme import recolor,COLORS


@pytest.mark.parametrize('screen',['home','reader','split'])
def test_menu_opens_after_release_and_keyboard_with_open_tabs(app,pdf,tmp_path,screen):
    w=Window(Store(tmp_path/'menu.db'),restore=False);w.show();w.open_pdf(pdf);wait(app)
    if screen=='home':w.show_home()
    elif screen=='split':w.split(0,0)
    wait(app)
    button=w.more_button;menu=w.more_menu;shown=QSignalSpy(menu.aboutToShow)
    for _ in range(3):
        QTest.mousePress(button,Qt.MouseButton.LeftButton)
        wait(app,10);assert not menu.isVisible()
        QTest.mouseRelease(button,Qt.MouseButton.LeftButton)
        wait(app,10);assert menu.isVisible()
        QTest.keyClick(menu,Qt.Key.Key_Escape);wait(app,10)
        assert not menu.isVisible() and not button.isDown()
    button.setFocus();QTest.keyClick(button,Qt.Key.Key_Space);wait(app,10)
    assert menu.isVisible() and shown.count()==4
    menu.close();w.close()


def test_caption_buttons_and_tabs_claim_client_input_but_blank_caption_does_not(app,pdf,tmp_path,monkeypatch):
    from mellow import caption
    monkeypatch.setattr(caption,'supported',lambda:True)
    w=Window(Store(tmp_path/'hit.db'),restore=False);w.showMaximized();w.open_pdf(pdf);wait(app)
    for widget,point in [(w.more_button,w.more_button.rect().center()),
                         (w.add_tab_button,w.add_tab_button.rect().center()),
                         (w.tabs,w.tabs.tabRect(0).center())]:
        assert w.caption_tabs.interactive_at(widget.mapTo(w,point))
    blank=QPoint(w.tabstrip.width()-w.tabstrip.layout().contentsMargins().right()-8,15)
    assert not w.caption_tabs.interactive_at(w.tabstrip.mapTo(w,blank))
    w.fullscreen();wait(app)
    assert not w.caption_tabs.interactive_at(QPoint(45,15))
    w.fullscreen();wait(app);w.close()


def test_fullscreen_final_geometry_restores_position_before_returning(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'entry.db'),restore=False);w.show();r=w.open_pdf(pdf);wait(app)
    r.jump(3);wait(app);old=r.state()
    w.fullscreen()
    if w.size()==w._fullscreen_target_size:
        assert w._fullscreen_snapshots is None and w.updatesEnabled()
        now=r.state()
        assert now['anchor_page']==old['anchor_page'] and abs(now['y']-old['y'])<2
    else:wait(app,180) # platform reports final bounds asynchronously
    w.fullscreen();wait(app);w.close()


def contrast(a,b):
    def luminance(color):
        channels=color.getRgbF()[:3]
        return sum((v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4)*weight
                   for v,weight in zip(channels,(.2126,.7152,.0722)))
    a,b=sorted((luminance(a),luminance(b)))
    return (b+.05)/(a+.05)


def test_dark_heading_colors_gain_contrast_while_bright_figure_colors_stay_exact(app):
    colors=['#1f4057','#665035','#1255cc','#dfba44','#44aadd','black','white']
    image=QImage(len(colors),1,QImage.Format.Format_RGBA8888)
    for i,color in enumerate(colors):image.setPixelColor(i,0,QColor(color))
    dark=recolor(image,'Dark',True);paper=QColor(COLORS['Dark'][0])
    for i in range(3):assert contrast(dark.pixelColor(i,0),paper)>4.5
    for i in (3,4):assert dark.pixelColor(i,0)==image.pixelColor(i,0)
    assert recolor(image,'Light')==image


def test_light_canvas_does_not_retain_other_themes_in_split_views(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'light.db'),restore=False);w.show();w.open_pdf(pdf);w.split(0,0);wait(app)
    w.secondary.rotate_by(90)
    for previous in ['Sepia','Black','Dark']:
        w.change_theme(previous);wait(app,40)
        w.change_theme('Light');wait(app,80)
        image=w.grab().toImage()
        for reader in [w.readers[0],w.secondary]:
            point=reader.viewport().mapTo(w,QPoint(2,100))
            assert image.pixelColor(point)==QColor(COLORS['Light'][1])
    w.close()
