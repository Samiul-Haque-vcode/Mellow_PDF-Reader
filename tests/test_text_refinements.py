"""Source-backed excerpts and conservative paragraph endings in real PDFs."""
import hashlib
from reportlab.pdfgen.canvas import Canvas
from PySide6.QtPdf import QPdfDocument
from PySide6.QtCore import Qt
from test_reader import app,wait
from mellow.search_model import SearchModel
from mellow.selection import TextSelection


def finish(app,model):
    for _ in range(300):
        wait(app,20)
        if model.status()==model.Status.Finished:return
    raise AssertionError('PDF search did not finish')


def test_excerpts_use_source_case_spacing_and_verified_context(app,tmp_path):
    path=tmp_path/'excerpts.pdf';c=Canvas(str(path),pagesize=(600,800))
    c.setFont('Times-Bold',14);c.drawString(40,750,'Attention Is All You Need')
    c.setFont('Times-Roman',10)
    c.drawString(40,710,'The models connect through self-attention and retain their original notation.')
    c.drawString(40,696,'An Attention mechanism can continue onto the next printed line.')
    c.save();digest=hashlib.sha256(path.read_bytes()).hexdigest()
    document=QPdfDocument();document.load(str(path));model=SearchModel();model.setDocument(document)
    model.setSearchString('attention');finish(app,model)
    assert model.rowCount()==3
    title=model.index(0,0).data()
    assert 'Attention Is All You Need' in title and 'self-attention' in title
    assert '⏎' not in title and '\r' not in title and title.count('\n')==1
    assert 'self-attention and retain' in model.index(1,0).data()
    assert 'An Attention mechanism' in model.index(2,0).data()
    class BadSnippets:
        def __init__(self,result):self.result=result
        def page(self):return self.result.page()
        def rectangles(self):return self.result.rectangles()
        def contextBefore(self):return 'bad_offset'
        def contextAfter(self):return 'bad_offset'
    assert model.excerpt(BadSnippets(model.resultAtIndex(1)))==model.index(1,0).data().split('\n',1)[1]
    class Unmapped(BadSnippets):
        def rectangles(self):return []
        def contextBefore(self):return 'Native⏎context '
        def contextAfter(self):return ' retained\r\nwithout guessing'
    assert model.excerpt(Unmapped(model.resultAtIndex(0)))=='Native context attention retained without guessing'
    class BlankContext(Unmapped):
        def contextBefore(self):return ' '*100
        def contextAfter(self):return ' '*200
    assert model.excerpt(BlankContext(model.resultAtIndex(0)))=='… attention…'
    model.setDocument(None);document.close()
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest


def test_excerpts_are_lazy_bounded_and_invalidated_on_query_and_document(app,tmp_path):
    path=tmp_path/'many-excerpts.pdf';c=Canvas(str(path),pagesize=(600,3000));c.setFont('Helvetica',10)
    for n in range(150):c.drawString(40,2950-n*18,f'Row {n} has an Attention mechanism with useful surrounding words.')
    c.save();document=QPdfDocument();document.load(str(path));model=SearchModel();model.setDocument(document)
    calls=[];original=model.excerpt
    def tracked(result):calls.append(result.page());return original(result)
    model.excerpt=tracked
    model.setSearchString('attention');finish(app,model)
    assert model.rowCount()==150 and not calls and not model._excerpts
    first=model.index(0,0)
    assert first.data()==first.data(Qt.ItemDataRole.ToolTipRole) and len(calls)==1
    for row in range(150):assert 'Attention' in model.index(row,0).data()
    assert len(model._excerpts)==128
    model.setSearchString('mechanism');finish(app,model)
    assert not model._excerpts and 'mechanism' in model.index(0,0).data()
    model.setDocument(None);assert not model._excerpts;document.close()


def test_paragraph_endings_join_without_merging_lists_formulas_or_short_rows(app,tmp_path):
    path=tmp_path/'endings.pdf';c=Canvas(str(path),pagesize=(600,800));c.setFont('Helvetica',10)
    rows=[(750,'This paragraph has several ordinary words and its final line'),
          (736,'is quite short.'),
          (700,'Here another paragraph has several words describing the result'),
          (686,'called none.'),
          (650,'The equation below must remain separate from this prose line'),
          (636,'x = y + 2'),
          (600,'1. This first list item should retain its own line'),
          (586,'2. This second list item should retain its own line'),
          (550,'A short label.'),(536,'Another short label.')]
    for y,text in rows:c.drawString(40,y,text)
    c.showPage();c.setFont('Helvetica',10)
    c.drawString(40,750,'The following text ends with a deliberately unjoined hyphen-')
    c.drawString(40,736,'ated continuation.')
    c.save();document=QPdfDocument();document.load(str(path));selection=TextSelection(document);selection.select_page(0)
    normal=selection.text();joined=selection.text(True)
    assert 'final line is quite short.' in joined and 'result called none.' in joined
    assert '\nHere another paragraph' in joined
    assert '\nx = y + 2' in joined and '\n2. This second list' in joined
    assert 'A short label.\nAnother short label.' in joined
    assert ''.join(joined.split())==''.join(normal.split())
    # Qt can encode this wrapped hyphen as an unmapped character and a single
    # logical line. Preserve that native text instead of guessing its spelling.
    selection.select_page(1)
    assert selection.text(True)==selection.text()
    document.close()


def test_sparse_paragraph_gaps_do_not_set_the_wrapping_pitch(app,tmp_path):
    path=tmp_path/'sparse.pdf';c=Canvas(str(path),pagesize=(600,800));c.setFont('Helvetica',10)
    # More paragraph breaks than ordinary line gaps: a median over every
    # vertical step used to merge the separate complete paragraphs below.
    rows=[(750,'This opening paragraph has several words and should wrap'),
          (736,'over this second line with several more ordinary words.'),
          (712,'This separate paragraph has several words describing a result.'),
          (688,'Another separate paragraph has several ordinary words describing results.'),
          (664,'A final separate paragraph also contains several ordinary words.')]
    for y,text in rows:c.drawString(40,y,text)
    c.save();document=QPdfDocument();document.load(str(path));selection=TextSelection(document);selection.select_page(0)
    joined=selection.text(True)
    assert 'should wrap over this second line' in joined
    for text in ('This separate paragraph','Another separate paragraph','A final separate paragraph'):
        assert '\n\n'+text in joined
    assert ''.join(joined.split())==''.join(selection.text().split())
    document.close()
