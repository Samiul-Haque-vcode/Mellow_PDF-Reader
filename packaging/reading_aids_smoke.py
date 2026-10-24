"""Native Windows pointer, focus and cleanup probe for queued reading controls."""
import os,sys,tempfile,ctypes
from pathlib import Path
if sys.platform!='win32':raise SystemExit('This probe requires native Windows.')
os.environ['QT_QPA_PLATFORM']='windows'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer,QEventLoop,QPointF,Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from reportlab.pdfgen.canvas import Canvas
from mellow.app import Window
from mellow.storage import Store
from mellow.settings import SettingsDialog


def main():
    app=QApplication([])
    assert app.platformName()=='windows'
    def settle(ms=60):
        loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()
    with tempfile.TemporaryDirectory(prefix='mellow-native-aids-') as directory:
        path=Path(directory)/'source.pdf'
        c=Canvas(str(path))
        for page in range(2):
            c.setFillColorRGB(1,0,0);c.rect(60,600,100,100,fill=1,stroke=0)
            c.setFillColorRGB(0,0,0);c.drawString(40,750,'Native Mellow reading aids')
            c.bookmarkPage(str(page));c.addOutlineEntry('Chapter' if not page else 'Nested section',str(page),page)
            c.showPage()
        c.save()
        store=Store(Path(directory)/'state.sqlite3')
        w=Window(store,restore=False);w.resize(900,700);w.move(10,10);w.show()
        r=w.open_pdf(path);settle(300);w.raise_();w.activateWindow();r.setFocus();settle(100)
        ctypes.windll.user32.SetForegroundWindow(int(w.winId()));settle(100)
        r.aids.set_lens_enabled(True)
        QCursor.setPos(r.viewport().mapToGlobal(r.viewport().rect().topLeft()));settle(40)
        point=r.point_in_view(0,QPointF(110,190)).toPoint()
        before=r.state(include_history=True)
        QCursor.setPos(r.viewport().mapToGlobal(point))
        for _ in range(100):
            settle(20)
            if r.aids.overlay is not None and r.aids.overlay.image is not None and r.aids.pending is None:break
        assert r.aids.overlay is not None and r.aids.overlay.image is not None,'Native pointer did not render lens'
        image=r.aids.overlay.image;pixel=image.pixelColor(image.width()//2,image.height()//2)
        assert pixel.red()>220 and pixel.green()<40 and pixel.blue()<40,'Incorrect native PDF region'
        assert r.state(include_history=True)==before,'Lens changed reading position'
        assert QApplication.focusWidget() is r,'Lens stole keyboard focus'
        QTest.keyClick(r,Qt.Key.Key_Escape);settle()
        assert not r.aids.lens_enabled and r.aids.renderer is None
        w.lock_zoom_action.trigger();settle();zoom=r.zoomFactor()
        r.zoom_to(3);r.setZoomFactor(4);w.set_fit(1);settle()
        assert r.zoom_locked and r.zoomFactor()==zoom and not w.fit.isEnabled()
        w.lock_zoom_action.trigger();settle();w.update_controls()
        assert r.aids.index_ready and len(r.aids.targets)==2
        w.chapter_next_action.trigger();settle()
        assert r.pageNavigator().currentPage()==1,'Nested chapter was not reached'
        r.back();settle();assert r.pageNavigator().currentPage()==0
        r.setFocus();QTest.keyClick(r,Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(r,Qt.Key.Key_C,Qt.KeyboardModifier.ControlModifier)
        assert 'Native Mellow' in QApplication.clipboard().text()
        dialog=SettingsDialog(store,w);dialog.show();settle()
        assert [dialog.tabs.tabText(i) for i in range(4)]==['General','Reading','Appearance','Shortcuts']
        dialog.reject();dialog.deleteLater();settle()
        w.close();settle();store.db.close()
        moved=path.with_suffix('.moved.pdf');path.rename(moved)
        assert moved.is_file()
    print('Native pointer lens, focus, zoom lock, nested chapters, copying, Settings and file cleanup passed.')


if __name__=='__main__':main()
