"""A PDF-region render failure must not create a permanent busy retry loop."""
from PySide6.QtCore import QPointF,QSize
from PySide6.QtGui import QImage
from test_reader import app,pdf,wait
from mellow.app import Window
from mellow.storage import Store


def test_failed_lens_render_waits_for_new_input_then_recovers(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'lens.db'),restore=False);w.resize(760,700);w.show()
    r=w.open_pdf(pdf);wait(app,40)
    try:
        aids=r.aids;aids.set_lens_enabled(True)
        point=r.point_in_view(0,QPointF(80,140)).toPoint()
        aids.pointer=point;aids.refresh();aids.timer.stop()
        failed=aids.desired;assert failed is not None
        aids.pending=(123,failed)
        aids.rendered(0,QSize(),QImage(),None,123)
        assert aids.pending is None and aids.last_render==failed
        assert not aids.timer.isActive() and aids.overlay.image is None
        assert aids.overlay.message=='Preview unavailable'
        aids.pointer=None;aids.refresh();aids.pointer=point;aids.refresh()
        assert aids.overlay.message=='Preview unavailable' and not aids.timer.isActive()
        aids.pointer=r.point_in_view(0,QPointF(100,140)).toPoint();aids.refresh()
        for _ in range(100):
            wait(app,10)
            if aids.overlay.image is not None:break
        assert aids.overlay.image is not None and not aids.overlay.image.isNull()
        assert aids.last_render!=failed
        image=aids.overlay.image;point=aids.pointer
        aids.pointer=None;aids.refresh();aids.pointer=point;aids.refresh()
        assert aids.overlay.image is image and not aids.timer.isActive()
    finally:w.close()
