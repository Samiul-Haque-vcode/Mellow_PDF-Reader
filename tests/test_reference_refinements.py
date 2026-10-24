"""Offline reference ambiguity, real PDF source geometry and manual fallback."""
from mellow.dialogs import DismissibleInputDialog
import hashlib
import pytest
from reportlab.pdfgen.canvas import Canvas
from PySide6.QtCore import Qt
from PySide6.QtPdf import QPdfDocument,QPdfSelection
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QInputDialog,QLabel
from test_reader import app,wait
from mellow.references import ReferenceResolver
from mellow.reference_choices import ReferenceChoices
from mellow.app import Window
from mellow.storage import Store


@pytest.fixture
def references_pdf(tmp_path):
    path=tmp_path/'repeated.pdf';c=Canvas(str(path),pagesize=(600,800));c.setFont('Helvetica',10)
    c.drawString(30,750,'Figure 3.8 shows how the method works in this discussion.')
    c.drawString(30,730,'We use Equation (2.4) and refer to (2.4) in this discussion.')
    c.drawString(30,700,'4.2 Methods and results . . . . . . . . . . . . . . . 3')
    c.showPage();c.setFont('Helvetica',10)
    c.drawString(30,770,'Figure 3.8: Original experiment')
    c.drawString(320,770,'Figure 3.8: Repeated experiment')
    c.drawString(30,650,'x = y + 2    (2.4)')
    c.drawString(30,620,')V (9)')
    c.showPage();c.setFont('Helvetica',10)
    c.drawString(30,750,'Figure 3.8: Alternative experiment')
    c.drawString(30,680,'4.2 Methods and results')
    c.save();return path


def resolve(app,document,label,page=0):
    job=ReferenceResolver(document,label,page);done=[];sizes=[]
    job.finished.connect(done.append);job.progress.connect(lambda *_:sizes.append(len(job.candidates)))
    job.start()
    for _ in range(300):
        if done:break
        wait(app,10)
    assert done and not job.timer.isActive()
    return done[0],sizes,job


def test_repeated_captions_keep_same_page_columns_context_and_rank(app,references_pdf,tmp_path):
    digest=hashlib.sha256(references_pdf.read_bytes()).hexdigest()
    w=Window(Store(tmp_path/'references.db'),restore=False);w.show();reader=w.open_pdf(references_pdf);wait(app)
    targets,_,_=resolve(app,reader.document(),'Figure 3.8',2)
    assert [t.page for t in targets]==[2,1,1,0]
    assert targets[-1].evidence=='Text citation'
    same=[t for t in targets if t.page==1]
    assert len(same)==2 and abs(same[0].x-same[1].x)>200
    assert any('Original experiment' in t.excerpt for t in same)
    assert any('Repeated experiment' in t.excerpt for t in same)
    before=reader.state(include_history=True)
    choices=ReferenceChoices(reader,targets,w);choices.show();wait(app,30)
    choices.listing.setFocus();QTest.keyClick(choices.listing,Qt.Key.Key_Down)
    QTest.keyClick(choices.listing,Qt.Key.Key_Return)
    assert choices.target is not None and choices.target.page==1 and not choices.manual
    assert reader.state(include_history=True)==before
    choices.deleteLater();w.close()
    assert hashlib.sha256(references_pdf.read_bytes()).hexdigest()==digest


def test_equation_citations_do_not_outrank_math_labels_or_duplicate_explicit_text(app,references_pdf):
    document=QPdfDocument();document.load(str(references_pdf))
    targets,_,_=resolve(app,document,'Equation (2.4)')
    assert len(targets)==3
    assert targets[0].page==1 and targets[0].evidence=='Possible equation label'
    assert all(t.evidence=='Text citation' for t in targets[1:])
    sections,_,_=resolve(app,document,'Section 4.2')
    assert len(sections)==2 and sections[0].page==2 and 'Methods and results' in sections[0].excerpt
    assert sections[1].evidence=='Contents entry'
    equation,_,_=resolve(app,document,'Equation (9)')
    assert len(equation)==1 and equation[0].evidence=='Possible equation label'
    document.close()


def test_candidates_stay_bounded_and_cancellation_cannot_restart(app,tmp_path):
    path=tmp_path/'many-references.pdf';c=Canvas(str(path),pagesize=(600,800))
    for page in range(40):
        c.drawString(30,740,f'Figure 2.1: Experiment number {page}');c.showPage()
    c.save();document=QPdfDocument();document.load(str(path))
    targets,sizes,job=resolve(app,document,'Figure 2.1',39)
    assert len(targets)==30 and max(sizes)==30 and targets[0].page==39
    cancelled=ReferenceResolver(document,'Figure 2.1',0);done=[];cancelled.finished.connect(done.append)
    cancelled.start();cancelled.cancel();cancelled.start();cancelled.tick();wait(app,30)
    assert cancelled.count==0 and not done and not cancelled.timer.isActive()
    document.close()


def test_invalid_source_ranges_offer_manual_fallback_instead_of_origin_target(app,references_pdf):
    document=QPdfDocument();document.load(str(references_pdf))
    class Unmapped:
        def pageCount(self):return document.pageCount()
        def getAllText(self,page):return document.getAllText(page)
        def getSelectionAtIndex(self,*_):return QPdfSelection()
    targets,_,_=resolve(app,Unmapped(),'Figure 3.8')
    assert not targets
    document.close()


def test_missing_reference_manual_preview_preserves_source_and_original_colors(app,references_pdf,tmp_path,monkeypatch):
    w=Window(Store(tmp_path/'manual.db'),restore=False);w.show();reader=w.open_pdf(references_pdf);wait(app)
    before=reader.state(include_history=True)
    shown=[]
    def choose_manual(dialog):
        assert dialog.listing.count()==0 and not dialog.open_button.isEnabled()
        shown.append(dialog);dialog.choose_manual();return dialog.DialogCode.Accepted
    monkeypatch.setattr(ReferenceChoices,'exec',choose_manual)
    monkeypatch.setattr(DismissibleInputDialog,'getInt',lambda *_:(2,True))
    w.resolve_reference(reader,'Figure 99.1')
    for _ in range(100):
        if w.popups:break
        wait(app,20)
    wait(app,100)
    assert shown and len(w.popups)==1 and not w.reference_jobs
    popup=w.popups[0]
    assert popup.reader.pageNavigator().currentPage()==1 and not popup.reader.effect.isEnabled()
    assert reader.state(include_history=True)==before
    w.close()


def test_single_heuristic_target_still_shows_evidence_and_keeps_source_position(app,references_pdf,tmp_path):
    w=Window(Store(tmp_path/'single-reference.db'),restore=False);w.show();reader=w.open_pdf(references_pdf);wait(app)
    before=reader.state(include_history=True)
    w.resolve_reference(reader,'Equation (9)')
    for _ in range(100):
        if w.popups:break
        wait(app,20)
    wait(app,100)
    assert len(w.popups)==1 and not w.reference_jobs
    popup=w.popups[0]
    assert any('Possible equation label' in label.text() for label in popup.findChildren(QLabel))
    assert popup.reader.pageNavigator().currentPage()==1 and not popup.reader.effect.isEnabled()
    assert reader.state(include_history=True)==before
    w.close()


def test_reference_completion_ignores_discarded_split_reader(app,references_pdf,tmp_path,monkeypatch):
    w=Window(Store(tmp_path/'discarded-reference.db'),restore=False);w.show();w.open_pdf(references_pdf)
    w.split(0,0);wait(app);reader=w.secondary
    previews=[];monkeypatch.setattr(w,'preview',lambda *args:previews.append(args))
    w.resolve_reference(reader,'Equation (9)');assert w.reference_jobs
    w.exit_split()
    for _ in range(100):
        if not w.reference_jobs:break
        wait(app,20)
    assert not w.reference_jobs and not previews and not w.popups
    w.close()
