"""Reading palettes change real PDF pages without recoloring the shared header."""
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor,QPalette
from test_reader import app,pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.theme import COLORS,INK,theme_tunings
from mellow.style import CHROME


def test_rendered_header_fields_icons_and_active_tab_stay_constant_in_split_views(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'chrome.db'),restore=False);w.resize(1180,820);w.show()
    w.open_pdf(pdf)
    other=tmp_path/'Second document.pdf';other.write_bytes(pdf.read_bytes())
    w.open_pdf(other);w.tabs.setCurrentIndex(0);w.split(0,0);w.secondary.rotate_by(90);wait(app,80)
    expected=None
    for theme in ('Sepia','Dark','Light','Black','Dark','Sepia'):
        w.change_theme(theme);wait(app,80)
        tab=w.tabstrip.grab().toImage();bar=w.toolbar.grab().toImage()
        assert tab.pixelColor(tab.width()-3,tab.height()-5)==QColor(CHROME['bg'])
        assert bar.pixelColor(bar.width()-3,bar.height()//2)==QColor(CHROME['surface'])
        selected=w.tabs.tabRect(w.tabs.currentIndex())
        point=w.tabs.mapTo(w.tabstrip,QPoint(selected.left()+5,selected.bottom()-5))
        assert tab.pixelColor(point)==QColor(CHROME['active_tab'])
        inactive=w.tabs.tabRect(1)
        point=w.tabs.mapTo(w.tabstrip,QPoint(inactive.left()+5,inactive.bottom()-5))
        assert tab.pixelColor(point)==QColor(CHROME['tab'])
        fields=[w.page.lineEdit(),w.fit.lineEdit(),w.inline_search.text]
        sample=([field.palette().color(QPalette.ColorRole.Text).name() for field in fields],
                [field.palette().color(QPalette.ColorRole.Base).name() for field in fields],
                w.home_action.icon().pixmap(24,24).toImage(),
                w.inline_search.next.icon().pixmap(24,24).toImage())
        if expected is None:expected=sample
        else:assert sample==expected
        assert all(reader.effect.theme==theme for reader in [w.readers[0],w.secondary])
    w.close()


def test_retired_palette_keeps_saved_reading_tuning_and_new_choice(app,pdf,tmp_path):
    store=Store(tmp_path/'rose.db')
    store.set('theme','Rose');store.set('theme_tuning',{'Rose':dict(warmth=12,contrast=7)})
    w=Window(store,restore=False);w.show();r=w.open_pdf(pdf);wait(app,80)
    assert w.theme_name=='Black' and store.get('theme')=='Black'
    assert list(COLORS)==['Light','Sepia','Dark','Black']
    from mellow.settings import SettingsDialog
    dialog=SettingsDialog(store,w)
    assert [dialog.theme.itemText(i) for i in range(dialog.theme.count())]==list(COLORS)
    dialog.reject();dialog.deleteLater()
    assert not hasattr(w,'themes')
    assert r.effect.warmth==12 and r.effect.contrast==7
    assert theme_tunings({'Rose':{'warmth':12},'Black':{'warmth':-3}})['Black']['warmth']==-3
    w.close()


def test_new_neutral_and_black_ink_contrast():
    def luminance(hex_color):
        rgb=QColor(hex_color).getRgb()[:3]
        return sum((v/255/12.92 if v/255<=.04045 else ((v/255+.055)/1.055)**2.4)*weight
                   for v,weight in zip(rgb,(.2126,.7152,.0722)))
    for theme in ('Black','Dark'):
        a,b=sorted((luminance(COLORS[theme][0]),luminance(INK[theme])))
        assert (b+.05)/(a+.05)>=7
    for ink,paper in ((CHROME['text'],CHROME['active_tab']),
                      (CHROME['muted'],CHROME['tab']),
                      (CHROME['text'],CHROME['input'])):
        a,b=sorted((luminance(ink),luminance(paper)))
        assert (b+.05)/(a+.05)>=4.5
    assert COLORS['Sepia']==('#faf1d9','#faf1d9')
    assert COLORS['Light']==('#ffffff','#f2f2f2')


def test_black_paper_stays_pure_with_saved_warmth(app,tmp_path):
    from mellow.theme import canvas_color,tone_colors
    from mellow.settings import SettingsDialog
    for warmth in (-50,0,50):
        assert canvas_color('Black',warmth,30)=='#000000'
        assert tone_colors('Black',warmth,30)[0]==(0,0,0)
    dialog=SettingsDialog(Store(tmp_path/'black-settings.db'))
    assert [dialog.theme.itemText(i) for i in range(dialog.theme.count())]==list(COLORS)
    dialog.theme.setCurrentText('Black')
    assert not dialog.warmth.isEnabled() and dialog.contrast.isEnabled()
    assert dialog.preview.image.pixelColor(0,0)==QColor('#000000')
    dialog.reject()
