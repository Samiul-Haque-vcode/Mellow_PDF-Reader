"""Render actual PDF details above display resolution without inflating the cache."""
import pytest
from PySide6.QtCore import Qt,QSize,QEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtPdf import QPdfDocument
from mellow.page_grid import PageGrid,CACHE_BYTES
from test_reader import app,technical_pdf,wait
from test_page_thumbnails_and_arrangement import thumbnails_ready


@pytest.mark.parametrize('density',[1.,1.25,2.])
@pytest.mark.parametrize('angle',[0,90])
def test_supersampled_real_pdf_keeps_physical_cache_and_original_colors(app,technical_pdf,monkeypatch,density,angle):
    document=QPdfDocument();document.load(str(technical_pdf))
    grid=PageGrid(document,entries=[(2,angle)])
    monkeypatch.setattr(grid,'devicePixelRatioF',lambda:density)
    requests=[]
    request_page=grid.renderer.requestPage
    def capture(page,size):
        requests.append(QSize(size))
        return request_page(page,size)
    monkeypatch.setattr(grid.renderer,'requestPage',capture)
    grid.resize(480,360);grid.show();thumbnails_ready(app,grid)
    image=grid.cache[(2,angle)]
    source_size=QSize(image.size())
    if angle:source_size.transpose()
    assert requests==[source_size*2]  # PDF detail is resolved above display size
    assert image.width()<=round(132*density) and image.height()<=round(156*density)
    assert sum(i.sizeInBytes() for i in grid.cache.values())<=CACHE_BYTES
    assert not image.isNull() and image.pixelColor(0,0)==Qt.GlobalColor.white
    # Text/diagrams contain real ink and smooth intermediate intensities.
    colors={image.pixelColor(x,y).rgba() for y in range(image.height()) for x in range(image.width())}
    assert len(colors)>20
    grid.close();assert not grid.pending and not grid._request_sizes
    document.close();grid.deleteLater();document.deleteLater();wait(app,10)


def test_monitor_change_discards_pending_old_resolution_and_rerenders(app,technical_pdf,monkeypatch):
    document=QPdfDocument();document.load(str(technical_pdf))
    grid=PageGrid(document,entries=[(0,0)]);grid.resize(400,280)
    density=[1.]
    monkeypatch.setattr(grid,'devicePixelRatioF',lambda:density[0])
    grid.show();grid.request(0);grid.pump()
    assert grid.pending
    obsolete=set(grid.pending)
    density[0]=2.
    QApplication.sendEvent(grid,QEvent(QEvent.Type.DevicePixelRatioChange))
    assert obsolete<=grid._obsolete_requests and not grid.cache
    thumbnails_ready(app,grid)
    assert grid.cache[(0,0)].height()==312  # 156 logical pixels at 200% DPI
    assert not grid._obsolete_requests and not grid._request_sizes and len(grid.pending)<=2
    grid.close();document.close();grid.deleteLater();document.deleteLater();wait(app,10)
