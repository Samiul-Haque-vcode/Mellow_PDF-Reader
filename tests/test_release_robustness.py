"""Boundary inputs must not overflow Qt or bypass backup validation."""
import copy
import json
import pytest
from test_reader import app,pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow import backup
from mellow.autoscroll import scroll_speed
from mellow.reading_options import crop_values


@pytest.mark.parametrize('method',['scroll_line','scroll_screen'])
@pytest.mark.parametrize('direction',[-1,1])
def test_manual_scroll_clamps_before_qt_integer_conversion(app,pdf,tmp_path,method,direction):
    w=Window(Store(tmp_path/'state.db'),restore=False);w.show();r=w.open_pdf(pdf);wait(app,30)
    try:
        bar=r.verticalScrollBar()
        bar.setRange(-2147483647,2147483647)
        edge=bar.maximum() if direction>0 else bar.minimum()
        bar.setValue(edge)
        getattr(r,method)(direction)
        assert bar.value()==edge
    finally:w.close()


@pytest.mark.parametrize('value',[10**400,-10**400,float('inf'),float('nan'),True])
def test_out_of_range_numbers_fail_validation_without_overflow(value):
    assert not backup.number(value)
    expected=24 if type(value) is not int else (200 if value>0 else 5)
    assert scroll_speed(value)==expected
    with pytest.raises(ValueError,match='Margins'):crop_values([value,0,0,0])


@pytest.mark.parametrize('field',['x','crop'])
def test_bad_backup_numbers_leave_existing_metadata_unchanged(tmp_path,field):
    store=Store(tmp_path/'data'/'state.db');store.add('favorite','/book.pdf',0,'Keep')
    try:
        before=backup.snapshot(store);data=copy.deepcopy(before)
        if field=='x':data['locations'][0]['x']=10**400
        else:
            data['document_options'].append(dict(path='/book.pdf',page_layout='continuous',cover=1,crop=json.dumps([10**400,0,0,0]),numbering=None))
        with pytest.raises(ValueError):backup.replace(store,data)
        assert backup.snapshot(store)==before
    finally:store.db.close()
