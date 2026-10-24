"""Final accepted queue: real text matches, display tones and explicit prose copy."""
import hashlib
import re
import pytest
from reportlab.pdfgen.canvas import Canvas
from PySide6.QtCore import Qt,QModelIndex,QPoint,QPointF,QRectF,QTimer
from PySide6.QtGui import QColor,QImage,QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_reader import app,pdf,technical_pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.search import SearchPanel,SearchDialog
from mellow.settings import SettingsDialog
from mellow.theme import recolor,COLORS,INK,canvas_color,tone_colors,theme_tunings,tuning_values
from mellow.selection import join_paragraph_lines,clean_text
from mellow.references import Target


def done(app,reader,total=None):
    for _ in range(300):
        if reader.search.status()!=reader.search.Status.Searching and (total is None or reader.search.rowCount()==total):break
        wait(app,20)
    assert reader.search.status()!=reader.search.Status.Searching
    if total is not None:assert reader.search.rowCount()==total


@pytest.fixture
def search_pdf(tmp_path):
    path=tmp_path/'search.pdf';c=Canvas(str(path),pagesize=(600,800))
    c.drawString(40,750,'Cat cat scatter cat2 CAT. A cat, cats _cat cat_cat.')
    c.showPage();c.drawString(40,750,'A second cat page.');c.showPage()
    c.setFillColorRGB(.2,.5,.7);c.rect(30,30,500,700,fill=1);c.save()
    return path


def test_search_filters_labels_independent_panes_and_scans(app,search_pdf,tmp_path):
    w=Window(Store(tmp_path/'search.db'),restore=False);w.show();r=w.open_pdf(search_pdf);wait(app)
    source=hashlib.sha256(search_pdf.read_bytes()).hexdigest()
    w.apply_numbering(dict(pdf=0,book=30))
    query='Cat cat scatter cat2 CAT. A cat, cats _cat cat_cat. A second cat page.'
    r.search.setSearchString('cat');done(app,r,len(re.findall('cat',query,re.I)))
    assert 'Page 30 · PDF page 1' in r.search.index(0,0).data()
    assert 'scatter' in r.search.index(0,0).data()
    r.visit_search(1);r.search.set_options(whole_words=True)
    assert r.currentSearchResultIndex()==-1
    done(app,r,len(re.findall(r'\bcat\b',query,re.I)))
    r.search.set_options(match_case=True);done(app,r,len(re.findall(r'\bcat\b',query)))
    r.visit_search(r.search.rowCount()-1)
    assert r.pageNavigator().currentPage()==1
    assert not r.search.resultsOnPage(2)
    w.split(0,0);wait(app);other=w.secondary
    assert not other.search.whole_words and not other.search.match_case and other.search.searchString()==''
    other.search.setSearchString('CAT');done(app,other,len(re.findall('cat',query,re.I)))
    assert r.search.searchString()=='cat' and r.search.match_case
    r.search.setSearchString('no such text');done(app,r,0)
    panel=SearchPanel(r,w);panel.show();wait(app)
    assert 'Scanned pages' in panel.status.text() and r.search.rowCount()==0
    panel.reject();assert panel.results.model() is None and not panel._connections
    panel.deleteLater()
    r.search.setSearchString('');assert r.search.rowCount()==0 and r.search.status()==r.search.Status.Null
    w.close();wait(app,20)
    assert not r.search.timer.isActive() and r.search.rowCount()==0
    assert hashlib.sha256(search_pdf.read_bytes()).hexdigest()==source


@pytest.mark.parametrize('angle,layout,crop',[(0,'continuous',(0,0,0,0)),(90,'two',(3,4,3,4)),(270,'single',(5,5,5,5))])
def test_filtered_search_navigation_and_overlay(app,search_pdf,tmp_path,angle,layout,crop):
    w=Window(Store(tmp_path/'geometry.db'),restore=False);w.show();r=w.open_pdf(search_pdf);wait(app)
    r.set_page_layout(layout);r.set_rotation(angle);r.change_crop(crop)
    r.search.setSearchString('cat');r.search.set_options(whole_words=True,match_case=True);done(app,r,3)
    r.visit_search(0);wait(app)
    result=r.search.resultAtIndex(0)
    rect=result.rectangles()[0];point=r.viewport().mapTo(w,r.point_in_view(result.page(),rect.topLeft()).toPoint())
    image=w.grab().toImage()
    colors=[image.pixelColor(point.x()+dx,point.y()+dy) for dx in range(-4,5) for dy in range(-4,5)
            if image.rect().contains(point.x()+dx,point.y()+dy)]
    assert QColor('#376c51') in colors
    r.visit_search(2);assert r.pageNavigator().currentPage()==1
    r.back();wait(app);assert r.pageNavigator().currentPage()==0
    assert r.currentSearchResultIndex()==2  # Back restores reading location without changing the query.
    w.close()


def test_search_result_popup_keyboard_live_options_and_cancellation(app,search_pdf,tmp_path):
    w=Window(Store(tmp_path/'popup.db'),restore=False);w.show();r=w.open_pdf(search_pdf);wait(app)
    r.search.setSearchString('cat');done(app,r)
    assert not w.inline_search.results.icon().isNull()
    opened=[]
    def close_opened_panel():
        panels=w.findChildren(SearchPanel)
        opened.extend(panel for panel in panels if panel.isVisible())
        for panel in opened:panel.reject()
    QTimer.singleShot(50,close_opened_panel)
    w.inline_search.results.click()
    wait(app,100)
    assert len(opened)==1 and opened[0]._closed
    before=r.state(include_history=True)
    panel=SearchPanel(r,w);panel.position_near(w.inline_search);panel.show();wait(app)
    assert panel.isVisible() and r.state(include_history=True)==before
    from PySide6.QtWidgets import QPushButton
    assert not panel.findChildren(QPushButton)
    panel.whole_words.setChecked(True);done(app,r,5)
    assert w.inline_search.status.text()=='5 found'
    panel.match_case.setChecked(True);done(app,r,3)
    panel.results.setCurrentIndex(r.search.index(2,0));QTest.keyClick(panel.results,Qt.Key.Key_Return);wait(app)
    assert r.pageNavigator().currentPage()==1
    QTest.keyClick(panel.text,Qt.Key.Key_Return,Qt.KeyboardModifier.ShiftModifier)
    assert r.currentSearchResultIndex()==1
    QTest.keyClick(panel.text,Qt.Key.Key_Escape);wait(app)
    assert not panel.isVisible() and r.search.whole_words and r.search.match_case
    panel.deleteLater()
    reopened=SearchDialog(r,parent=w)
    assert reopened.whole_words.isChecked() and reopened.match_case.isChecked()
    r.search.set_options(match_case=False);done(app,r,5)
    assert not reopened.match_case.isChecked()
    reopened.reject();reopened.deleteLater()
    w.close()


def test_search_popup_outside_click_dismisses_without_reopening(app,search_pdf,tmp_path):
    w=Window(Store(tmp_path/'dismiss-search.db'),restore=False);w.show()
    r=w.open_pdf(search_pdf);wait(app)
    w.inline_search.text.setText('cat');done(app,r)
    assert not any(p.isVisible() for p in w.findChildren(SearchPanel))
    w.search_results();wait(app,50)
    panel=next(p for p in w.findChildren(SearchPanel) if p.isVisible())
    assert not panel.isModal()
    panel.whole_words.setChecked(True);done(app,r,5)
    QTest.mouseClick(r.viewport(),Qt.MouseButton.LeftButton,pos=r.viewport().rect().bottomRight()-QPoint(10,10))
    wait(app,100)
    assert not any(p.isVisible() for p in w.findChildren(SearchPanel))
    assert r.search.searchString()=='cat' and r.search.whole_words
    r.search.setSearchString('other');done(app,r)
    assert not any(p.isVisible() for p in w.findChildren(SearchPanel))
    w.close()


def test_search_filters_incremental_batches_and_replacement(app,tmp_path):
    path=tmp_path/'many.pdf';c=Canvas(str(path),pagesize=(600,1200))
    for n in range(90):c.drawString(20,1170-n*12,'cat cat cat cat cat cat cat cat')
    c.save();w=Window(Store(tmp_path/'batches.db'),restore=False);w.show();r=w.open_pdf(path);wait(app)
    sizes=[];r.search.rowsInserted.connect(lambda parent,first,last:sizes.append(last-first+1))
    r.search.setSearchString('cat');done(app,r,720)
    assert len(sizes)>1 and max(sizes)<=64
    # Refilter an already-populated native model, then immediately replace it;
    # no stale rows or callbacks may reappear after changing query/document.
    r.search.set_options(match_case=True)
    r.search.setSearchString('absent');done(app,r,0)
    r.search.setSearchString('cat');r.setDocument(None);wait(app,80)
    assert r.search.rowCount()==0 and not r.search.timer.isActive()
    w.close()


@pytest.mark.parametrize('theme',['Sepia','Black','Dark'])
def test_theme_tuning_defaults_original_colors_and_contrast(app,theme):
    image=QImage(4,1,QImage.Format.Format_RGBA8888)
    for x,color in enumerate(('#ffffff','#000000','#48ba9b','#1f4057')):image.setPixelColor(x,0,QColor(color))
    default=recolor(image,theme)
    assert recolor(image,theme,True,0,0)==default
    for warmth in (-50,50):
        tuned=recolor(image,theme,True,warmth,25)
        assert tuned!=default
        assert tuned.pixelColor(0,0)==QColor(canvas_color(theme,warmth,25))
        assert tuned.pixelColor(2,0)==image.pixelColor(2,0)
        paper,ink=tone_colors(theme,warmth,25)
        original=QColor(INK[theme]).getRgb()[:3]
        assert sum(ink)>sum(original) if theme in ('Dark','Black') else sum(ink)<sum(original)
        assert recolor(image,'Light',False,warmth,25)==image
    assert canvas_color('Light',50,30)=='#f2f2f2'
    assert tuning_values(dict(warmth=1000,contrast='bad'))==(50,0)
    assert theme_tunings(None)['Sepia']==dict(warmth=0,contrast=0)


def test_theme_settings_cancel_reset_save_and_split_preview(app,technical_pdf,tmp_path):
    store=Store(tmp_path/'tones.db');w=Window(store,restore=False);w.show();r=w.open_pdf(technical_pdf);wait(app)
    defaults=SettingsDialog(store,w);base=defaults.preview.image.copy()
    defaults.warmth.setValue(35);defaults.contrast.setValue(20)
    assert defaults.preview.image!=base and r.effect.warmth==0 and store.get('theme_tuning') is None
    defaults.theme.setCurrentText('Dark');defaults.warmth.setValue(-20)
    defaults.theme.setCurrentText('Sepia');assert defaults.warmth.value()==35 and defaults.contrast.value()==20
    defaults.reset_theme.click();assert defaults.preview.image==base
    defaults.warmth.setValue(30);values=defaults.values();defaults.reject();defaults.deleteLater()
    assert r.effect.warmth==0 and store.get('theme_tuning') is None
    w.apply_settings(values);assert r.effect.warmth==30 and store.get('theme_tuning')['Dark']['warmth']==-20
    w.split(0,0);wait(app);other=w.secondary
    assert other.effect.warmth==30
    r.set_rotation(90);wait(app);assert r.viewport().palette().color(QPalette.ColorRole.Dark)==QColor(canvas_color('Sepia',30,0))
    w.preview(r,Target(1));wait(app);preview=w.popups[-1]
    assert preview.reader.effect.theme=='Light' and not preview.reader.effect.isEnabled()
    w.apply_settings(dict(theme='Dark',theme_tuning={'Dark':dict(warmth=40,contrast=30)}));wait(app)
    assert r.effect.warmth==40 and other.effect.contrast==30
    assert preview.reader.effect.theme=='Light'
    reopened=SettingsDialog(store,w);assert reopened.warmth.value()==40
    reopened.theme.setCurrentText('Light');assert not reopened.warmth.isEnabled() and not reopened.contrast.isEnabled()
    assert reopened.preview.image==reopened.preview.original
    reopened.reset_appearance();assert all(v==dict(warmth=0,contrast=0) for v in reopened.values()['theme_tuning'].values())
    reopened.reject();reopened.deleteLater();w.close()


@pytest.fixture
def prose_pdf(tmp_path):
    path=tmp_path/'prose.pdf';c=Canvas(str(path),pagesize=(600,800));c.setFont('Helvetica',11)
    lines=[(40,750,'This is a paragraph with several words that'),(40,736,'continues naturally on the next printed line.'),
           (40,700,'Here is a separate paragraph that must stay'),(40,686,'separate from the first block of text.'),
           (40,650,'x = y + 2'),(40,630,'1. This list item must remain a line'),(40,615,'2. This second item must remain a line'),
           (40,580,'Column A    Column B    Column C'),(40,566,'Sample A    Sample B    Sample C')]
    for x,y,text in lines:c.drawString(x,y,text)
    c.save();return path


def test_copy_explicit_paragraph_joining_partial_full_split_and_preview(app,prose_pdf,tmp_path):
    source=hashlib.sha256(prose_pdf.read_bytes()).hexdigest()
    w=Window(Store(tmp_path/'copy.db'),restore=False);w.show();r=w.open_pdf(prose_pdf);wait(app)
    r.select_page_text();normal=r.selected_text();assert '\n' in normal
    assert r.copy_selection();assert QApplication.clipboard().text()==normal
    assert r.copy_selection(True);joined=QApplication.clipboard().text()
    assert 'that continues naturally' in joined and 'stay separate from' in joined
    assert '\n\nHere is' in joined and re.search(r'\nx = y \+ 2\n+1\.',joined) and '\n2.' in joined
    assert '\nColumn A Column B Column C\nSample A Sample B Sample C' in joined and ''.join(joined.split())==''.join(normal.split())
    full=r.text_selection.full(0)
    r.text_selection.anchor=(0,full.startIndex()+5)
    end=normal.index('Here is')-1
    r.text_selection.set_extent(0,end)
    partial=r.selected_text();assert r.copy_selection(True)
    assert ''.join(QApplication.clipboard().text().split())==''.join(partial.split())
    w.split(0,0);wait(app);other=w.secondary
    assert not other.copy_joined_action.isEnabled()
    other.select_page_text();other.copy_joined_action.trigger()
    assert QApplication.clipboard().text()==joined
    w.preview(r,Target(0));wait(app);preview=w.popups[-1]
    preview.reader.select_page_text();assert preview.reader.copy_selection(True)
    assert QApplication.clipboard().text()==joined
    r.clear_selection();assert not r.copy_joined_action.isEnabled() and other.copy_joined_action.isEnabled()
    assert hashlib.sha256(prose_pdf.read_bytes()).hexdigest()==source
    w.close()


def test_joining_conservative_columns_math_and_ambiguous_fallback(app,tmp_path):
    path=tmp_path/'columns.pdf';c=Canvas(str(path),pagesize=(600,800));c.setFont('Helvetica',9)
    for n in range(4):
        c.drawString(35,750-n*12,f'Left prose line {n} has several ordinary words')
        c.drawString(325,750-n*12,f'Right prose line {n} has several ordinary words')
    c.save();w=Window(Store(tmp_path/'columns.db'),restore=False);w.show();r=w.open_pdf(path);wait(app)
    r.select_page_text();r.copy_selection(True);text=QApplication.clipboard().text()
    assert text.index('Left prose line 3')<text.index('Right prose line 0') and '\nRight prose line 0' in text
    assert 'words Left prose line 1' in text
    assert join_paragraph_lines('ambiguous\nlayout')=='ambiguous\nlayout'
    symbols='ﬁeld λ − x² + a₁ ∫ f(x) dx'
    assert clean_text(symbols)=='field λ − x² + a₁ ∫ f(x) dx'
    w.close()


def test_search_boundaries_use_validated_source_instead_of_native_snippets(app,search_pdf,tmp_path):
    w=Window(Store(tmp_path/'boundaries.db'),restore=False);w.show();r=w.open_pdf(search_pdf);wait(app)
    r.search.setSearchString('cat');done(app,r)
    native=r.search.native
    class SnippetOffsets:
        # Real Qt match rectangles, deliberately bad snippet offsets. This
        # reproduces the native context/source-index disagreement seen in the
        # 15-page technical-paper probe without replacing its PDF text engine.
        def __init__(self,result,before,after):self.result,self.before,self.after=result,before,after
        def page(self):return self.result.page()
        def rectangles(self):return self.result.rectangles()
        def contextBefore(self):return self.before
        def contextAfter(self):return self.after
    r.search.set_options(whole_words=True);done(app,r,5)
    assert r.search.accepts(SnippetOffsets(native.resultAtIndex(1),'letter','letter'))
    assert not r.search.accepts(SnippetOffsets(native.resultAtIndex(2),' ',' '))  # scatter
    assert not r.search.accepts(SnippetOffsets(native.resultAtIndex(3),' ',' '))  # cat2
    r.search.set_options(match_case=True);done(app,r,3)
    assert not r.search.accepts(SnippetOffsets(native.resultAtIndex(0),' ',' '))  # Cat
    assert r.search.accepts(SnippetOffsets(native.resultAtIndex(1),'x','y'))
    w.close()


def test_match_case_keeps_tightly_kerned_hyphenated_terms(app,tmp_path):
    path=tmp_path/'hyphenated.pdf';c=Canvas(str(path));c.setFont('Times-Roman',10)
    c.drawString(40,740,'Read stacked self-attention and point-wise functions.')
    c.drawString(40,725,'Self-Attention and self-attention are separate cases.')
    c.save();w=Window(Store(tmp_path/'hyphens.db'),restore=False);w.show();r=w.open_pdf(path);wait(app)
    r.search.setSearchString('attention');r.search.set_options(whole_words=True,match_case=True);done(app,r,2)
    assert len(r.search.resultsOnPage(0))==2
    for index in range(2):
        result=r.search.resultAtIndex(index)
        spelling,first,last=r.search.source_match(result)
        assert spelling=='attention' and first is not None
        assert r.document().getSelectionAtIndex(0,first,last-first).text()=='attention'
    w.close()


def test_paragraph_copy_handles_font_runs_and_the_documents_line_pitch(app,tmp_path):
    path=tmp_path/'font-runs.pdf';c=Canvas(str(path),pagesize=(600,800))
    text=c.beginText(40,750);text.setFont('Helvetica',10)
    text.textOut('This paragraph contains several normal words and ')
    text.setFont('Helvetica-Bold',10);text.textOut('bold words')
    text.setFont('Helvetica',10);text.textOut(' that wrap');c.drawText(text)
    c.setFont('Helvetica',10)
    c.drawString(40,730,'over a normally spaced line with several more words.')
    c.drawString(40,680,'This is a separate paragraph with enough ordinary words')
    c.drawString(40,660,'to continue on another line without losing its boundary.')
    c.save();w=Window(Store(tmp_path/'font-runs.db'),restore=False);w.show();r=w.open_pdf(path);wait(app)
    r.select_page_text();original=r.selected_text();r.copy_selection(True);joined=QApplication.clipboard().text()
    assert 'bold words that wrap over a normally spaced line' in joined
    assert '\n\nThis is a separate paragraph' in joined
    assert 'ordinary words to continue' in joined
    assert ''.join(joined.split())==''.join(original.split())
    assert len([line for line in joined.splitlines() if line.strip()])<len(original.splitlines())
    w.close()
