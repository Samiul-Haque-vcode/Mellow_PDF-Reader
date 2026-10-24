"""First roadmap batch: saved destinations, disposable previews and pane feedback."""
import pytest
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QColor
from test_reader import app, pdf, technical_pdf, wait
from mellow.app import Window
from mellow.storage import Store
from mellow.home import GROUP_ROLE
from mellow.search import SearchDialog


def await_results(app,reader,total):
    for _ in range(80):
        if reader.search.rowCount(QModelIndex())==total: break
        wait(app,20)
    assert reader.search.rowCount(QModelIndex())==total


def test_continue_after_restart_restores_labels_and_releases_thumbnail(app,technical_pdf,tmp_path):
    store=Store(tmp_path/'home.db')
    store.record_history(technical_pdf,1,state=dict(page=1,label='ii',zoom=1.4,mode=0))
    w=Window(store,restore=False)
    w.show()
    assert w.home.continue_strip.isVisible()
    assert 'ii' in w.home.continue_details.text()
    assert 'PDF page 2' in w.home.continue_details.text()
    assert 'Today' in w.home.listing.item(0).text()
    for _ in range(80):
        if w.home.thumbnail.image is not None: break
        wait(app,20)
    assert w.home.thumbnail.image is not None
    assert not w.home.thumbnail.source.isOpen()
    thumbnail=w.home.thumbnail
    assert thumbnail.image.pixelColor(0,0)==QColor('#ffffff')
    for theme,paper in [('Sepia','#faf1d9'),('Dark','#242622'),('Light','#ffffff')]:
        thumbnail.set_theme(theme)
        assert thumbnail.pixmap().toImage().pixelColor(0,0)==QColor(paper)
    # In particular, the asynchronous preview must not lock a source on Windows.
    moved=tmp_path/'renamed.pdf'
    technical_pdf.rename(moved)
    moved.rename(technical_pdf)
    w.home.resume.click()
    wait(app)
    assert not w._on_home and w.active.pageNavigator().currentPage()==1
    assert w.active.zoomFactor()==1.4
    assert not w.home.thumbnail.source.isOpen()
    w.close()


def test_home_continue_targets_focused_split_when_history_paused(app,pdf,technical_pdf,tmp_path):
    store=Store(tmp_path/'paused.db')
    store.set('history_paused',True)
    w=Window(store,restore=False)
    w.show()
    primary=w.open_pdf(pdf)
    w.open_pdf(technical_pdf)
    wait(app)
    w.split(0,1)
    wait(app)
    other=w.secondary
    other.jump(3)
    primary.jump(2)
    w.focus_reader(other)
    wait(app)
    before=[r.state() for r in (primary,other)]
    w.show_home()
    wait(app)
    assert w.home.continue_name.text()==technical_pdf.name
    assert w.home.continuation['page']==3
    assert not w.home.listing.count() and store.history()==[]
    w.home.resume.click()
    wait(app)
    assert w.active is other and w.secondary is other
    assert [r.state()['vertical'] for r in (primary,other)]==[s['vertical'] for s in before]
    w.close()


def test_favorite_group_filter_keeps_destinations_and_stacks(app,pdf,technical_pdf,tmp_path):
    store=Store(tmp_path/'groups.db')
    store.add('favorite',str(pdf),1,'First equation')
    store.add('favorite',str(technical_pdf),2,'Figure diagram')
    store.add('favorite',str(pdf),5,'Last equation')
    w=Window(store,restore=False)
    w.show()
    items=[w.home.favorites.item(i) for i in range(3)]
    assert [item.data(Qt.ItemDataRole.UserRole)['path'] for item in items]==[str(pdf),str(pdf),str(technical_pdf)]
    assert [item.data(GROUP_ROLE) for item in items]==[pdf.name,'',technical_pdf.name]
    w.home.filter.setText('First equation')
    assert items[0].isHidden() and not items[1].isHidden()
    assert items[1].data(GROUP_ROLE)==pdf.name
    assert w.home.favorite_count.text()=='1 / 3'
    w.resize(620,800)
    wait(app)
    assert w.home.columns.orientation()==Qt.Orientation.Vertical
    w.home.open_favorite(items[1])
    wait(app)
    assert w.active.path==str(pdf) and w.active.pageNavigator().currentPage()==1
    w.close()


def test_thumbnail_missing_encrypted_and_stale_work_are_quiet(app,pdf,tmp_path):
    from pypdf import PdfWriter
    encrypted=tmp_path/'encrypted.pdf'
    writer=PdfWriter(clone_from=pdf)
    writer.encrypt('password')
    writer.write(encrypted)
    w=Window(Store(tmp_path/'quiet.db'),restore=False)
    w.show()
    thumb=w.home.thumbnail
    for source in (str(pdf),str(encrypted),str(tmp_path/'missing.pdf')):
        thumb.set_source(source,0)
        thumb.load()
    wait(app)
    assert thumb.image is None and not thumb.source.isOpen()
    thumb.set_source(str(pdf),2)
    thumb.load()
    w.open_pdf(pdf)  # Hiding Home invalidates the outstanding preview request.
    wait(app)
    assert thumb.request is None and not thumb.source.isOpen()
    w.close()


def test_search_counter_wrap_reopen_and_reset_in_one_pane(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'search.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    w.split(0,0)
    wait(app)
    other=w.secondary
    dialog=SearchDialog(other,'Mellow',w)
    await_results(app,other,8)
    dialog.step(-1)
    assert dialog.status.text().startswith('8 of 8')
    assert other.pageNavigator().currentPage()==7
    dialog.step(1)
    assert dialog.status.text().startswith('1 of 8')
    dialog.step(1)
    assert dialog.status.text().startswith('2 of 8')
    dialog.accept()
    assert not dialog._connections
    reopened=SearchDialog(other,parent=w)
    assert reopened.status.text().startswith('2 of 8')
    reopened.text.setText('not-in-this-document')
    for _ in range(100):
        wait(app,20)
        if 'No matches' in reopened.status.text(): break
    assert 'No matches' in reopened.status.text()
    assert other.search.rowCount()==0 and other.currentSearchResultIndex()==-1
    reopened.text.clear()
    assert reopened.status.text()=='Enter text to search this PDF.'
    assert r.search.searchString()==''
    before=other.state(include_history=True)
    other.visit_search(0)  # No results: never navigate or add a history entry.
    assert other.state(include_history=True)==before
    reopened.reject()
    w.close()


@pytest.mark.parametrize('theme',['Light','Sepia','Black','Dark'])
@pytest.mark.parametrize('rotation',[0,90])
@pytest.mark.parametrize('layout',['continuous','single'])
def test_current_match_visible_after_theme_composition(app,pdf,tmp_path,theme,rotation,layout):
    w=Window(Store(tmp_path/'match.db'),restore=False)
    w.show()
    r=w.open_pdf(pdf)
    wait(app)
    r.set_page_layout(layout)
    r.rotate_by(rotation)
    w.change_theme(theme)
    r.search.setSearchString('Mellow')
    await_results(app,r,8)
    r.visit_search(0)
    wait(app)
    screenshot=w.grab().toImage()
    rect=r.search.resultAtIndex(0).rectangles()[0]
    point=r.point_in_view(0,rect.topLeft()).toPoint()
    origin=r.viewport().mapTo(w,point)
    expected=QColor('#acd8bd' if theme in ('Dark','Black') else '#376c51')
    # The dark-green outline is composited after toning, even at 90 degrees.
    pixels=[screenshot.pixelColor(origin.x()+x,origin.y()+y)
            for x in range(-4,5) for y in range(-4,5)
            if screenshot.rect().contains(origin.x()+x,origin.y()+y)]
    assert expected in pixels
    w.close()


def test_focused_pane_accent_follows_swap_orientation_home_and_exit(app,pdf,tmp_path):
    w=Window(Store(tmp_path/'focus.db'),restore=False)
    w.show()
    primary=w.open_pdf(pdf)
    wait(app)
    assert not primary.pane_active
    w.split(0,0)
    wait(app)
    secondary=w.secondary
    w.focus_reader(secondary)
    assert secondary.pane_active and not primary.pane_active
    for action in (w.swap,w.orientation):
        action()
        wait(app)
        assert secondary.pane_active and not primary.pane_active
        screenshot=w.grab().toImage()
        point=secondary.viewport().mapTo(w,secondary.viewport().rect().topLeft())
        assert screenshot.pixelColor(point.x()+10,point.y())==QColor('#527c64')
    w.show_home()
    assert not primary.pane_active and not secondary.pane_active
    w.resume_reading()
    assert secondary.pane_active
    w.exit_split()
    assert not primary.pane_active
    w.close()
