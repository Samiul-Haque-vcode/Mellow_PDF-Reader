"""Named, persisted keyboard bindings shared by controls and reading panes."""
import weakref
from PySide6.QtGui import QKeySequence
from shiboken6 import isValid

# Stable IDs are stored instead of translated labels or QAction indexes.
COMMANDS={
 'open':('Open PDFs','General','Ctrl+O'),
 'reopen':('Reopen closed tab','General','Ctrl+Shift+T'),
 'tab_next':('Next document tab','General','Ctrl+Tab'),
 'tab_previous':('Previous document tab','General','Ctrl+Shift+Tab'),
 'focus_next':('Focus next reading area','Interface','F6'),
 'focus_previous':('Focus previous reading area','Interface','Shift+F6'),
 'document_info':('Document information','General',''),
 'page_numbering':('Page numbering','Reading',''),
 'page_thumbnails':('Page preview','Reading',''),
 'auto_scroll':('Start / pause auto-scroll','Reading',''),
 'reading_margins':('Trim reading margins','Reading',''),
 'reset_margins':('Reset reading margins','Reading',''),
 'home':('Home','General','Alt+Home'),
 'settings':('Settings','General','Ctrl+,'),
 'fullscreen':('Fullscreen','Interface','F11'),
 'chrome':('Show / hide controls','Interface','Ctrl+Shift+H'),
 'back':('Back through visited locations','Reading','Alt+Left'),
 'forward':('Forward through visited locations','Reading','Alt+Right'),
 'previous':('Previous page','Reading','PgUp'),
 'next':('Next page','Reading','PgDown'),
 'zoom_out':('Zoom out','Reading','Ctrl+-'),
 'zoom_in':('Zoom in','Reading','Ctrl+='),
 'search':('Search PDF','Reading','Ctrl+F'),
 'magnifier':('Magnifying Lens','Reading',''),
 'zoom_lock':('Lock Zoom','Reading',''),
 'chapter_previous':('Previous Chapter','Reading',''),
 'chapter_next':('Next Chapter','Reading',''),
 'copy':('Copy selected PDF text','Reading','Ctrl+C'),
 'select_page':('Select current page text','Reading','Ctrl+A'),
 'select_document':('Select entire PDF text','Reading','Ctrl+Shift+A'),
 'find_selection':('Find selected text','Reading','Ctrl+F3'),
 'rotate_left':('Rotate view left','Reading','Ctrl+Shift+-'),
 'rotate_right':('Rotate view right','Reading','Ctrl+Shift+='),
 'screen_next':('Scroll forward one screen','Reading','Space'),
 'screen_previous':('Scroll back one screen','Reading','Shift+Space'),
 'line_up':('Scroll up a line','Reading','Up'),
 'line_down':('Scroll down a line','Reading','Down'),
 'page_left':('Previous page (arrow)','Reading','Left'),
 'page_right':('Next page (arrow)','Reading','Right'),
 'bookmarks':('Bookmarks','Reading','Ctrl+B'),
 'favorites':('Favorites','Reading','Ctrl+Shift+F'),
 'ruler':('Reading ruler','Reading','Ctrl+R'),
 'marker_save':('Set Quick Jump','Reading','Ctrl+M'),
 'marker_return':('Return to Quick Jump','Reading','Ctrl+Shift+M'),
 'exit_split':('Exit split view','Split view',''),
 'split':('Split view menu','Split view',''),
 'swap':('Swap panes','Split view',''),
 'maximize':('Maximize / restore pane','Split view',''),
 'orientation':('Change split orientation','Split view',''),
 'extract':('Split / extract pages','PDF tools',''),
 'merge':('Merge PDFs','PDF tools',''),
 'images':('Images to PDF','PDF tools',''),
}
FORMAT=QKeySequence.SequenceFormat.PortableText


def normalize(value):
    result=QKeySequence.fromString(value,FORMAT).toString(FORMAT)
    if value.strip() and not result: raise ValueError('Invalid keyboard shortcut.')
    return result


def bindings(overrides=None):
    result={key:default for key,(_,_,default) in COMMANDS.items()}
    if overrides:
        if not isinstance(overrides,dict): raise ValueError('Invalid keyboard shortcut settings.')
        for key,value in overrides.items():
            if key not in COMMANDS or not isinstance(value,str): raise ValueError('Unknown keyboard shortcut.')
            result[key]=normalize(value)
    return result


def migrate_navigation(overrides):
    """Preserve older custom keys when adding navigation/focus defaults."""
    if not isinstance(overrides,dict): return overrides
    result=dict(overrides)
    for key in ('tab_next','tab_previous','focus_next','focus_previous','select_document'):
        if key in result: continue
        default=QKeySequence(COMMANDS[key][2])
        if any(isinstance(value,str) and default.matches(QKeySequence(value))==QKeySequence.SequenceMatch.ExactMatch
               for value in result.values()):
            result[key]=''
    return result


def validate(overrides):
    result=bindings(overrides)
    used=[]
    reserved={'Esc','Ctrl+X','Ctrl+V','Ctrl+Z','Ctrl+Y','Alt+F4','Tab','Shift+Tab','Return','Enter','Backspace','Delete'}
    for key,value in result.items():
        if not value: continue
        seq=QKeySequence(value)
        if seq.isEmpty() or seq.count()!=1 or seq[0].key()==0 or seq[0].key()==0x1ffffff:
            raise ValueError(f'Choose a single valid key combination for {COMMANDS[key][0]}.')
        # Plain printable keys must remain available to text fields and search.
        combo=seq[0]
        from PySide6.QtCore import Qt
        scoped={'screen_next','screen_previous','line_up','line_down','page_left','page_right'}
        if key not in scoped and combo.keyboardModifiers() in (Qt.KeyboardModifier.NoModifier,Qt.KeyboardModifier.ShiftModifier) and combo.key() in (Qt.Key.Key_Up,Qt.Key.Key_Down,Qt.Key.Key_Left,Qt.Key.Key_Right):
            raise ValueError('Plain arrow keys are reserved for focused reading commands.')
        if combo.keyboardModifiers() in (Qt.KeyboardModifier.NoModifier,Qt.KeyboardModifier.ShiftModifier) and 32<=combo.key()<127 and not (key in scoped and combo.key()==Qt.Key.Key_Space):
            raise ValueError('Use Ctrl, Alt or a function key instead of a plain typing key.')
        if value in reserved or (value=='Ctrl+C' and key!='copy') or (value=='Ctrl+A' and key!='select_page'):
            raise ValueError(f'{value} is reserved for editing text or closing a window.')
        for other,previous in used:
            if seq.matches(previous)!=QKeySequence.SequenceMatch.NoMatch or previous.matches(seq)!=QKeySequence.SequenceMatch.NoMatch:
                raise ValueError(f'{value} is assigned to both {COMMANDS[other][0]} and {COMMANDS[key][0]}.')
        used.append((key,seq))
    return result


class ShortcutManager:
    def __init__(self,overrides=None):
        try: self.bindings=validate(migrate_navigation(overrides or {}))
        except (ValueError,TypeError): self.bindings=bindings()
        self.actions={key:[] for key in COMMANDS}
    def register(self,key,action):
        self.actions[key].append(weakref.ref(action))
        self._apply(key,action)
        return action
    def _apply(self,key,action):
        action.setShortcut(QKeySequence(self.bindings[key]))
        label=COMMANDS[key][0]
        native=QKeySequence(self.bindings[key]).toString(QKeySequence.SequenceFormat.NativeText)
        action.setToolTip(f'{label} ({native})' if native else label)
    def apply(self,overrides):
        self.bindings=validate(overrides)
        for key,refs in self.actions.items():
            live=[]
            for ref in refs:
                action=ref()
                if action is not None and isValid(action):
                    live.append(ref)
                    self._apply(key,action)
            self.actions[key]=live


def category(key):
    if key in ('marker_save','marker_return'):return 'Quick Jump'
    if key in ('copy','find_selection','select_page','select_document'):return 'Text Selection and Copying'
    group=COMMANDS[key][1]
    return {'General':'Documents and Tabs','Reading':'Navigation and Zoom',
            'Interface':'Window and Fullscreen','Split view':'Split Reading','PDF tools':'PDF Tools'}[group]
