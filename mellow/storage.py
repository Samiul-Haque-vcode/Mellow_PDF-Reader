import json
import math
import sqlite3
from pathlib import Path
from .saved_locations import path_key,destination_key,rewrite_paths,document_paths

class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY, kind TEXT NOT NULL, path TEXT NOT NULL,
            page INTEGER NOT NULL, title TEXT NOT NULL, x REAL DEFAULT 0, y REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS history (path TEXT PRIMARY KEY, page INTEGER DEFAULT 0,
            x REAL DEFAULT 0,y REAL DEFAULT 0,visited TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS document_options(path TEXT PRIMARY KEY,page_layout TEXT NOT NULL);''')
        options_columns={row[1] for row in self.db.execute('PRAGMA table_info(document_options)')}
        if 'cover' not in options_columns:
            with self.db:self.db.execute('ALTER TABLE document_options ADD COLUMN cover INTEGER DEFAULT 1')
        for name in ('crop','numbering'):
            if name not in options_columns:
                with self.db:self.db.execute(f'ALTER TABLE document_options ADD COLUMN {name} TEXT')
        location_columns={row[1] for row in self.db.execute('PRAGMA table_info(locations)')}
        if 'label' not in location_columns:
            with self.db: self.db.execute('ALTER TABLE locations ADD COLUMN label TEXT')
        with self.db: self.db.execute('CREATE INDEX IF NOT EXISTS locations_path_page ON locations(path,page)')
        columns={row[1] for row in self.db.execute('PRAGMA table_info(history)')}
        if 'state' not in columns:
            with self.db: self.db.execute('ALTER TABLE history ADD COLUMN state TEXT')
    def set(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, json.dumps(value)))
    def get(self, key, default=None):
        row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default
    def add(self, kind, path, page, title, x=0, y=0, label=None):
        with self.db:
            cursor=self.db.execute('INSERT INTO locations(kind,path,page,title,x,y,label) VALUES(?,?,?,?,?,?,?)',
                                   (kind, str(Path(path).resolve()), page, title, x, y, label))
            return cursor.lastrowid
    def locations(self, kind, path=None):
        sql, args = 'SELECT * FROM locations WHERE kind=?', [kind]
        if path is not None:
            sql += ' AND path=?'
            args.append(path)
        return [dict(r) for r in self.db.execute(sql + ' ORDER BY id DESC', args)]
    def matching_locations(self,kind,path,page,x=0,y=0,exclude=None):
        target=dict(kind=kind,path=path,page=page,x=x,y=y)
        key=destination_key(target)
        if key is None:return []
        # Query metadata candidates only; no document/text extraction.
        rows=self.db.execute('SELECT * FROM locations WHERE kind=? AND page=? ORDER BY id DESC',(kind,page))
        return [dict(row) for row in rows if row['id']!=exclude and destination_key(dict(row))==key]
    def update_labels(self,path,labels):
        # Only saved destinations need labels; never persist a full PDF page map.
        with self.db:
            self.db.executemany('UPDATE locations SET label=? WHERE path=? AND page=? AND (label IS NULL OR label!=?)',
                                [(label,path,page,label) for page,label in labels.items()])
    def document_layout(self,path):
        path=str(Path(path).resolve())
        row=self.db.execute('SELECT page_layout FROM document_options WHERE path=?',(path,)).fetchone()
        modes=('continuous','single','two','two_continuous')
        if row and row[0] in modes:return row[0]
        saved=self.db.execute('SELECT state FROM history WHERE path=?',(path,)).fetchone()
        try:
            state=json.loads(saved[0]) if saved and saved[0] else None
            if isinstance(state,dict) and state.get('layout') in modes:return state['layout']
        except (TypeError,ValueError):pass
        return self.default_layout()
    def default_layout(self):
        value=self.get('default_layout','continuous')
        return value if value in ('continuous','single','two','two_continuous') else 'continuous'
    def set_document_layout(self,path,layout):
        if layout not in ('continuous','single','two','two_continuous'): raise ValueError('Unknown page layout')
        with self.db:
            self.db.execute('INSERT INTO document_options(path,page_layout) VALUES(?,?) ON CONFLICT(path) DO UPDATE SET page_layout=excluded.page_layout',(str(Path(path).resolve()),layout))
    def document_cover(self,path):
        row=self.db.execute('SELECT cover FROM document_options WHERE path=?',(str(Path(path).resolve()),)).fetchone()
        return bool(row[0]) if row else True
    def set_document_cover(self,path,separate,layout=None):
        with self.db:
            self.db.execute("INSERT INTO document_options(path,page_layout,cover) VALUES(?,?,?) ON CONFLICT(path) DO UPDATE SET cover=excluded.cover",(str(Path(path).resolve()),layout or self.document_layout(path),int(bool(separate))))
    def rename(self, ident, title):
        with self.db:
            self.db.execute('UPDATE locations SET title=? WHERE id=?', (title, ident))
    def document_option(self,path,name):
        from .reading_options import crop_values,numbering_values
        validator={'crop':crop_values,'numbering':numbering_values}[name]
        row=self.db.execute(f'SELECT {name} FROM document_options WHERE path=?',(str(Path(path).resolve()),)).fetchone()
        try:return validator(json.loads(row[0])) if row and row[0] else ((0.,0.,0.,0.) if name=='crop' else None)
        except (ValueError,TypeError):return (0.,0.,0.,0.) if name=='crop' else None
    def set_document_option(self,path,name,value,layout=None):
        from .reading_options import crop_values,numbering_values
        validator={'crop':crop_values,'numbering':numbering_values}[name]
        value=validator(value)
        with self.db:
            self.db.execute(f"INSERT INTO document_options(path,page_layout,{name}) VALUES(?,?,?) ON CONFLICT(path) DO UPDATE SET {name}=excluded.{name}",
                            (str(Path(path).resolve()),layout or self.document_layout(path),json.dumps(value)))
    def refresh_history_labels(self,path,label_for):
        row=self.recent(path)
        if not row or not row.get('state'):return
        state=row['state'];label=label_for(row['page'])
        if state.get('label')==label:return
        state['label']=label
        with self.db:self.db.execute('UPDATE history SET state=? WHERE path=?',(json.dumps(state),str(Path(path).resolve())))
    def remove(self, ident):
        with self.db:
            self.db.execute('DELETE FROM locations WHERE id=?', (ident,))
    def relocate(self, old, new):
        old_input=str(old)
        old,new=str(Path(old).resolve()),str(Path(new).resolve())
        if path_key(old)==path_key(new):return new
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            session=self.get('session',{})
            paths={row[0] for row in self.db.execute('SELECT path FROM locations UNION SELECT path FROM history UNION SELECT path FROM document_options')}
            paths.update(document_paths(session))
            if any(path_key(path)==path_key(new) for path in paths):
                raise ValueError('The selected PDF already has saved reading data. Choose the moved original in another location to avoid combining documents.')
            aliases={path for path in paths if path_key(path)==path_key(old)}|{old,old_input}
            # Never replace a target row: a collision or any later failure
            # rolls back locations, preferences, history and session together.
            for source in aliases:
                self.db.execute('UPDATE locations SET path=? WHERE path=?',(new,source))
                self.db.execute('UPDATE document_options SET path=? WHERE path=?',(new,source))
                self.db.execute('UPDATE history SET path=? WHERE path=?',(new,source))
            row=self.recent(new)
            if row and row.get('state'):
                state=rewrite_paths(row['state'],old,new)
                self.db.execute('UPDATE history SET state=? WHERE path=?',(json.dumps(state),new))
            rewritten=rewrite_paths(session,old,new)
            if rewritten!=session:
                self.db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(rewritten),'session'))
        return new
    def export_favorites(self, path):
        Path(path).write_text(json.dumps(self.locations('favorite'), indent=2), encoding='utf8')
    def import_favorites(self, path):
        limit=32*1024*1024
        with Path(path).open('rb') as source:content=source.read(limit+1)
        if len(content)>limit:raise ValueError('Favorites file exceeds the 32 MB limit')
        def reject_constant(value):raise ValueError('Invalid number in Favorites file')
        try:data=json.loads(content,parse_constant=reject_constant)
        except (UnicodeError,RecursionError) as error:raise ValueError('Invalid Favorites file') from error
        if not isinstance(data,list) or len(data)>100000:raise ValueError('Invalid Favorites file')
        validated=[]
        def text(value):return isinstance(value,str) and len(value)<=100000 and '\x00' not in value
        for r in data:
            if not isinstance(r,dict) or not text(r.get('path')) or not r['path'] or not text(r.get('title')):
                raise ValueError('Invalid Favorite entry')
            page=r.get('page');label=r.get('label')
            if type(page) is not int or not 0<=page<1000000:raise ValueError('Invalid page')
            if label is not None and not text(label):raise ValueError('Invalid page label')
            coordinates=[]
            for key in ('x','y'):
                value=r.get(key,0)
                if type(value) not in (int,float) or abs(value)>1e9 or not math.isfinite(value):
                    raise ValueError('Invalid Favorite position')
                coordinates.append(float(value))
            validated.append((r['path'],page,r['title'],*coordinates,label))
        with self.db:
            self.db.executemany("INSERT INTO locations(kind,path,page,title,x,y,label) VALUES('favorite',?,?,?,?,?,?)", validated)

    def record_history(self,path,page=None,x=0,y=0,state=None):
        if self.get('history_paused',False): return
        path=str(Path(path).resolve())
        with self.db:
            if page is None and state is None:
                # Merely reopening a path must not erase its saved reading position.
                self.db.execute("INSERT INTO history(path,visited) VALUES(?,strftime('%Y-%m-%d %H:%M:%f','now')) ON CONFLICT(path) DO UPDATE SET visited=excluded.visited",(path,))
            else:
                self.db.execute("INSERT OR REPLACE INTO history(path,page,x,y,visited,state) VALUES(?,?,?,?,strftime('%Y-%m-%d %H:%M:%f','now'),?)",
                                (path,0 if page is None else page,x,y,json.dumps(state) if state else None))
            self.db.execute('DELETE FROM history WHERE path NOT IN (SELECT path FROM history ORDER BY visited DESC,rowid DESC LIMIT 200)')
    @staticmethod
    def _recent_row(row):
        data=dict(row)
        try: data['state']=json.loads(data['state']) if data.get('state') else None
        except (ValueError,TypeError): data['state']=None
        return data
    def recent(self,path):
        row=self.db.execute('SELECT * FROM history WHERE path=?',(str(Path(path).resolve()),)).fetchone()
        return self._recent_row(row) if row else None
    def forget_recent(self,path):
        with self.db: self.db.execute('DELETE FROM history WHERE path=?',(str(Path(path).resolve()),))
    def clear_history(self):
        # Pause as well so open tabs cannot immediately recreate cleared rows.
        with self.db:
            self.db.execute('DELETE FROM history')
            self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('history_paused','true'))
    def history(self):
        return [self._recent_row(r) for r in self.db.execute('SELECT * FROM history ORDER BY visited DESC,rowid DESC')]
