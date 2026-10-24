"""Quiet shared chrome. PDF page colors remain controlled by theme.py."""
PALETTES={
 'Light':dict(bg='#f4f5f7',surface='#ffffff',text='#30363c',muted='#626c74',line='#dce0e4',hover='#e9edf0',accent='#426f62',onaccent='#ffffff'),
 'Sepia':dict(bg='#f8efda',surface='#fff5df',text='#634f38',muted='#826e50',line='#e2d4b6',hover='#efe1c1',accent='#79613e',onaccent='#fff8e9'),
 'Black':dict(bg='#000000',surface='#111111',text='#eeeeee',muted='#bdbdbd',line='#383838',hover='#252525',accent='#b6c9bd',onaccent='#121a15'),
 'Dark':dict(bg='#242622',surface='#2d302a',text='#e8e4d9',muted='#b1b7a9',line='#454b3f',hover='#3a4134',accent='#b6c9a2',onaccent='#242b20'),
}

# Tabs, toolbar, their fields and shared action menus keep one stable palette.
CHROME=dict(bg='#ece8de',surface='#f6f2e9',text='#4a443a',muted='#655d50',
            line='#d4cdbf',hover='#eae4d8',accent='#786a54',onaccent='#ffffff',input='#fffcf5',
            tab='#e2ddd2',active_tab='#d6d0c2',tab_hover='#dcd5c8',
            active_tab_hover='#cbc2b2',pressed='#dad1bf',checked='#e3dccd')


def chrome_stylesheet():
    return '''
    QWidget {{ color:{text}; }}
    QWidget#tabstrip,QTabBar {{ background:{bg}; }}
    QWidget#readingToolbar {{ background:{surface}; border-bottom:1px solid {line}; }}
    QLabel[role="muted"] {{ color:{muted}; }}
    QTabBar::tab {{ color:{muted}; background:{tab}; padding:1px 11px; border-top-left-radius:5px; border-top-right-radius:5px; }}
    QTabBar::tab:selected {{ color:{text}; background:{active_tab}; border-bottom-color:{accent}; }}
    QTabBar::tab:hover {{ color:{text}; background:{tab_hover}; }}
    QTabBar::tab:selected:hover {{ background:{active_tab_hover}; }}
    QToolButton#captionMenuButton {{ padding:3px; }}
    QToolButton:hover,QToolButton:focus {{ background:{hover}; }}
    QToolButton:checked {{ background:{checked}; }}
    QToolButton:pressed {{ background:{pressed}; }}
    QToolButton:checked,QToolButton:focus {{ border-color:{accent}; }}
    QToolButton:focus,QTabBar::tab:focus {{ outline:1px solid {accent}; }}
    QToolButton[readingButton="true"] {{ background:{input}; border:1px solid {line}; border-radius:5px; padding:2px; }}
    QToolButton[readingButton="true"]:hover {{ background:{hover}; border-color:#bfb4a2; }}
    QToolButton[readingButton="true"]:checked {{ background:{checked}; border-color:{accent}; }}
    QToolButton[readingButton="true"]:focus {{ background:{hover}; border-color:{accent}; outline:1px solid {accent}; }}
    QToolButton[readingButton="true"]:pressed {{ background:{pressed}; border-color:#ac9d86; }}
    QToolButton[readingButton="true"]:disabled {{ background:transparent; border-color:#e7e0d4; }}
    QWidget#readingControlGroup {{ border-right-color:{line}; }}
    QComboBox,QLineEdit,QSpinBox {{ color:{text}; background:{input}; padding:2px 7px; border-color:{line}; selection-background-color:{accent}; selection-color:{onaccent}; }}
    QComboBox:hover,QLineEdit:focus,QSpinBox:focus {{ border-color:{accent}; }}
    QComboBox QAbstractItemView {{ color:{text}; background:{input}; selection-background-color:{hover}; selection-color:{text}; }}
    QToolButton:disabled {{ color:{muted}; }}
    '''.format(**CHROME)


def stylesheet(theme):
    from .theme import normalize_theme,COLORS
    theme=normalize_theme(theme)
    c=PALETTES[theme]
    c=dict(c)
    c['accent_hover']={'Light':'#375d53','Sepia':'#644e30','Black':'#c5d4ca','Dark':'#c3d4b2'}[theme]
    c['scroll_bg']=COLORS[theme][1]
    c['scroll_thumb']={'Light':'#b8bec5','Sepia':'#d1bd95','Black':'#666666','Dark':'#626e57'}[theme]
    return '''
    QWidget {{ color:{text}; }}
    QMainWindow,QDialog,QWidget#home,QWidget#homeContent,QWidget#tabstrip,QWidget#infoContent {{ background:{bg}; }}
    QDialog#locationsPanel {{ border:1px solid {line}; }}
    QToolBar,QWidget#readingToolbar {{ background:{surface}; border:0; border-bottom:1px solid {line}; spacing:3px; padding:3px 8px; }}
    QWidget#readingToolbar {{ padding:0; }}
    QToolBar::separator {{ width:1px; background:{line}; margin:6px 5px; }}
    QWidget#readingControlGroup {{ border-right:1px solid {line}; }}
    QToolButton {{ border:0; border-radius:5px; background:transparent; padding:6px; }}
    QToolButton::menu-indicator {{ image:none; width:0px; }}
    QToolButton#tabCloseButton {{ padding:0; }}
    QToolButton:hover {{ background:{hover}; }}
    QToolButton:focus {{ background:{hover}; outline:1px solid {accent}; }}
    QPushButton:focus,QCheckBox:focus,QTabBar::tab:focus {{ outline:1px solid {accent}; }}
    QToolButton:checked {{ background:{hover}; border:1px solid {accent}; }}
    QToolButton:disabled,QPushButton:disabled {{ color:{muted}; }}
    QPushButton {{ border:1px solid {line}; border-radius:6px; background:{surface}; padding:7px 12px; }}
    QPushButton:hover {{ background:{hover}; border-color:{accent}; }}
    QPushButton#primary {{ background:{accent}; border-color:{accent}; color:{onaccent}; font-weight:600; }}
    QPushButton#primary:hover {{ background:{accent_hover}; border-color:{accent_hover}; }}
    QComboBox,QLineEdit,QSpinBox {{ border:1px solid {line}; border-radius:5px; background:{surface}; padding:5px 7px; selection-background-color:{accent}; selection-color:{onaccent}; }}
    QComboBox:hover,QLineEdit:focus,QSpinBox:focus {{ border-color:{accent}; }}
    QComboBox::drop-down {{ border:0; width:18px; }}
    QComboBox#pageNumber {{ padding:5px; }}
    QComboBox#pageNumber::drop-down {{ border:0; width:0; }}
    QComboBox#pageNumber::down-arrow {{ image:none; }}
    QTabBar {{ background:{bg}; }}
    QTabBar::tab {{ color:{muted}; background:transparent; border-bottom:2px solid transparent; padding:6px 11px; margin:2px 1px 0 1px; }}
    QTabBar::tab:selected {{ color:{text}; background:{surface}; border-bottom-color:{accent}; border-top-left-radius:5px; border-top-right-radius:5px; }}
    QTabBar::tab:hover {{ background:{hover}; }}
    QLabel[role="title"] {{ color:{text}; font-size:23px; font-weight:600; }}
    QLabel[role="section"] {{ color:{text}; font-weight:600; }}
    QLabel[role="muted"] {{ color:{muted}; }}
    QListWidget,QTreeView {{ background:{surface}; border:1px solid {line}; border-radius:7px; outline:0; padding:3px; }}
    QListWidget::item {{ padding:10px 9px; border-radius:4px; }}
    QListWidget::item:hover {{ background:{hover}; }}
    QListWidget::item:selected,QTreeView::item:selected {{ background:{hover}; color:{text}; }}
    QTreeView::item:hover {{ background:{hover}; }}
    QTreeView::item:focus,QListWidget::item:focus {{ border-left:2px solid {accent}; }}
    QListWidget#locationEntries {{ border:0; border-radius:0; padding:0; }}
    QListView#pageThumbnails {{ background:{surface}; border:1px solid {line}; border-radius:6px; outline:0; }}
    QListView#searchResults {{ background:{surface}; border:1px solid {line}; border-radius:6px; outline:0; padding:3px; }}
    QListView#searchResults::item:hover,QListView#searchResults::item:selected {{ background:{hover}; color:{text}; }}
    QListView#searchResults::item:focus {{ border-left:2px solid {accent}; }}
    QListView#pageThumbnails::item {{ border:1px solid transparent; border-radius:5px; }}
    QListView#pageThumbnails::item:hover {{ background:{hover}; }}
    QListView#pageThumbnails::item:selected {{ background:{accent}; color:{onaccent}; }}
    QListWidget#homeEntries {{ background:{bg}; border:0; border-radius:0; padding:0; }}
    QFrame#continueStrip {{ border-top:1px solid {line}; border-bottom:1px solid {line}; }}
    QMenu {{ background:{surface}; border:1px solid {line}; padding:5px; }}
    QMenu::item {{ padding:7px 24px 7px 12px; border-radius:4px; }}
    QMenu::item:selected {{ background:{hover}; }}
    QMenu::separator {{ height:1px; background:{line}; margin:4px; }}
    QTabWidget::pane {{ border:1px solid {line}; background:{bg}; border-radius:6px; }}
    QTabWidget QScrollArea {{ border:0; background:{bg}; }}
    QTabWidget QScrollArea > QWidget > QWidget {{ background:{bg}; }}
    QKeySequenceEdit {{ background:{surface}; border:1px solid {line}; border-radius:5px; }}
    QLabel[role="error"] {{ color:#b04838; }}
    QScrollBar:vertical {{ background:{scroll_bg}; width:12px; margin:0; border:0; }}
    QScrollBar:horizontal {{ background:{scroll_bg}; height:12px; margin:0; border:0; }}
    QScrollBar::handle:vertical {{ background:{scroll_thumb}; min-height:28px; border-radius:4px; margin:2px; }}
    QScrollBar::handle:horizontal {{ background:{scroll_thumb}; min-width:28px; border-radius:4px; margin:2px; }}
    QScrollBar::add-line,QScrollBar::sub-line {{ width:0; height:0; border:0; background:none; }}
    QScrollBar::add-page,QScrollBar::sub-page {{ background:none; }}
    QAbstractScrollArea::corner {{ background:{scroll_bg}; border:0; }}
    QToolTip {{ color:{text}; background:{surface}; border:1px solid {line}; padding:4px; }}
    QSplitter::handle {{ background:{line}; }}
    QSplitter#homeColumns::handle {{ background:transparent; }}
    QSplitter#homeColumns::handle:hover {{ background:{line}; }}
    '''.format(**c) + '''
    QMenu {{ color:{text}; background:{input}; border-color:{line}; }}
    QMenu::item:selected {{ color:{text}; background:{hover}; }}
    QMenu::item:disabled {{ color:{muted}; }}
    QMenu::separator {{ background:{line}; }}
    '''.format(**CHROME)
