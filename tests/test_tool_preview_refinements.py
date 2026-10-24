"""Preview continuity and stale-output protection using actual generated PDFs."""
from pathlib import Path
from threading import Event
import hashlib
import pytest
from PIL import Image
from reportlab.pdfgen.canvas import Canvas
from pypdf import PdfReader
from PySide6.QtCore import QPointF
from PySide6.QtPdfWidgets import QPdfView
from test_reader import app,pdf,technical_pdf,wait
from test_settings_and_tools import settle
from mellow.tool_dialog import ToolDialog
from mellow import utilities


def images(tmp_path):
    paths=[]
    for index,color in enumerate(('red','blue','green')):
        path=tmp_path/f'{index}.png';Image.new('RGB',(120,80),color).save(path);paths.append(str(path))
    return paths


@pytest.mark.parametrize('mode',['images','merge','extract'])
def test_compatible_rebuild_keeps_page_and_zoom(app,pdf,technical_pdf,tmp_path,mode):
    paths=images(tmp_path) if mode=='images' else [str(pdf),str(technical_pdf)] if mode=='merge' else [str(pdf)]
    d=ToolDialog(mode,paths=paths)
    if mode=='extract':d.ranges.setText('1-4')
    d.show();settle(app,d);d.fit.setCurrentText('150%');d.page.setValue(3)
    count=d.document.pageCount();digests=[hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths]
    d.queue_preview()
    assert d.current_output is None and not d.save_button.isEnabled() and not d.output_info.text()
    assert not d.preview_file.isOpen() and d.view.document() is None
    settle(app,d)
    assert d.page.value()==3 and d.view.pageNavigator().currentPage()==2
    assert d.document.pageCount()==count and d.count.accessibleName()==f'{count} output pages'
    assert d.view.zoomMode()==QPdfView.ZoomMode.Custom and abs(d.view.zoomFactor()-1.5)<.001
    assert [hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths]==digests
    d.reject()


def test_image_page_size_change_keeps_source_page_and_scaled_location(app,tmp_path):
    d=ToolDialog('images',paths=images(tmp_path));d.show();settle(app,d)
    d.fit.setCurrentText('150%');d.page.setValue(2)
    d.view.pageNavigator().jump(1,QPointF(10,20));wait(app,20)
    old=d.document.pagePointSize(1);point=QPointF(d.view.pageNavigator().currentLocation())
    d.size.setCurrentText('Letter');settle(app,d)
    size=d.document.pagePointSize(1);actual=d.view.pageNavigator().currentLocation()
    assert d.page.value()==2 and d.view.pageNavigator().currentPage()==1
    assert abs(d.view.zoomFactor()-1.5)<.001 and size.width()==612
    assert abs(actual.x()-point.x()*size.width()/old.width())<1
    assert abs(actual.y()-point.y()*size.height()/old.height())<1
    assert '215.9 × 279.4 mm' in d.output_info.text()
    d.reject()


def test_arrangement_follows_base_page_through_reorder_and_rotation(app,pdf):
    d=ToolDialog('extract',paths=[str(pdf)]);d.ranges.setText('1-4');d.show();settle(app,d)
    d.fit.setCurrentText('Fit Width');d.page.setValue(3)
    d.apply_arrangement([(3,0),(2,90),(1,0),(0,0)]);settle(app,d)
    assert d.page.value()==2 and 'chapter 3' in d.document.getAllText(1).text()
    assert d.view.zoomMode()==QPdfView.ZoomMode.FitToWidth
    size=d.document.pagePointSize(1)
    assert size.width()>size.height() and f'{size.width()*25.4/72:.1f}' in d.output_info.text()
    d.apply_arrangement([(page,0) for page in range(4)]);settle(app,d)
    assert d.page.value()==3 and 'chapter 3' in d.document.getAllText(2).text()
    d.reject()


def test_new_ranges_and_invalid_preview_clear_stale_output(app,pdf,tmp_path):
    d=ToolDialog('extract',paths=[str(pdf)]);d.ranges.setText('1-4');d.show();settle(app,d)
    d.page.setValue(3);d.fit.setCurrentText('200%')
    d.ranges.setText('5-6')
    assert not d.save_to(tmp_path/'stale.pdf') and not (tmp_path/'stale.pdf').exists()
    assert not d.output_info.text() and d.count.text()=='/ 0'
    settle(app,d)
    assert d.page.value()==1 and 'chapter 5' in d.document.getAllText(0).text()
    assert abs(d.view.zoomFactor()-2)<.001
    d.ranges.setText('999');settle(app,d)
    assert d.current_output is None and not d.output_info.text() and not d.save_button.isEnabled()
    assert d.retry.isVisible()
    d.ranges.setText('5-6');settle(app,d)
    expected=Path(d.current_output).read_bytes();out=tmp_path/'fresh.pdf'
    assert d.save_to(out);settle(app,d)
    assert out.read_bytes()==expected


def test_external_source_change_blocks_save_and_rebuilds_actual_output(app,pdf,technical_pdf,tmp_path):
    source=tmp_path/'source.pdf';source.write_bytes(pdf.read_bytes())
    d=ToolDialog('extract',paths=[str(source)]);d.show();settle(app,d)
    original=Path(d.current_output).read_bytes()
    source.write_bytes(technical_pdf.read_bytes());out=tmp_path/'saved.pdf'
    assert not d.save_to(out) and not out.exists()
    assert d.current_output is None and 'Inputs changed' in d.status.text()
    settle(app,d)
    assert Path(d.current_output).read_bytes()!=original
    with PdfReader(d.current_output) as result,PdfReader(source) as actual:
        assert result.pages[0].extract_text()==actual.pages[0].extract_text()
    d.reject()


def test_source_change_during_worker_never_publishes_old_output(app,pdf,technical_pdf,tmp_path,monkeypatch):
    source=tmp_path/'source.pdf';source.write_bytes(pdf.read_bytes())
    started,release=Event(),Event();original=utilities.extract;calls=[]
    def controlled(src,output,ranges,cancel,progress):
        original(src,output,ranges,cancel,progress);calls.append(output);started.set();release.wait(2)
    monkeypatch.setattr(utilities,'extract',controlled)
    d=ToolDialog('extract',paths=[str(source)]);d.show();d.timer.stop();d.build_preview()
    try:
        assert started.wait(1)
        source.write_bytes(technical_pdf.read_bytes())
    finally:release.set()
    settle(app,d)
    assert len(calls)==2 and d.current_output==calls[-1]
    with PdfReader(d.current_output) as result,PdfReader(source) as actual:
        assert result.pages[0].extract_text()==actual.pages[0].extract_text()
    d.reject()


def test_user_page_choice_wins_over_queued_restore(app,pdf):
    d=ToolDialog('extract',paths=[str(pdf)]);d.ranges.setText('1-4');d.show();settle(app,d)
    d.page.setValue(2);d.queue_preview();d.timer.stop();d.build_preview()
    d._job.succeeded.connect(lambda *_:d.page.setValue(4))
    settle(app,d)
    assert d.page.value()==4 and d.view.pageNavigator().currentPage()==3
    d.reject()


def test_current_page_dimensions_follow_mixed_size_output(app,technical_pdf):
    d=ToolDialog('merge',paths=[str(technical_pdf)]);d.show();settle(app,d)
    seen=set()
    for index in range(d.document.pageCount()):
        d.page.setValue(index+1);size=d.document.pagePointSize(index)
        expected=f'{size.width()*25.4/72:.1f} × {size.height()*25.4/72:.1f} mm'
        assert expected in d.output_info.text()
        seen.add(expected)
    assert len(seen)>1
    root=d._temp.name;d.reject()
    assert not d.restore_timer.isActive() and not d.preview_file.isOpen() and not Path(root).exists()


def test_visible_page_pixels_follow_navigation_zoom_and_rebuild(app,tmp_path):
    source=tmp_path/'colored-pages.pdf';canvas=Canvas(str(source),pagesize=(595,842))
    for color in ((1,0,0),(0,1,0),(0,0,1)):
        canvas.setFillColorRGB(*color);canvas.rect(0,0,595,842,fill=1,stroke=0);canvas.showPage()
    canvas.save()
    d=ToolDialog('extract',paths=[str(source)]);d.ranges.setText('1-3');d.show();settle(app,d)
    def visible_color(channel):
        actual=None
        for _ in range(80):
            wait(app,30)
            actual=d.view.viewport().grab().toImage().pixelColor(50,60)
            values=(actual.red(),actual.green(),actual.blue())
            if values[channel]>200 and all(v<50 for i,v in enumerate(values) if i!=channel):return
        pytest.fail(f'Visible page color {actual.name()} differs from selected page {d.page.value()}')
    d.page.setValue(3);d.fit.setCurrentText('Fit Width');visible_color(2)
    d.resize(1100,730);visible_color(2)
    d.fit.setCurrentText('150%');visible_color(2)
    d.queue_preview();settle(app,d);assert d.page.value()==3;visible_color(2)
    d.page.setValue(2);visible_color(1)
    d.reject()
