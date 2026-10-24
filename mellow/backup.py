"""Versioned metadata backups. Never copy PDFs or execute SQL from a backup."""
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .reading_options import crop_values, numbering_values

FORMAT = 'mellow-pdf-reader-backup'
LIMIT = 32 * 1024 * 1024
TABLES = {
    'settings': ('key', 'value'),
    'locations': ('id', 'kind', 'path', 'page', 'title', 'x', 'y', 'label'),
    'history': ('path', 'page', 'x', 'y', 'visited', 'state'),
    'document_options': ('path', 'page_layout', 'cover', 'crop', 'numbering'),
}


def require(condition):
    if not condition:
        raise ValueError('Invalid Mellow backup data.')


def number(value, low=-1e9, high=1e9):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def text(value):
    return isinstance(value, str) and len(value) <= 100000


def state(value, depth=0):
    require(isinstance(value, dict) and depth <= 6)
    for key in ('path', 'label'):
        if key in value: require(text(value[key]))
    for key in ('page', 'anchor_page'):
        if key in value: require(type(value[key]) is int and 0 <= value[key] < 1000000)
    for key in ('x', 'y', 'horizontal', 'vertical'):
        if key in value: require(number(value[key]))
    for key in ('horizontal', 'vertical'):
        if key in value: require(type(value[key]) is int)
    for key in ('zoom', 'dpi', 'dpr'):
        if key in value: require(number(value[key], .001, 10000))
    if 'mode' in value: require(type(value['mode']) is int and value['mode'] in (0, 1, 2))
    if 'rotation' in value: require(value['rotation'] in (0, 90, 180, 270))
    if 'layout' in value: require(value['layout'] in ('single', 'continuous', 'two', 'two_continuous'))
    if 'crop' in value: crop_values(value['crop'])
    if 'cover' in value: require(type(value['cover']) is bool)
    if 'viewport' in value:
        require(isinstance(value['viewport'], list) and len(value['viewport']) == 2
                and all(type(v) is int and 0 <= v <= 100000 for v in value['viewport']))
    for key in ('past', 'future'):
        if key in value:
            require(isinstance(value[key], list) and len(value[key]) <= 1000)
            for entry in value[key]: state(entry, depth + 1)


def session(value):
    require(isinstance(value, dict))
    documents = value.get('documents', [])
    require(isinstance(documents, list) and len(documents) <= 10000)
    for entry in documents:
        state(entry)
        require(text(entry.get('path')) and bool(entry['path']))
    if value.get('secondary') is not None:
        state(value['secondary'])
        require(text(value['secondary'].get('path')))
    if value.get('active_path') is not None: require(text(value['active_path']))
    if 'active' in value: require(type(value['active']) is int and value['active'] >= 0)
    if 'orientation' in value: require(value['orientation'] in (1, 2))
    for key in ('home', 'active_secondary'):
        if key in value: require(type(value[key]) is bool)
    if 'sizes' in value:
        require(isinstance(value['sizes'], list) and len(value['sizes']) <= 2
                and all(type(v) is int and 0 <= v <= 1000000 for v in value['sizes']))
    if 'pane_order' in value:
        require(isinstance(value['pane_order'], list) and len(value['pane_order']) <= 2
                and all(v in ('primary', 'secondary') for v in value['pane_order']))
        if value.get('secondary') is not None: require(len(value['pane_order']) == 2)
    if 'window' in value: require(isinstance(value['window'], dict))


def settings(key, value):
    booleans = {'preserve', 'restore_session', 'fullscreen_autohide', 'toolbar_labels', 'caption_tabs', 'history_paused'}
    if key in booleans: require(type(value) is bool)
    elif key in ('ruler_height', 'ruler_opacity', 'fullscreen_hide_delay', 'auto_scroll_speed'):
        require(type(value) is int and 0 <= value <= 10000)
    elif key in ('theme', 'default_fit', 'zoom_speed'): require(text(value))
    elif key == 'default_layout': require(isinstance(value,str) and value in ('continuous','single','two','two_continuous'))
    elif key == 'copy_format': require(isinstance(value,str) and value in ('preserve','paragraphs'))
    elif key == 'session': session(value)
    elif key == 'shortcuts':
        require(isinstance(value, dict) and all(text(k) and text(v) for k, v in value.items()))
        from .shortcuts import validate, migrate_navigation
        validate(migrate_navigation(value))
    elif key == 'theme_tuning':
        require(isinstance(value, dict))
        for tuning in value.values():
            require(isinstance(tuning, dict))
            require(all(type(v) is int and -100 <= v <= 100 for v in tuning.values()))


def validate(data):
    require(isinstance(data, dict) and set(data) == set(TABLES))
    for table, columns in TABLES.items():
        rows = data[table]
        require(isinstance(rows, list) and len(rows) <= 100000)
        seen = set()
        for row in rows:
            require(isinstance(row, dict) and set(row) == set(columns))
            identity = row['key' if table == 'settings' else 'id' if table == 'locations' else 'path']
            require(type(identity) in (str, int) and identity not in seen)
            seen.add(identity)
            if table == 'settings':
                require(text(row['key']) and isinstance(row['value'], str) and len(row['value']) <= LIMIT)
                settings(row['key'], json.loads(row['value']))
                continue
            require(text(row['path']) and bool(row['path']) and '\x00' not in row['path'])
            if table in ('locations', 'history'):
                require(type(row['page']) is int and 0 <= row['page'] < 1000000)
                require(number(row['x']) and number(row['y']))
            if table == 'locations':
                require(type(row['id']) is int and 0 < row['id'] <= 9223372036854775807)
                require(row['kind'] in ('favorite', 'bookmark') and text(row['title']))
                require(row['label'] is None or text(row['label']))
            elif table == 'history':
                require(text(row['visited']))
                if row['state'] is not None:
                    require(isinstance(row['state'], str))
                    state(json.loads(row['state']))
            else:
                require(row['page_layout'] in ('single', 'continuous', 'two', 'two_continuous'))
                require(row['cover'] in (0, 1))
                if row['crop'] is not None: crop_values(json.loads(row['crop']))
                if row['numbering'] is not None: numbering_values(json.loads(row['numbering']))
    return data


def snapshot(store):
    with store.db:
        if not store.db.in_transaction: store.db.execute('BEGIN')
        data = {table: [dict(row) for row in store.db.execute(
            'SELECT ' + ','.join(columns) + ' FROM ' + table)] for table, columns in TABLES.items()}
    return validate(data)


def write(store, path):
    path = Path(path).resolve()
    database = store.db.execute('PRAGMA database_list').fetchone()[2]
    if database and path.is_relative_to(Path(database).resolve().parent):
        raise ValueError('Save the backup outside Mellow’s data folder so uninstall will keep it.')
    body = json.dumps(dict(format=FORMAT, version=1,
        created_utc=datetime.now(timezone.utc).isoformat(), data=snapshot(store)),
        ensure_ascii=False, allow_nan=False, indent=2).encode('utf8')
    if len(body) > LIMIT: raise ValueError('Backup is larger than the 32 MB metadata limit.')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.mellow-backup-', delete=False) as output:
            temporary = Path(output.name)
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)


def read(path):
    with Path(path).open('rb') as source:
        content = source.read(LIMIT + 1)
    require(len(content) <= LIMIT)
    try:
        def reject_constant(value): raise ValueError('Invalid number in Mellow backup.')
        document = json.loads(content, parse_constant=reject_constant)
        require(isinstance(document, dict) and document.get('format') == FORMAT
                and type(document.get('version')) is int and document['version'] == 1)
        return validate(document.get('data'))
    except (TypeError, KeyError, OverflowError, RecursionError, UnicodeError) as error:
        raise ValueError('Invalid Mellow backup file.') from error


def replace(store, data):
    data = validate(data)
    with store.db:
        for table, columns in TABLES.items():
            store.db.execute('DELETE FROM ' + table)
            store.db.executemany('INSERT INTO ' + table + '(' + ','.join(columns) + ') VALUES ('
                + ','.join('?' for _ in columns) + ')',
                [tuple(row[column] for column in columns) for row in data[table]])
