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


def test_return_to_previous_region_while_another_render_is_pending(app,pdf,tmp_path):
    from PySide6.QtCore import Qt
    w=Window(Store(tmp_path/'race.db'),restore=False);w.resize(760,700);w.show()
    r=w.open_pdf(pdf);wait(app,40)
    try:
        aids=r.aids;aids.set_lens_enabled(True)
        first=r.point_in_view(0,QPointF(80,140)).toPoint()
        second=r.point_in_view(0,QPointF(180,240)).toPoint()
        aids.pointer=first;aids.refresh();aids.timer.stop();a=aids.desired
        image=QImage(40,40,QImage.Format.Format_RGB32);image.fill(Qt.GlobalColor.red)
        aids.pending=(123,a);aids.rendered(0,QSize(),image,None,123)
        assert aids.last_render==a and aids.overlay.image is not None
        aids.pointer=second;aids.refresh();aids.timer.stop();b=aids.desired
        assert a!=b and aids.overlay.image is None
        aids.pending=(124,b)
        aids.pointer=first;aids.refresh();aids.timer.stop()
        aids.rendered(0,QSize(),image,None,124)
        assert aids.desired==a and aids.timer.isActive()
        for _ in range(100):
            wait(app,10)
            if aids.overlay.image is not None:break
        assert aids.overlay.image is not None and aids.last_render==a
    finally:w.close()
