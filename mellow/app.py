import os
import sys
import time
import sqlite3
from pathlib import Path
from shiboken6 import isValid
from PySide6.QtCore import Qt, QStandardPaths, QPointF, QTimer, QModelIndex, QEvent, QSize, QFile, QIODevice,Signal
from PySide6.QtGui import QActionGroup, QAction, QKeySequence, QPdfWriter, QPainter, QImage, QPageSize
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QTabBar,
    QToolBar, QSpinBox, QComboBox, QFileDialog, QMessageBox, QInputDialog, QMenu,
    QSplitter, QSplitterHandle, QDialog, QListWidget, QLineEdit, QPushButton,
    QHBoxLayout, QLabel, QStackedWidget, QStyle, QToolButton)
from .storage import Store
from .saved_locations import path_key,rewrite_paths
from .reader import Reader
from .theme import COLORS, INK, normalize_theme, theme_tunings
from . import utilities
from .references import Target, ReferenceResolver
from .preview import PreviewDialog
from .jobs import FileJob
from .config import data_directory,fullscreen_hide_delay
from .home import Home
from .icons import icon,application_icon
from .style import CHROME,stylesheet,chrome_stylesheet
from .settings import SettingsDialog
from .about import AboutDialog
from .shortcuts import ShortcutManager,validate as validate_shortcuts,migrate_navigation
from .tool_dialog import ToolDialog
from .search import SearchDialog,InlineSearch,SearchPanel
from .toolbar import ReadingToolbar
from .document_info import DocumentInfoDialog
from .locations import LocationsPanel
from .display import window_record,screen_records,restored_bounds
from .caption import CaptionTabs,DocumentTabs,CaptionMenuButton
from .window_effects import WindowEffects
from .reading_options import page_index,crop_values,numbering_values
from .page_preferences import MarginsDialog,NumberingDialog
from .pages import PagesPanel,ArrangePagesDialog
from .autoscroll import AutoScroll,scroll_speed
from .dialogs import DismissibleDialog,DismissibleInputDialog

class Handle(QSplitterHandle):
    def mouseDoubleClickEvent(self, event):
        self.splitter().balanceRequested.emit()
class Splitter(QSplitter):
    balanceRequested=Signal()
    def createHandle(self):
        return Handle(self.orientation(), self)

class Window(QMainWindow):
    def __init__(self, store=None, restore=True, portable=False):
        super().__init__()
        self.setWindowTitle('Mellow PDF Reader — A softer way to read')
        self.setWindowIcon(application_icon())
        self._toolbar_icon_names={}
        self.resize(1150, 850)
        data = data_directory(portable)
        self.store = store or Store(data/'mellow.sqlite3')
        saved_keys=self.store.get('shortcuts',{})
        migrated_keys=migrate_navigation(saved_keys)
        if migrated_keys!=saved_keys: self.store.set('shortcuts',migrated_keys)
        self.shortcuts=ShortcutManager(migrated_keys)
        self.docs, self.readers = [], []
        self.active = None
        self.secondary = None
        self.popups = []
        self.reference_jobs = []
        self.file_jobs = []
        self._closing = False
        self._pending_backup_data = None
        self._backup_restored = False
        self._on_home = True
        self._home_states = []
        self._document_actions = []
        self._search_open = False
        self.closed_tabs=[]
        self._chrome_overlay=False
        self._fullscreen_snapshots=None
        self._resize_snapshots=[]
        self._display_states=[]
        self._display_restoring=False
        self._fullscreen_was_maximized=False
        self._fullscreen_target_size=None
        self._fullscreen_windowed_size=None
        self._fullscreen_windowed_geometry=None
        self._fullscreen_native_bounds=None
        self._fullscreen_initial_size=None
        self._fullscreen_observed_size=None
        self._fullscreen_updates=None
        self._fullscreen_active=None
        self.window_effects=WindowEffects(self)
        self._fullscreen_deadline=0
        self._chrome_pointer_inside=False
        self.sync_timer=QTimer(self)
        self.sync_timer.setInterval(24)
        self.sync_timer.setSingleShot(True)
        self.sync_timer.timeout.connect(self.sync)
        self._toolbar_signature=None
        self.theme_name = normalize_theme(self.store.get('theme','Sepia'))
        self.preserve = self.store.get('preserve', True)
        self.fullscreen_autohide=self.store.get('fullscreen_autohide',True)
        root = QWidget()
        layout = QVBoxLayout(root)
        self._root_layout=layout
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        self.tabs = DocumentTabs()
        self.tabs.setAccessibleName('Open PDF documents')
        self.tabs.setTabsClosable(False)
        self.tabs.setExpanding(False)
        self.tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self.tab_menu)
        self.tabs.currentChanged.connect(self.select)
        self.tabs.tabBarClicked.connect(self.tab_clicked)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        tabrow = QHBoxLayout()
        tabrow.setContentsMargins(0,0,0,0)
        self.brand_mark=QLabel()
        self.brand_mark.setPixmap(application_icon().pixmap(22,22))
        self.brand_mark.setFixedSize(30,28)
        self.brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_mark.setToolTip('Mellow PDF Reader')
        self.brand_mark.setAccessibleName('Mellow PDF Reader')
        tabrow.addWidget(self.brand_mark)
        tabrow.addWidget(self.tabs)
        plus=QToolButton()
        self.add_tab_button=plus
        plus.setIcon(icon('plus'))
        plus.setIconSize(QSize(16,16))
        plus.setFixedSize(28,28)
        self.open_action=QAction('Open PDFs',self)
        self.open_action.setIcon(icon('plus'))
        self.open_action.triggered.connect(self.open_dialog)
        self.shortcuts.register('open',self.open_action)
        self.addAction(self.open_action)
        plus.setDefaultAction(self.open_action)
        plus.setAccessibleName('Open PDFs')
        tabrow.addWidget(plus)
        tabrow.addStretch()
        self.tabstrip = QWidget()
        self.tabstrip.setObjectName('tabstrip')
        self.tabstrip.setLayout(tabrow)
        self.tabstrip.setStyleSheet(chrome_stylesheet())
        self.caption_tabs=CaptionTabs(self,self.tabstrip,self.store.get('caption_tabs',True))
        layout.addWidget(self.tabstrip)
        self.toolbar = ReadingToolbar()
        self.toolbar.setStyleSheet(chrome_stylesheet())
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        layout.addWidget(self.toolbar)
        self.splitter = Splitter(Qt.Orientation.Horizontal)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.splitter)
        self.home = Home()
        self.home.openRequested.connect(self.open_dialog)
        self.home.resumeRequested.connect(self.resume_reading)
        self.home.settingsRequested.connect(self.settings_dialog)
        self.home.recentRequested.connect(self.open_recent)
        self.home.favoriteRequested.connect(self.open_saved)
        self.home.manageFavoritesRequested.connect(lambda: self.locations('favorite'))
        self.home.toolRequested.connect(self.home_tool)
        self.home.recentRemoved.connect(self.remove_recent)
        self.home.historyRequested.connect(self.history_dialog)
        self.home.folderRequested.connect(self.show_in_folder)
        self.pages.addWidget(self.home)
        self.pages.setCurrentWidget(self.home)
        layout.addWidget(self.pages,1)
        self.setCentralWidget(root)
        self.auto_scroll=AutoScroll(self,self.store.get('auto_scroll_speed',24))
        self.splitter.balanceRequested.connect(lambda:self.set_split_proportion(50))
        self.splitter.splitterMoved.connect(lambda *_:self.sync_split_proportions())
        home_action=self.action('Home',self.show_home,'Alt+Home')
        self.home_action=home_action
        home_action.setIconVisibleInMenu(True)
        self.back_action=self.action('Back', lambda: self.run(lambda r: r.back()), 'Alt+Left', reading=True)
        self.forward_action=self.action('Forward', lambda: self.run(lambda r: r.forward()), 'Alt+Right', reading=True)
        self.previous_action=self.action('‹', lambda: self.run(lambda r: r.jump(r.pageNavigator().currentPage()-1)), 'PgUp', reading=True)
        self.page = QComboBox()
        self.page.setObjectName('pageNumber')
        self.page.setEditable(True)
        self.page.setFixedWidth(64)
        self.page.lineEdit().setAlignment(Qt.AlignmentFlag.AlignRight)
        self.page.setAccessibleName('Printed page label or physical page number')
        self.page.lineEdit().returnPressed.connect(self.go_page)
        self.page_total=QLabel()
        self.page_total.setProperty('role','muted')
        self.next_action=self.action('›', lambda: self.run(lambda r: r.jump(r.pageNavigator().currentPage()+1)), 'PgDown', reading=True)
        self.zoom_out_action=self.action('−', lambda: self.run(lambda r: r.zoom_by(1/1.2)), 'Ctrl+-', reading=True)
        self.zoom_in_action=self.action('+', lambda: self.run(lambda r: r.zoom_by(1.2)), 'Ctrl+=', reading=True)
        self.fit = QComboBox()
        self.fit.addItems(['Fit Page','Fit Width','Actual Size','50%','75%','125%','150%','200%'])
        self.fit.setFixedWidth(110)
        self.fit.setEditable(True)
        self.fit.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.fit.lineEdit().returnPressed.connect(self.set_zoom_text)
        self.fit.activated.connect(self.set_fit)
        self.search_action=self.action('Search', lambda:self.search_dialog(), 'Ctrl+F', reading=True)
        self.bookmarks_action=self.action('Bookmarks', lambda: self.locations('bookmark'), 'Ctrl+B', reading=True)
        self.favorites_action=self.action('Favorites', lambda: self.locations('favorite'), 'Ctrl+Shift+F')
        self.ruler_action = self.action('Ruler', self.toggle_ruler, 'Ctrl+R', reading=True)
        self.ruler_action.setText('Reading Ruler')
        self.ruler_action.setCheckable(True)
        self.inline_search=InlineSearch()
        self.inline_search.activated.connect(self.find_activated)
        self.inline_search.resultsRequested.connect(self.search_results)
        more = QMenu(self)
        self.more_menu=more
        more.aboutToShow.connect(self.sync_menu)
        document_menu=more.addMenu('Document')
        self.document_menu=document_menu
        self.info_action=self.menu_command(document_menu,'document_info',self.document_info)
        self._document_actions.append(self.info_action)
        self.numbering_action=self.menu_command(document_menu,'page_numbering',self.numbering_dialog)
        self._document_actions.append(self.numbering_action)
        self._document_actions.append(document_menu.addAction('Show in folder',lambda:self.show_in_folder(self.active.path)))
        self.reopen_action=self.menu_command(document_menu,'reopen',self.reopen_closed_tab)
        self.reopen_action.setEnabled(False)
        self.tab_next_action=self.menu_command(None,'tab_next',lambda:self.cycle_tab(1))
        self.tab_previous_action=self.menu_command(None,'tab_previous',lambda:self.cycle_tab(-1))
        more.addSeparator()
        reading=more.addMenu('Reading')
        self.reading_menu=reading
        self.pages_action=self.menu_command(None,'page_thumbnails',self.page_thumbnails)
        self._document_actions.append(self.pages_action)
        self.auto_scroll_action=self.menu_command(None,'auto_scroll',self.toggle_auto_scroll)
        self.auto_scroll_action.setText('Auto-scroll');self.auto_scroll_action.setCheckable(True)
        self.auto_scroll.changed.connect(self.update_auto_scroll)
        self._document_actions.append(self.auto_scroll_action)
        self._toolbar_icon_names[self.auto_scroll_action]='auto_scroll'
        self.zoom_menu=QMenu('Zoom',self)
        zoom=self.zoom_menu
        zoom.addAction(self.zoom_out_action);zoom.addAction(self.zoom_in_action);zoom.addSeparator()
        self.fit_actions={};self.fit_action_group=QActionGroup(self)
        for index,name in enumerate(['Fit Page','Fit Width','Actual Size']):
            action=zoom.addAction(name,lambda checked=False,i=index:self.set_fit(i))
            action.setCheckable(True);self.fit_actions[name]=action
            self.fit_action_group.addAction(action);self._document_actions.append(action)
        self.custom_zoom_action=zoom.addAction('Custom zoom…',self.zoom_prompt)
        self._document_actions.append(self.custom_zoom_action)
        self.rotation_actions=[]
        for key,delta in [('rotate_left',-90),('rotate_right',90)]:
            action=self.menu_command(None,key,lambda checked=False,d=delta:self.run(lambda r:r.rotate_by(d)))
            self._document_actions.append(action);self._toolbar_icon_names[action]=key;self.rotation_actions.append(action)
        self._document_actions.append(self.menu_command(None,'marker_save',self.save_marker))
        self._document_actions.append(self.menu_command(None,'marker_return',self.return_marker))
        self.fullscreen_action=self.menu_command(None,'fullscreen',self.fullscreen)
        self.fullscreen_action.setCheckable(True);self.fullscreen_action.setAutoRepeat(False)
        self.menu_command(None,'chrome',self.toggle_chrome).setAutoRepeat(False)
        self.lens_action=self.menu_command(reading,'magnifier',self.toggle_magnifier)
        self.lens_action.setCheckable(True)
        self.lock_zoom_action=self.menu_command(reading,'zoom_lock',self.toggle_zoom_lock)
        self.lock_zoom_action.setCheckable(True)
        reading.addAction(self.ruler_action)
        reading.addSeparator()
        self.chapter_previous_action=self.menu_command(reading,'chapter_previous',lambda:self.chapter_step(-1))
        self.chapter_next_action=self.menu_command(reading,'chapter_next',lambda:self.chapter_step(1))
        self._document_actions.extend([self.lens_action,self.lock_zoom_action,self.chapter_previous_action,self.chapter_next_action])
        reading.aboutToShow.connect(self.update_controls)
        self.layout_menu=more.addMenu('Page layout')
        self.layout_group=QActionGroup(self)
        self.layout_actions={}
        for key,title in [('continuous','Continuous'),('single','Single Page'),('two','Two Pages'),('two_continuous','Two Pages Continuous')]:
            action=self.layout_menu.addAction(title,lambda checked=False,k=key:self.set_page_layout(k))
            action.setCheckable(True)
            self.layout_group.addAction(action)
            self.layout_actions[key]=action
            self._document_actions.append(action)
        self.layout_menu.addSeparator()
        self.cover_action=self.layout_menu.addAction('Show cover separately',self.set_cover)
        self.cover_action.setCheckable(True)
        self._document_actions.append(self.cover_action)
        self.layout_menu.aboutToShow.connect(self.update_controls)
        self.margins_action=self.menu_command(None,'reading_margins',self.margins_dialog)
        self.reset_margins_action=self.menu_command(None,'reset_margins',lambda:self.apply_margins((0,0,0,0)))
        self._document_actions.extend([self.margins_action,self.reset_margins_action])
        split_menu=QMenu('Split view',self)
        self.split_menu=split_menu
        self.split_choices=split_menu.addMenu('Open side by side')
        self.split_choices.aboutToShow.connect(self.populate_split_choices)
        self.proportions_menu=split_menu.addMenu('Pane proportions')
        self.ratio_group=QActionGroup(self)
        self.ratio_actions={}
        for portion in (50,60,70):
            action=self.proportions_menu.addAction(f'{portion}:{100-portion}',lambda checked=False,p=portion:self.set_split_proportion(p))
            action.setCheckable(True)
            action.setToolTip('Size of the left / top pane; restores both panes if one is maximized.')
            self.ratio_group.addAction(action)
            self.ratio_actions[portion]=action
        split_menu.addSeparator()
        self.split_actions=[]
        for key,callback in [('exit_split',self.exit_split),('swap',self.swap),
                             ('maximize',self.maximize_pane),('orientation',self.orientation)]:
            self.split_actions.append(self.menu_command(split_menu,key,callback))
        self.split_menu_action=self.menu_command(None,'split',self.show_split_menu)
        self.split_menu_action.setText('Split view')
        self.split_menu_action.setMenu(split_menu)
        self.split_menu_action.setCheckable(True)
        self._document_actions.append(self.split_menu_action)
        self._toolbar_icon_names[self.split_menu_action]='split'
        self._toolbar_icon_names[self.fullscreen_action]='fullscreen'
        tools=more.addMenu('PDF Tools')
        for key,callback in [('extract',self.extract),('merge',self.merge),('images',self.images)]:
            self.menu_command(tools,key,callback)
        # Retained as a shared compatibility action; the visible history switch
        # now lives in General settings.
        self.history_pause_action=QAction('Pause recording',self)
        self.history_pause_action.setCheckable(True)
        self.history_pause_action.toggled.connect(self.pause_history)
        self.overflow_menu=more.addMenu('More reading controls')
        more.aboutToShow.connect(self.populate_overflow)
        more.addSeparator()
        settings_action=self.menu_command(more,'settings',self.settings_dialog)
        settings_action.setIcon(icon('settings'))
        self._toolbar_icon_names[settings_action]='settings'
        more.addAction('About / Credits…',self.about_dialog)
        act = QAction('Menu',self)
        self.more_action=act
        self.addAction(act)
        act.setToolTip('Menu')
        self._toolbar_icon_names[act]='menu'
        act.setMenu(more)
        self.more_button=CaptionMenuButton()
        self.more_button.setObjectName('captionMenuButton')
        self.more_button.setMenu(more)
        self.more_button.setDefaultAction(act)
        self.more_button.setAccessibleName('Menu')
        self.more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_button.setIconSize(QSize(18,18))
        self.more_button.setFixedSize(32,28)
        tabrow.insertWidget(1,self.more_button)
        self.pane_indicator=QLabel()
        self.pane_indicator.setProperty('role','muted')
        self.build_toolbar()
        self.focus_next_action=self.menu_command(None,'focus_next',lambda:self.cycle_focus(1))
        self.focus_previous_action=self.menu_command(None,'focus_previous',lambda:self.cycle_focus(-1))
        self.chrome_timer = QTimer(self)
        self.chrome_timer.setSingleShot(True)
        self.chrome_timer.setInterval(fullscreen_hide_delay(self.store.get('fullscreen_hide_delay',600)))
        self.chrome_timer.timeout.connect(self.hide_chrome)
        self.chrome_restore_timer=QTimer(self)
        self.chrome_restore_timer.setSingleShot(True)
        self.chrome_restore_timer.setInterval(0)
        self.chrome_restore_timer.timeout.connect(self.finish_fullscreen_transition)
        QApplication.instance().installEventFilter(self)
        escape = QAction(self)
        self.escape_action=escape
        escape.setShortcut(QKeySequence('Escape'))
        escape.triggered.connect(self.escape)
        self.addAction(escape)
        # Native Windows menus can become visible before a widget Show event
        # reaches the application filter. Pause before any owned menu opens.
        for menu in self.findChildren(QMenu):
            menu.aboutToShow.connect(self.auto_scroll.pause)
        self.apply_interface_options()
        self.change_theme(self.theme_name)
        self.home.refresh(self.store.history(),False,self.store.locations('favorite'))
        self.update_controls()
        self.toolbar.hide()
        if restore:
            QTimer.singleShot(0,self.startup)
    def action(self, text, callback, shortcut=None, reading=False):
        a = QAction(text,self)
        a.triggered.connect(callback)
        icons={'Home':'home','Open':'open','Back':'back','Forward':'forward','‹':'previous','›':'next',
               '−':'minus','+':'plus','Search':'search','Bookmarks':'outline','Favorites':'star','Ruler':'ruler'}
        if text in icons: self._toolbar_icon_names[a]=icons[text]
        name={'‹':'Previous page','›':'Next page','−':'Zoom out','+':'Zoom in'}.get(text,text)
        a.setToolTip(f'{name} ({shortcut})' if shortcut else name)
        ids={'Home':'home','Open':'open','Back':'back','Forward':'forward','‹':'previous','›':'next',
             '−':'zoom_out','+':'zoom_in','Search':'search','Bookmarks':'bookmarks','Favorites':'favorites','Ruler':'ruler'}
        if text in ids: self.shortcuts.register(ids[text],a)
        self.addAction(a)
        if reading: self._document_actions.append(a)
        return a
    def menu_command(self,menu,key,callback):
        from .shortcuts import COMMANDS
        action=QAction(COMMANDS[key][0],self)
        action.triggered.connect(callback)
        if menu is not None: menu.addAction(action)
        self.shortcuts.register(key,action)
        self.addAction(action)
        return action
    def build_toolbar(self):
        bar=self.toolbar
        bar.command('home',self.home_action)
        self.page_caption=QLabel('Page:')
        self.page_caption.setBuddy(self.page)
        bar.group('page',[self.page_caption,self.page,self.page_total,self.previous_action,self.next_action],compact=True)
        bar.group('zoom',[self.zoom_out_action,self.fit,self.zoom_in_action],60,compact=True)
        bar.group('history',[self.back_action,self.forward_action],80)
        bar.group('rotation',self.rotation_actions,20,compact=True)
        bar.control('inline_search',self.inline_search)
        bar.command('bookmarks',self.bookmarks_action,70)
        bar.command('favorites',self.favorites_action,65)
        bar.command('auto_scroll',self.auto_scroll_action,45)
        bar.command('split',self.split_menu_action,40)
        bar.command('fullscreen',self.fullscreen_action,50)
        bar.control('pane',self.pane_indicator,100)
        bar.stretch()
        bar.available('pane',False)
        self.inline_search.geometryChanged.connect(lambda:bar.timer.start(0))
    def cycle_tab(self,delta):
        if len(self.readers)<2: return
        if self.active and not self._on_home: self.active.flush_zoom()
        self.tabs.setCurrentIndex((self.tabs.currentIndex()+delta)%len(self.readers))
    def document_info(self):
        if not self.active or self._on_home: return
        dialog=DocumentInfoDialog(self.active,self)
        dialog.exec()
        dialog.deleteLater()
    def reader_margins(self,reader):
        if reader in self.readers or reader is self.secondary:
            self.focus_reader(reader)
            self.margins_dialog()
        elif any(p.reader is reader for p in self.popups) and reader.document():
            dialog=MarginsDialog(reader,reader.window())
            if dialog.exec()==QDialog.DialogCode.Accepted and isValid(reader) and reader.document():
                reader.change_crop(dialog.margins())
            dialog.deleteLater()

    def margins_dialog(self):
        if not self.active or self._on_home:return
        dialog=MarginsDialog(self.active,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.apply_margins(dialog.margins())
        dialog.deleteLater()
    def apply_margins(self,margins):
        if not self.active or self._on_home:return
        margins=crop_values(margins)
        self.active.change_crop(margins)
        self.store.set_document_option(self.active.path,'crop',margins,layout=self.active.page_layout_mode)
        self.update_controls()
    def numbering_dialog(self):
        if not self.active or self._on_home:return
        dialog=NumberingDialog(self.active,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.apply_numbering(dialog.mapping())
        dialog.deleteLater()
    def apply_numbering(self,mapping):
        if not self.active or self._on_home:return
        mapping=numbering_values(mapping)
        if mapping and mapping['pdf']>=self.active.document().pageCount():raise ValueError('PDF page is outside this document.')
        self.store.set_document_option(self.active.path,'numbering',mapping,layout=self.active.page_layout_mode)
        self.active.document()._mellow_numbering=mapping
        self.refresh_saved_labels()
        self._toolbar_signature=None
        self.page.lineEdit().clearFocus()
        self.sync()
        if self.home.isVisible():self.refresh_home()
    def populate_split_choices(self):
        self.split_choices.clear()
        if not self.active or self._on_home: return
        for reader in self.readers:
            path=reader.path
            name=Path(path).name+(' (independent view)' if path==self.active.path else '')
            action=self.split_choices.addAction(name,lambda checked=False,p=path:self.open_side_by_side(p))
            action.setToolTip(path)
    def open_side_by_side(self,path):
        if not self.active or self._on_home: return
        snapshot=self.active.state()
        first=next((i for i,r in enumerate(self.readers) if r.path==self.active.path),None)
        second=next((i for i,r in enumerate(self.readers) if r.path==path),None)
        if first is None or second is None: return
        self.split(first,second)
        self.readers[first].restore(snapshot,defer=True)
        if path==snapshot['path']: self.secondary.restore(snapshot,defer=True)
    def show_split_menu(self):
        if not self.active or self._on_home: return
        button=self.toolbar.widgetForAction(self.split_menu_action)
        if not button.isVisible(): button=self.more_button
        self.split_menu.popup(button.mapToGlobal(button.rect().bottomLeft()))
    def pause_history(self,paused):
        self.store.set('history_paused',paused)
        if self._on_home: self.refresh_home()
    def sync_menu(self):
        self.history_pause_action.blockSignals(True)
        self.history_pause_action.setChecked(self.store.get('history_paused',False))
        self.history_pause_action.blockSignals(False)
    def populate_overflow(self):
        menu=self.overflow_menu;menu.clear()
        groups={'zoom':[self.zoom_menu.menuAction()],'history':[self.back_action,self.forward_action],
                'rotation':self.rotation_actions,'bookmarks':[self.bookmarks_action],
                'favorites':[self.favorites_action],'auto_scroll':[self.auto_scroll_action],
                'split':[self.split_menu.menuAction()],'fullscreen':[self.fullscreen_action]}
        if not self._on_home:
            for key in self.toolbar.entries:
                if key in self.toolbar.collapsed:
                    for action in groups.get(key,[]):menu.addAction(action)
        menu.menuAction().setVisible(bool(menu.actions()))

    def clear_reading_history(self,dialog):
        answer=QMessageBox.question(dialog,'Clear reading history?',
            'Clear Recent PDFs and pause recording? PDF files, Favorites, bookmarks and sessions will be kept.',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if answer!=QMessageBox.StandardButton.Yes:return
        self.store.clear_history()
        dialog.record_history.setChecked(False)
        dialog._baseline['history_paused']=True
        dialog.update_dirty();self.refresh_home()

    def toggle_magnifier(self):
        self.run(lambda r:r.aids.set_lens_enabled(not r.aids.lens_enabled))
        self.update_controls()
    def toggle_zoom_lock(self):
        self.run(lambda r:r.set_zoom_locked(not r.zoom_locked))
        self.update_controls()
    def chapter_step(self,direction):
        self.run(lambda r:r.aids.chapter_step(direction))

    def apply_interface_options(self):
        labels=self.store.get('toolbar_labels',False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon if labels else Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.timer.start(0)
    def run(self, callback):
        self.auto_scroll.pause()
        if self.active and not self._on_home:
            callback(self.active)
    def update_controls(self):
        enabled=not self._on_home and self.active is not None
        self.add_tab_button.setVisible(not self._on_home)
        for reader in self.readers+([self.secondary] if self.secondary else []):
            reader.set_pane_active(bool(enabled and self.secondary is not None and reader is self.active))
        for action in self._document_actions: action.setEnabled(enabled)
        self.document_menu.setEnabled(enabled or bool(self.closed_tabs))
        self.layout_menu.setEnabled(enabled)
        for name,action in self.layout_actions.items():
            action.setChecked(bool(enabled and (self.active._pending or {}).get('layout',self.active.page_layout_mode)==name))
        self.cover_action.setChecked(bool(enabled and self.active.cover_separate))
        self.cover_action.setEnabled(bool(enabled and self.active.facing_pages))
        self.reset_margins_action.setEnabled(bool(enabled and any(self.active.crop)))
        self.page.setEnabled(enabled)
        locked=bool(enabled and self.active.zoom_locked)
        self.fit.setEnabled(enabled and not locked)
        for action in [self.zoom_in_action,self.zoom_out_action,self.custom_zoom_action,*self.fit_actions.values()]:action.setEnabled(enabled and not locked)
        self.lock_zoom_action.setChecked(locked)
        self.lens_action.setChecked(bool(enabled and self.active.aids.lens_enabled))
        self.chapter_previous_action.setEnabled(bool(enabled and self.active.aids.chapter_target(-1) is not None))
        self.chapter_next_action.setEnabled(bool(enabled and self.active.aids.chapter_target(1) is not None))
        self.reading_menu.setEnabled(enabled)
        self.page_total.setVisible(enabled)
        self.tab_next_action.setEnabled(len(self.readers)>1)
        self.tab_previous_action.setEnabled(len(self.readers)>1)
        self.inline_search.bind(self.active if enabled else None)
        self.toolbar.available('inline_search',enabled)
        self.fullscreen_action.setChecked(self.isFullScreen())
        self.split_menu_action.setChecked(self.secondary is not None)
        self.split_choices.setEnabled(enabled)
        self.proportions_menu.setEnabled(enabled and self.secondary is not None)
        self.sync_split_proportions()
        if enabled:
            self.back_action.setEnabled(bool(self.active._past))
            self.forward_action.setEnabled(bool(self.active._future))
            page=self.active.pageNavigator().currentPage()
            self.previous_action.setEnabled(page>0)
            self.next_action.setEnabled(page<self.active.document().pageCount()-1)
            self.ruler_action.setChecked(self.active.ruler)
        for action in self.split_actions: action.setEnabled(enabled and self.secondary is not None)
        self.toolbar.available('pane',enabled and self.secondary is not None)
        if enabled and self.secondary:
            index=self.splitter.indexOf(self.active)
            names=['Left pane','Right pane'] if self.splitter.orientation()==Qt.Orientation.Horizontal else ['Top pane','Bottom pane']
            self.pane_indicator.setText(names[max(0,min(index,1))])
            self.pane_indicator.setToolTip('Toolbar controls '+Path(self.active.path).name)
    def startup(self):
        if self.store.get('restore_session',True): self.restore_session()
        else: self.show_home()
    def remember_reader(self,reader):
        reader.flush_zoom()
        saved=reader.state()
        if self._backup_restored: return saved
        page=saved.get('anchor_page',saved['page'])
        if reader.document(): saved['label']=reader.page_label(page)
        self.store.record_history(reader.path,page,saved.get('x',0),saved.get('y',0),state=saved)
        return saved
    def show_home(self):
        self.auto_scroll.pause()
        self.close_page_thumbnails()
        self.finish_fullscreen_transition(force=True)
        if not self._on_home:
            # Focused pane is written last, so its location is the most recent
            # when the same PDF is visible in two independent panes.
            for reader,_ in self.visible_states(): reader.flush_zoom()
            self._home_states=self.visible_states()
            for reader in self.readers:
                if reader is not self.active: self.remember_reader(reader)
            if self.secondary and self.secondary is not self.active: self.remember_reader(self.secondary)
            if self.active: self.remember_reader(self.active)
            for reader,_ in self._home_states: reader.suspend()
        self._on_home=True
        self.pages.setCurrentWidget(self.home)
        self.sync_timer.stop()
        self.refresh_home()
        self.show_chrome()
        self.update_controls()
    def tab_clicked(self,index):
        if self._on_home and 0<=index<len(self.readers):
            if index==self.tabs.currentIndex(): self.resume_reading()
            else: self.select(index)
    def resume_reading(self):
        if not self.readers: return
        self._on_home=False
        self.pages.setCurrentWidget(self.splitter)
        self.sync_chrome_layout()
        self.tabstrip.setVisible(not self.isFullScreen() or not self.fullscreen_autohide)
        self.toolbar.setVisible(not self.isFullScreen() or not self.fullscreen_autohide)
        if self._home_states:
            for reader,state in self._home_states:
                if reader in self.readers or reader is self.secondary:
                    reader.show()
                    reader.restore(state,defer=True)
        else:
            self.readers[self.tabs.currentIndex()].show()
        self._home_states=[]
        self.update_controls()
        self._toolbar_signature=None
        self.sync()
    def remove_recent(self,path):
        self.store.forget_recent(path)
        self.refresh_home()
    def refresh_home(self):
        self.refresh_saved_labels()
        continuation=None
        if self.active and self.readers:
            state=self.active.state()
            page=state.get('anchor_page',state['page'])
            state['label']=self.active.page_label(page)
            continuation=dict(path=self.active.path,page=page,state=state)
        self.home.refresh(self.store.history(),bool(self.readers),self.store.locations('favorite'),continuation)
    def home_tool(self,name):
        operations={'extract':self.extract,'merge':self.merge,'images':self.images,
                    'export':self.export_favorites,'import':self.import_favorites}
        if name in operations: operations[name]()
    def open_recent(self,saved):
        path=saved['path']
        if not Path(path).is_file():
            path,_=QFileDialog.getOpenFileName(self,'Locate missing PDF','','PDF (*.pdf)')
            if not path: return
            path=self.relocate_pdf(saved['path'],path)
            if not path:return None
            if 'state' in saved:saved=self.store.recent(path) or saved
        state=saved.get('state') or dict(page=saved['page'],x=saved.get('x',0),y=saved.get('y',0))
        state=dict(state,path=str(Path(path).resolve()),layout=self.store.document_layout(path),cover=self.store.document_cover(path))
        margins=self.store.document_option(path,'crop')
        if tuple(state.get('crop',()))!=margins:state.update(crop=list(margins),viewport=None)
        return self.open_pdf(path,state=state)
    def relocate_pdf(self,old,new):
        """Validate the user's chosen PDF before changing any saved paths."""
        new=str(Path(new).resolve())
        if any(path_key(r.path)==path_key(old) for r in self.readers):
            self.error('Close the tab for this missing PDF before locating its new file.')
            return None
        if any(path_key(r.path)==path_key(new) for r in self.readers):
            self.error('The selected PDF is already open with its own reading state. Choose the moved original.')
            return None
        source=QFile(new)
        probe=QPdfDocument()
        try:
            if not source.open(QIODevice.OpenModeFlag.ReadOnly):
                raise ValueError('Cannot read the selected PDF. Saved paths were kept.')
            probe.load(source)
            error=probe.error()
            # A protected PDF is recognizable before asking for its password
            # in the normal opening flow; never prompt twice just to relink.
            if error not in (QPdfDocument.Error.None_,QPdfDocument.Error.IncorrectPassword) or error==QPdfDocument.Error.None_ and probe.pageCount()==0:
                raise ValueError('The selected file is not a readable PDF. Saved paths were kept.')
        except (ValueError,OSError) as error:
            self.error(error)
            return None
        finally:
            probe.close()
            source.close()
        try:
            self.store.relocate(old,new)
        except (ValueError,OSError,sqlite3.Error) as error:
            self.error(error)
            return None
        self.closed_tabs=rewrite_paths(self.closed_tabs,old,new)
        self.refresh_home()
        return new
    def about_dialog(self):
        dialog=AboutDialog(self)
        dialog.exec()
        dialog.deleteLater()
    def settings_dialog(self):
        dialog=SettingsDialog(self.store,self)
        dialog.backupRequested.connect(lambda:self.backup_data(dialog))
        dialog.restoreRequested.connect(lambda:self.restore_data(dialog))
        dialog.clearHistoryRequested.connect(lambda:self.clear_reading_history(dialog))
        dialog.exportFavoritesRequested.connect(self.export_favorites)
        dialog.importFavoritesRequested.connect(self.import_favorites)
        if dialog.exec(): self.apply_settings(dialog.values())
        dialog.deleteLater()
    def backup_data(self,dialog):
        import sqlite3
        from datetime import date
        from PySide6.QtCore import QStandardPaths
        from . import backup
        suggested=Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation))/f'Mellow-{date.today()}.mellow-backup.json'
        path,_=QFileDialog.getSaveFileName(dialog,'Create Mellow backup',str(suggested),'Mellow backup (*.mellow-backup.json)')
        if not path:return
        if not path.lower().endswith('.json'):path+='.mellow-backup.json'
        try:
            self.save_session()
            backup.write(self.store,path)
        except (OSError,ValueError,TypeError,sqlite3.Error) as error:
            QMessageBox.warning(dialog,'Backup failed',str(error))
            return
        QMessageBox.information(dialog,'Backup saved',f'Backup saved to:\n{path}\n\nKeep this file for use after reinstalling. PDFs remain in their original folders.')
    def restore_data(self,dialog):
        from . import backup
        if self.file_jobs or any(tool._job is not None for tool in self.findChildren(ToolDialog)):
            QMessageBox.warning(dialog,'Restore backup','Finish or cancel running PDF tools before restoring.')
            return
        path,_=QFileDialog.getOpenFileName(dialog,'Restore Mellow backup','','Mellow backup (*.mellow-backup.json);;JSON files (*.json)')
        if not path:return
        try:data=backup.read(path)
        except (OSError,ValueError) as error:
            QMessageBox.warning(dialog,'Restore failed',str(error))
            return
        favorites=sum(row['kind']=='favorite' for row in data['locations'])
        bookmarks=sum(row['kind']=='bookmark' for row in data['locations'])
        answer=QMessageBox.question(dialog,'Replace local reading data?',
            f'This backup contains {favorites} Favorites, {bookmarks} bookmarks and {len(data["history"])} recent PDFs.\n\n'
            'Restoring replaces your current saved settings and reading data. Mellow will close; reopen it to apply the restored session.\n\n'
            'PDF files are not changed. Continue?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if answer!=QMessageBox.StandardButton.Yes:return
        self._pending_backup_data=data
        dialog.reject()
        QTimer.singleShot(0,self.close)
    def apply_settings(self,values):
        if 'shortcuts' in values: validate_shortcuts(values['shortcuts'])
        self.auto_scroll.pause()
        if 'auto_scroll_speed' in values:values=dict(values,auto_scroll_speed=scroll_speed(values['auto_scroll_speed']))
        if 'fullscreen_hide_delay' in values:values=dict(values,fullscreen_hide_delay=fullscreen_hide_delay(values['fullscreen_hide_delay']))
        for key,value in values.items(): self.store.set(key,value)
        self.preserve=values.get('preserve',self.preserve)
        self.auto_scroll.speed=scroll_speed(self.store.get('auto_scroll_speed',24))
        self.change_theme(values.get('theme',self.theme_name))
        if 'shortcuts' in values: self.shortcuts.apply(values['shortcuts'])
        self.apply_interface_options()
        for reader in self.readers+([self.secondary] if self.secondary else [])+[p.reader for p in self.popups]:
            self.apply_reader_options(reader)
        self.set_autohide(values.get('fullscreen_autohide',self.fullscreen_autohide))
        self.chrome_timer.setInterval(fullscreen_hide_delay(self.store.get('fullscreen_hide_delay',600)))
    def apply_reader_options(self,reader):
        if not getattr(reader,'_shortcut_registered',False):
            for key,action in reader.reading_actions.items(): self.shortcuts.register(key,action)
            reader.findRequested.connect(self.find_selection)
            reader._shortcut_registered=True
        reader.default_copy_format=self.store.get('copy_format','preserve')
        reader.zoom_speed={'Gentle':.65,'Normal':1.0,'Fast':1.5}.get(self.store.get('zoom_speed','Normal'),1.0)
        reader.ruler_height=self.store.get('ruler_height',28)
        reader.ruler_opacity=round(self.store.get('ruler_opacity',14)*2.55)
        reader.viewport().update()
    def queue_sync(self,reader):
        if not self._closing and reader is self.active and not self._on_home and not self.sync_timer.isActive():
            self.sync_timer.start()
    def error(self, text):
        QMessageBox.warning(self, 'Mellow PDF Reader', str(text))
    def open_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, 'Open PDF', '', 'PDF documents (*.pdf)')
        for path in files:
            self.open_pdf(path)
    def open_pdf(self, path, state=None, activate=True):
        path = str(Path(path).resolve())
        if not Path(path).is_file():
            self.error(f'File not found:\n{path}')
            return None
        for i, r in enumerate(self.readers):
            if r.path == path:
                if activate:
                    if self._on_home or self.tabs.currentIndex()==i: self.select(i)
                    self.tabs.setCurrentIndex(i)
                if state: r.restore(state,defer=True)
                return r
        doc = QPdfDocument(self)
        # Own the input device so closing a tab releases its Windows file
        # handle immediately, rather than waiting for Qt's deferred deletion.
        doc.source_file=QFile(path,doc)
        if not doc.source_file.open(QIODevice.OpenModeFlag.ReadOnly):
            self.error(f'Cannot open PDF: {path}\n{doc.source_file.errorString()}')
            doc.deleteLater()
            return None
        doc.load(doc.source_file)
        result=doc.error()
        if result == QPdfDocument.Error.IncorrectPassword:
            password, ok = QInputDialog.getText(self, 'Protected PDF', 'Password:', QLineEdit.EchoMode.Password)
            if ok:
                doc.close()
                doc.source_file.seek(0)
                doc.setPassword(password)
                doc.load(doc.source_file)
                result=doc.error()
        if result != QPdfDocument.Error.None_ or doc.pageCount() == 0:
            self.error(f'Cannot open PDF: {path}\n{result.name}')
            doc.close()
            doc.source_file.close()
            doc.deleteLater()
            return None
        doc._mellow_numbering=self.store.document_option(path,'numbering')
        if doc._mellow_numbering and doc._mellow_numbering['pdf']>=doc.pageCount():doc._mellow_numbering=None
        if state is None:
            recent=self.store.recent(path)
            if recent and recent.get('state'):
                state=dict(recent['state'],layout=self.store.document_layout(path),cover=self.store.document_cover(path))
                margins=self.store.document_option(path,'crop')
                if tuple(state.get('crop',()))!=margins:state.update(crop=list(margins),viewport=None)
        r = self.make_reader(doc, path)
        self.docs.append(doc)
        self.readers.append(r)
        self.refresh_saved_labels()
        self.tabs.blockSignals(True)
        i = self.tabs.addTab(Path(path).name)
        close=QToolButton()
        close.setObjectName('tabCloseButton')
        close.setIcon(icon('close',CHROME['muted']))
        close.setIconSize(QSize(12,12))
        close.setFixedSize(22,22)
        close.setToolTip('Close '+Path(path).name)
        close.setAccessibleName('Close '+Path(path).name)
        close.clicked.connect(lambda checked=False,reader=r: self.close_tab(self.readers.index(reader)) if reader in self.readers else None)
        self.tabs.setTabButton(i,QTabBar.ButtonPosition.RightSide,close)
        self.tabs.blockSignals(False)
        self.tabs.setTabToolTip(i, path)
        if activate:
            self.tabs.blockSignals(True)
            self.tabs.setCurrentIndex(i)
            self.tabs.blockSignals(False)
            self.select(i)
        else:
            r.suspend()
        if state: r.restore(state,defer=activate)
        self.store.record_history(path)

        return r
    def make_reader(self, doc, path):
        r = Reader(doc, path, self)
        r.focused.connect(self.focus_reader)
        r.previewRequested.connect(self.preview)
        r.referenceRequested.connect(self.resolve_reference)
        r.referenceNavigationRequested.connect(lambda reader,label:self.resolve_reference(reader,label,navigate=True))
        r.marginsRequested.connect(self.reader_margins)
        r.aids.changed.connect(lambda:self.queue_sync(r))
        r.zoomLockChanged.connect(lambda *_:self.queue_sync(r))
        r.locationChanged.connect(lambda: self.queue_sync(r))
        r.pageNavigator().currentPageChanged.connect(lambda *_: self.queue_sync(r))
        self.apply_reader_options(r)
        r.cover_separate=self.store.document_cover(path)
        r.set_page_layout(self.store.document_layout(path))
        r.set_crop(self.store.document_option(path,'crop'))
        fit=self.store.get('default_fit','Fit Page')
        if fit=='Fit Width': r.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        elif fit=='Actual Size':
            r.setZoomMode(QPdfView.ZoomMode.Custom)
            r.setZoomFactor(1)
        r.theme(self.theme_name, self.preserve,theme_tunings(self.store.get('theme_tuning',{}))[self.theme_name])
        return r
    def select(self, index, keep_split=False):
        self.auto_scroll.pause()
        self.close_page_thumbnails()
        if not 0 <= index < len(self.readers): return
        self.finish_fullscreen_transition(force=True)
        self._on_home=False
        self._home_states=[]
        self.pages.setCurrentWidget(self.splitter)
        self.sync_chrome_layout()
        self.tabstrip.setVisible(not self.isFullScreen() or not self.fullscreen_autohide)
        self.toolbar.setVisible(not self.isFullScreen() or not self.fullscreen_autohide)
        if not keep_split: self.exit_split()
        target = self.readers[index]
        snapshot = target.state()
        for r in self.readers:
            if r is not target:
                r.suspend()
                r.setParent(self)
        self.splitter.insertWidget(0,target)
        target.show()
        self.focus_reader(target)
        target.restore(snapshot,defer=True)
        self.update_controls()

    def focus_reader(self,r):
        if self._closing:return
        if r is self.active:
            self.queue_sync(r)
            return
        self.auto_scroll.pause()
        self.active=r
        self.update_controls()
        self.sync()
    def sync(self):
        if self._closing:return
        if self._fullscreen_snapshots is not None or self._fullscreen_updates is not None:return
        if not self._display_restoring:self._display_states=self.visible_states()
        self.update_controls()
        if self._on_home or not self.active or not self.active.document(): return
        reader=self.active
        page=reader.pageNavigator().currentPage()
        document=reader.document()
        signature=(id(reader),id(document),page,reader.zoomMode(),round(reader.zoomFactor(),4),reader.viewport().size(),repr(getattr(document,'_mellow_numbering',None)))
        if signature==self._toolbar_signature: return
        self._toolbar_signature=signature
        self.page.blockSignals(True)
        if not self.page.lineEdit().hasFocus(): self.page.setCurrentText(reader.page_label(page))
        self.page.setToolTip(f'Page {reader.page_label(page)} · PDF page {page+1} of {document.pageCount()} · enter a book/printed label or # followed by a PDF page number')
        self.page.blockSignals(False)
        self.page_total.setText(f'PDF {page+1}/{document.pageCount()}' if getattr(document,'_mellow_numbering',None) else f'/ {document.pageCount()}')
        self.page_total.setToolTip(f'PDF page {page+1} of {document.pageCount()}')
        self.page.setAccessibleName(f'Page {reader.page_label(page)} of {document.pageCount()} PDF pages')
        self.toolbar.timer.start(0)
        self.fit.blockSignals(True)
        mode=reader.zoomMode()
        if mode==QPdfView.ZoomMode.FitInView: value='Fit Page'
        elif mode==QPdfView.ZoomMode.FitToWidth: value='Fit Width'
        else: value=f'{reader.zoomFactor()*100:.0f}%'
        if not self.fit.lineEdit().hasFocus(): self.fit.setCurrentText(value)
        self.fit.setToolTip(f'{value} · Current scale: {reader.effective_zoom()*100:.0f}%')
        self.fit.setAccessibleName('Zoom: '+value)
        for name,action in self.fit_actions.items():
            action.setChecked(name==value or name=='Actual Size' and mode==QPdfView.ZoomMode.Custom and abs(reader.zoomFactor()-1)<.0001)
        self.fit.blockSignals(False)
    def go_page(self):
        self.navigate_page_text(self.page.currentText())
    def page_prompt(self):
        if not self.active or self._on_home: return
        text,ok=DismissibleInputDialog.getText(self,'Go to page','Printed page label or # followed by a PDF page number:',
                                   text=self.active.page_label(self.active.pageNavigator().currentPage()))
        if ok: self.navigate_page_text(text)
    def zoom_prompt(self):
        if not self.active or self._on_home or self.active.zoom_locked: return
        value,ok=DismissibleInputDialog.getDouble(self,'Custom zoom','Zoom (%):',self.active.effective_zoom()*100,10,800,1)
        if ok: self.active.zoom_to(value/100)
    def navigate_page_text(self,text):
        if not self.active: return
        text=text.strip()
        document=self.active.document()
        page=page_index(document,text)
        if 0 <= page < document.pageCount(): self.active.jump(page)
        else: self.error('Page label or page number not found.')
        self.sync()
    def set_page_layout(self,name):
        if not self.active or self._on_home or name not in self.layout_actions: return
        self.active.change_layout(name)
        self.store.set_document_layout(self.active.path,name)
        self.update_controls()
    def set_cover(self,separate):
        if not self.active or self._on_home:return
        self.active.change_cover(separate)
        self.store.set_document_cover(self.active.path,separate,layout=self.active.page_layout_mode)
        self.update_controls()
    def set_fit(self,index):
        if self.active and self.active.zoom_locked:return
        if index>=3:
            self.set_zoom_text()
            return
        def apply(r):
            snapshot=r.state()
            if index==2:
                r.setZoomMode(QPdfView.ZoomMode.Custom)
                r.setZoomFactor(1)
            else:
                r.setZoomMode([QPdfView.ZoomMode.FitInView,QPdfView.ZoomMode.FitToWidth][index])
            snapshot.update(mode=r.zoomMode().value,zoom=r.zoomFactor(),viewport=None)
            r.restore(snapshot,defer=True)
        self.run(apply)
    def set_zoom_text(self):
        if not self.active: return
        try:
            factor=float(self.fit.currentText().strip().rstrip('%'))/100
            if not .1<=factor<=8: raise ValueError()
        except ValueError:
            self.sync()
            return
        self.active.zoom_to(factor)
    def close_tab(self, index):
        self.auto_scroll.pause()
        self.close_page_thumbnails()
        self.finish_fullscreen_transition(force=True)
        self.readers[index].flush_zoom()
        snapshot=self.readers[index].state(include_history=True)
        self.closed_tabs.append(dict(state=snapshot,index=index))
        self.closed_tabs=self.closed_tabs[-20:]
        self.reopen_action.setEnabled(True)
        was_home=self._on_home
        for job in list(self.reference_jobs):
            job.cancel_ui()
        for popup in list(self.popups): popup.close()
        self.exit_split()
        self.remember_reader(self.readers[index])
        r = self.readers.pop(index)
        doc = self.docs.pop(index)
        self.tabs.blockSignals(True)
        self.tabs.removeTab(index)
        self.tabs.blockSignals(False)
        r.suspend()
        r.setDocument(None)
        r.deleteLater()
        doc.close()
        doc.source_file.close()
        doc.deleteLater()
        self.active = None
        if self.readers:
            if was_home:
                self.active=self.readers[self.tabs.currentIndex()]
                self.show_home()
            else: self.select(self.tabs.currentIndex())
        else:
            self.show_home()
    def reopen_closed_tab(self):
        if not self.closed_tabs: return
        saved=self.closed_tabs[-1]
        state=saved['state']
        reader=self.open_pdf(state['path'],state=state)
        if reader is None: return
        self.closed_tabs.pop()
        index=self.readers.index(reader)
        target=min(saved['index'],len(self.readers)-1)
        # QTabBar is not movable: moving only its visual tab would mismatch the
        # parallel reader/document arrays. Keep all three in the same order.
        if index!=target:
            self.tabs.blockSignals(True)
            self.tabs.moveTab(index,target)
            self.readers.insert(target,self.readers.pop(index))
            self.docs.insert(target,self.docs.pop(index))
            self.tabs.setCurrentIndex(target)
            self.tabs.blockSignals(False)
        self.reopen_action.setEnabled(bool(self.closed_tabs))
    def show_in_folder(self,path):
        from .platform import show_in_folder
        try:
            if not show_in_folder(path): self.error('Could not open the containing folder.')
        except OSError as error: self.error(error)
    def tab_menu(self, point):
        index = self.tabs.tabAt(point)
        menu = QMenu(self)
        menu.addAction(self.reopen_action)
        if index<0:
            menu.exec(self.tabs.mapToGlobal(point))
            return
        side = menu.addMenu('Open Side by Side')
        for j, r in enumerate(self.readers):
            name = Path(r.path).name + (' (independent view)' if j == index else '')
            side.addAction(name, lambda checked=False, a=index, b=j: self.split(a,b))
        menu.addAction('Close', lambda: self.close_tab(index))
        menu.addAction('Show in folder',lambda:self.show_in_folder(self.readers[index].path))
        menu.exec(self.tabs.mapToGlobal(point))
    def split(self,first,second):
        source=self.readers[second]
        snapshot=source.state()
        self.tabs.blockSignals(True)
        self.tabs.setCurrentIndex(first)
        self.tabs.blockSignals(False)
        self.select(first)
        self.secondary=self.make_reader(source.document(),source.path)
        self.splitter.addWidget(self.secondary)
        self.secondary.show()
        self.splitter.setSizes([1000,1000])
        self.secondary.restore(snapshot,defer=True)
        primary=self.readers[first]
        primary.restore(primary.state(),defer=True)
        self.update_controls()
    def exit_split(self):
        self.auto_scroll.pause()
        self.close_page_thumbnails()
        if self.secondary:
            if self.active is self.secondary:
                self.active=self.readers[self.tabs.currentIndex()] if self.readers else None
            self.secondary.suspend()
            self.secondary.setDocument(None)
            self.secondary.setParent(None)
            self.secondary.deleteLater()
            self.secondary=None
        for i in range(self.splitter.count()): self.splitter.widget(i).show()
        self.update_controls()
    def visible_states(self):
        if self._on_home: return []
        views=self.readers+([self.secondary] if self.secondary else [])
        return [(r,r.state()) for r in views if r.isVisible()]
    def restore_visible(self,snapshots):
        for reader,state in snapshots:
            if reader.isVisible(): reader.restore(state,defer=True)
    def swap(self):
        self.auto_scroll.pause()
        if self.secondary:
            snapshots=self.visible_states()
            sizes=self.splitter.sizes()
            self.splitter.insertWidget(0,self.splitter.widget(1))
            # Sizes belong to slots, not books. A temporarily maximized pane
            # has a hidden sibling, whose zero size must not collapse it.
            if all(self.splitter.widget(i).isVisible() for i in range(self.splitter.count())):
                self.splitter.setSizes(sizes)
            self.restore_visible(snapshots)
            self.update_controls()
    def maximize_pane(self):
        self.auto_scroll.pause()
        if not self.secondary: return
        snapshots=self.visible_states()
        other=next((self.splitter.widget(i) for i in range(2) if self.splitter.widget(i) is not self.active),None)
        if other:
            if other.isVisible(): other.suspend()
            else:
                snapshot=other.state()
                other.show()
                other.restore(snapshot,defer=True)
        self.restore_visible(snapshots)
        self.update_controls()
    def orientation(self):
        self.auto_scroll.pause()
        snapshots=self.visible_states()
        self.splitter.setOrientation(Qt.Orientation.Vertical if self.splitter.orientation()==Qt.Orientation.Horizontal else Qt.Orientation.Horizontal)
        self.restore_visible(snapshots)
        self.update_controls()
    def set_split_proportion(self,portion):
        if self.secondary is None or self._on_home or portion not in (50,60,70):return
        self.auto_scroll.pause()
        readers=[self.splitter.widget(i) for i in range(self.splitter.count())]
        for reader in readers:reader.flush_zoom()
        snapshots=[(reader,reader.state()) for reader in readers]
        for reader in readers:reader.show()
        self.splitter.setSizes([portion*100,(100-portion)*100])
        self.restore_visible(snapshots)
        self.update_controls()
    def sync_split_proportions(self):
        sizes=self.splitter.sizes()
        ready=not self._on_home and self.secondary is not None and len(sizes)==2 and all(sizes)
        for portion,action in getattr(self,'ratio_actions',{}).items():
            action.setChecked(bool(ready and abs(sizes[0]-sum(sizes)*portion/100)<=2))
    def update_auto_scroll(self,running):
        self.auto_scroll_action.setChecked(running)
        name='pause' if running else 'auto_scroll'
        self._toolbar_icon_names[self.auto_scroll_action]=name
        self.auto_scroll_action.setIcon(icon(name,CHROME['text']))
        button=self.toolbar.widgetForAction(self.auto_scroll_action)
        label='Pause auto-scroll' if running else 'Start auto-scroll'
        if button:button.setAccessibleName(label)

    def toggle_auto_scroll(self):
        if self.auto_scroll.running:self.auto_scroll.pause()
        elif self.active and not self._on_home:
            self.active.setFocus(Qt.FocusReason.OtherFocusReason)
            self.auto_scroll.start(self.active)
        self.auto_scroll_action.setChecked(self.auto_scroll.running)
    def change_theme(self, name):
        name=normalize_theme(name)
        if self.caption_tabs.enabled:
            # Native caption glyphs follow the fixed light header, even when
            # the PDF and document dialogs use a dark reading theme.
            QApplication.styleHints().setColorScheme(Qt.ColorScheme.Light)
        self.theme_name = name
        c=CHROME
        self.setStyleSheet(stylesheet(name))
        self.home.thumbnail.tuning=theme_tunings(self.store.get('theme_tuning',{}))[name]
        self.home.thumbnail.preserve=self.preserve
        self.home.set_theme(name)
        self.inline_search.set_theme(name)
        self.open_action.setIcon(icon('plus',c['text']))
        for action,key in self._toolbar_icon_names.items(): action.setIcon(icon(key,c['text']))
        for index in range(self.tabs.count()):
            close=self.tabs.tabButton(index,QTabBar.ButtonPosition.RightSide)
            if close: close.setIcon(icon('close',c['muted']))
        for r in self.readers + ([self.secondary] if self.secondary else []):
            r.theme(name,self.preserve,theme_tunings(self.store.get('theme_tuning',{}))[name])
        self.store.set('theme', name)
        self.toolbar.timer.start(0)
        self.caption_tabs.update_space()
    def set_preserve(self, value):
        self.preserve = value
        self.store.set('preserve', value)
        self.change_theme(self.theme_name)
    def escape(self):
        if self.auto_scroll.running:
            self.auto_scroll.pause()
            return
        if self.active and not self._on_home and (self.active._two_point_mode or self.active._copy_job):
            self.active.clear_selection()
            return
        if self.active and self.active.aids.lens_enabled:
            self.active.aids.set_lens_enabled(False);self.update_controls();return
        focused=QApplication.focusWidget()
        if self._search_open and ((focused and self.inline_search.isAncestorOf(focused)) or
                                  not (self.active and self.active.text_selection.ranges)):
            self.close_search()
        elif self.active and not self._on_home and (self.active.text_selection.ranges or self.active._two_point_mode or self.active._copy_job):
            self.active.clear_selection()
        elif self.isFullScreen(): self.fullscreen()
    def fullscreen(self):
        previous=self._fullscreen_snapshots
        self.finish_fullscreen_transition(force=True)
        for reader in self.readers+([self.secondary] if self.secondary else []):
            if reader.isVisible():reader.flush_zoom()
        self._fullscreen_snapshots=previous if previous is not None else self.visible_states()
        self._fullscreen_active=self.active
        self._fullscreen_initial_size=self.size()
        self._fullscreen_observed_size=None
        self._fullscreen_deadline=time.monotonic()+.12
        self.chrome_timer.stop()
        entering=not self.isFullScreen()
        if entering:
            self._fullscreen_was_maximized=self.isMaximized()
            self._fullscreen_windowed_size=self.size()
            self._fullscreen_windowed_geometry=self.geometry()
            self._fullscreen_native_bounds=self.window_effects.capture_bounds()
            self._fullscreen_target_size=self.screen().geometry().size()
        else:self._fullscreen_target_size=self._fullscreen_windowed_size
        # Do not paint an intermediate full-sized PDF with windowed controls,
        # or repeatedly relayout the panes while native frame metrics change.
        self._fullscreen_updates=self.updatesEnabled()
        self.setUpdatesEnabled(False)
        layout_enabled=self._root_layout.isEnabled()
        self._root_layout.setEnabled(False)
        try:
            self.window_effects.begin()
            self.caption_tabs.prepare_fullscreen(entering)
            self.sync_chrome_layout(fullscreen=entering)
            controls=not entering or self._on_home or not self.fullscreen_autohide
            if not controls and self.editing_chrome() and self.active:self.active.setFocus()
            self.tabstrip.setVisible(controls)
            self.toolbar.setVisible(controls and not self._on_home)
            if entering:self.showFullScreen()
            elif self._fullscreen_was_maximized:self.showMaximized()
            else:
                self.showNormal()
                if self._fullscreen_windowed_geometry is not None:
                    self.setGeometry(self._fullscreen_windowed_geometry)
        except BaseException:
            self._root_layout.setEnabled(layout_enabled)
            self.caption_tabs.finish_transition()
            self.show_chrome()
            self.finish_fullscreen_transition(force=True)
            raise
        finally:
            self._root_layout.setEnabled(layout_enabled)
        self._root_layout.activate()
        self.position_chrome()
        # Native showFullScreen is synchronous on common Windows setups. When
        # its exact final bounds are already available, restore before returning
        # to the event loop instead of adding a timer/frame of old PDF position.
        if entering and self.size()==self._fullscreen_target_size:
            self.finish_fullscreen_transition()
        else:self.chrome_restore_timer.start(0)
    def finish_fullscreen_transition(self,force=False):
        if self._fullscreen_snapshots is None: return
        size=self.size()
        if not force and size!=self._fullscreen_target_size and time.monotonic()<self._fullscreen_deadline:
            if size==self._fullscreen_initial_size:
                # A native resize can arrive after the window-state signal.
                self.chrome_restore_timer.start(16)
                return
            if size!=self._fullscreen_observed_size:
                # Caption/frame metrics need not equal the predicted size.
                # Accept an actual changed geometry after one quiet event turn.
                self._fullscreen_observed_size=size
                self.chrome_restore_timer.start(0)
                return
        snapshots=self._fullscreen_snapshots
        self._fullscreen_snapshots=None
        self.chrome_restore_timer.stop()
        try:
            self.caption_tabs.finish_transition()
            # Windows can adjust client bounds while restoring the extended
            # caption. Apply the saved rectangle after those frame flags settle,
            # while painting is still paused, rather than exposing a correction.
            if not self.isFullScreen() and not self._fullscreen_was_maximized:
                native_restored=self.window_effects.restore_bounds(self._fullscreen_native_bounds)
                if (not native_restored and self._fullscreen_windowed_geometry is not None and
                        self.geometry()!=self._fullscreen_windowed_geometry):
                    self.setGeometry(self._fullscreen_windowed_geometry)
            self._root_layout.activate()
            self.position_chrome()
            live=self.readers+([self.secondary] if self.secondary else [])
            for reader,state in snapshots:
                if reader in live and reader.isVisible(): reader.restore_view_anchor(state)
            focused,self._fullscreen_active=self._fullscreen_active,None
            if focused in live and not self._on_home:
                self.focus_reader(focused)
                focused.setFocus(Qt.FocusReason.OtherFocusReason)
            self._display_states=self.visible_states()
        finally:
            if self._fullscreen_updates is not None:
                enabled,self._fullscreen_updates=self._fullscreen_updates,None
                self.setUpdatesEnabled(enabled)
            self.window_effects.finish()
        self._toolbar_signature=None
        self.sync_timer.start(0)
        if self.isFullScreen() and self.toolbar.isVisible():self.schedule_chrome_hide()
    def sync_chrome_layout(self,fullscreen=None):
        overlay=(self.isFullScreen() if fullscreen is None else fullscreen) and not self._on_home and self.fullscreen_autohide
        if overlay!=self._chrome_overlay:
            self._chrome_overlay=overlay
            if overlay:
                self._root_layout.removeWidget(self.tabstrip)
                self._root_layout.removeWidget(self.toolbar)
            else:
                self._root_layout.insertWidget(0,self.tabstrip)
                self._root_layout.insertWidget(1,self.toolbar)
            self._root_layout.activate()
        self.position_chrome()
    def position_chrome(self):
        if not self._chrome_overlay: return
        width=self.centralWidget().width()
        tab_height=self.tabstrip.sizeHint().height()
        tool_height=max(self.toolbar.minimumHeight(),self.toolbar.sizeHint().height())
        self.tabstrip.setGeometry(0,0,width,tab_height)
        self.toolbar.setGeometry(0,tab_height,width,tool_height)
        self.tabstrip.raise_()
        self.toolbar.raise_()
    def resizeEvent(self,event):
        snapshots=getattr(self,'_resize_snapshots',[])
        self._resize_snapshots=[]
        super().resizeEvent(event)
        if hasattr(self,'_chrome_overlay'):
            self.position_chrome()
            if self._fullscreen_snapshots is not None and hasattr(self,'chrome_restore_timer'):
                self.chrome_restore_timer.start(0)
        if snapshots:
            self._root_layout.activate()
            self.restore_visible(snapshots)
    def editing_chrome(self):
        widget=QApplication.focusWidget()
        return widget is not None and (self.tabstrip.isAncestorOf(widget) or self.toolbar.isAncestorOf(widget))
    def cycle_focus(self,delta):
        # Caption/menu, toolbar and each visible pane are separate stops.
        # Window-scoped actions leave dialogs and their text fields alone.
        if self._on_home:
            areas=[self.more_button,self.home.filter]
        else:
            self.show_chrome()
            areas=[self.more_button,self.toolbar.widgetForAction(self.home_action)]
            areas += [self.splitter.widget(i) for i in range(self.splitter.count()) if self.splitter.widget(i).isVisible()]
        areas=[widget for widget in areas if widget and widget.isVisible() and widget.isEnabled()]
        if not areas:return
        focused=QApplication.focusWidget()
        index=next((i for i,widget in enumerate(areas)
                    if focused is widget or (widget is self.toolbar.widgetForAction(self.home_action) and focused and self.toolbar.isAncestorOf(focused))),-1)
        if index<0:index=-1 if delta>0 else 0
        areas[(index+delta)%len(areas)].setFocus(Qt.FocusReason.TabFocusReason if delta>0 else Qt.FocusReason.BacktabFocusReason)
    def pointer_in_chrome(self):
        from PySide6.QtGui import QCursor
        point=self.centralWidget().mapFromGlobal(QCursor.pos())
        return (self.tabstrip.isVisible() and self.tabstrip.geometry().contains(point)) or (self.toolbar.isVisible() and self.toolbar.geometry().contains(point))
    def schedule_chrome_hide(self):
        if self._closing or self._on_home or not self.isFullScreen() or not self.fullscreen_autohide:
            self.chrome_timer.stop()
            return
        if self.toolbar.isVisible(): self.chrome_timer.start()
    def show_chrome(self):
        self.sync_chrome_layout()
        self.tabstrip.show()
        self.toolbar.setVisible(not self._on_home)
        self.position_chrome()
        self.schedule_chrome_hide()
    def set_autohide(self,value):
        changed=value!=self.fullscreen_autohide
        self.finish_fullscreen_transition(force=True)
        snapshots=self.visible_states() if changed and self.isFullScreen() else []
        self.fullscreen_autohide=value
        self.store.set('fullscreen_autohide',value)
        if changed and self.isFullScreen():
            self.show_chrome()
            self._root_layout.activate()
            for reader,state in snapshots: reader.restore_view_anchor(state)
        elif value and self.isFullScreen(): self.schedule_chrome_hide()
        else:
            self.chrome_timer.stop()
            self.show_chrome()
    def hide_chrome(self):
        if self._on_home or not self.isFullScreen() or not self.fullscreen_autohide: return
        if QApplication.activePopupWidget() or QApplication.activeModalWidget():
            self.chrome_timer.start()
            return
        if self.pointer_in_chrome():
            # Blank tab-row space may not send mouse moves. Remember the
            # pointer here so its next move into the page restarts auto-hide.
            self._chrome_pointer_inside=True
            self.chrome_timer.stop()
            return
        if self.editing_chrome():
            self.chrome_timer.stop()
            return
        # Fullscreen controls overlay the page. Visibility changes never resize
        # a reading pane or ask Qt PDF to jump/render that location again.
        self.tabstrip.hide()
        self.toolbar.hide()
        self._chrome_pointer_inside=False
    def toggle_chrome(self):
        if not self.isFullScreen(): return
        if self.toolbar.isVisible():
            self.chrome_timer.stop()
            if self.editing_chrome() and self.active: self.active.setFocus()
            self.tabstrip.hide()
            self.toolbar.hide()
            self._chrome_pointer_inside=False
        else: self.show_chrome()
    def showEvent(self,event):
        super().showEvent(event)
        handle=self.windowHandle()
        if handle is not None and not getattr(self,'_screen_connected',False):
            handle.screenChanged.connect(lambda *_:self.handle_display_change())
            self._screen_connected=True
    def nativeEvent(self,event_type,message):
        caption=getattr(self,'caption_tabs',None)
        if caption is not None:
            result=caption.native_hit_test(message)
            if result is not None:return True,result
        return super().nativeEvent(event_type,message)
    def handle_display_change(self):
        if self._fullscreen_snapshots is not None or self._fullscreen_updates is not None:return
        if self._display_restoring or self._closing:return
        snapshots=self._display_states or self.visible_states()
        self._display_restoring=True
        def finish():
            if not self._closing:
                self.restore_visible(snapshots)
                self._display_restoring=False
                self._toolbar_signature=None
                self.sync_timer.start()
        QTimer.singleShot(0,finish)
    def eventFilter(self,obj,event):
        self.auto_scroll.filter_event(obj,event)
        if obj is self and event.type()==QEvent.Type.DevicePixelRatioChange:self.handle_display_change()
        if (obj is self and event.type()==QEvent.Type.Resize and self._fullscreen_snapshots is None and
                self._fullscreen_updates is None and
                not self._on_home and not self._closing):
            # QMainWindow lays out its children before its virtual resizeEvent.
            # The application filter runs earlier, while source anchors still
            # use the old viewport/fit scale. Fullscreen has its own snapshot.
            for reader,_ in self.visible_states(): reader.flush_zoom()
            self._resize_snapshots=self.visible_states()
        if isinstance(obj,QWidget) and (obj is self or self.isAncestorOf(obj)):
            kind=event.type()
            if kind in (QEvent.Type.MouseButtonPress,QEvent.Type.Wheel,QEvent.Type.KeyPress):
                self.finish_fullscreen_transition(force=True)
            if not self.isFullScreen(): return super().eventFilter(obj,event)
            if kind==QEvent.Type.MouseMove:
                point=obj.mapTo(self.centralWidget(),event.position().toPoint())
                inside=(self.tabstrip.isVisible() and self.tabstrip.geometry().contains(point)) or (self.toolbar.isVisible() and self.toolbar.geometry().contains(point))
                if inside:
                    self.chrome_timer.stop()
                elif self._chrome_pointer_inside:
                    self.schedule_chrome_hide()
                self._chrome_pointer_inside=inside
                if 0<=point.y()<=6 and not self.toolbar.isVisible():
                    self.show_chrome()
                    self._chrome_pointer_inside=True
            elif kind==QEvent.Type.Leave and obj in (self,self.toolbar,self.tabstrip):
                # Leaving onto another monitor may deliver no mouse movement
                # inside this window. Resume the saved auto-hide delay there.
                if self._chrome_pointer_inside and not self.pointer_in_chrome():
                    self._chrome_pointer_inside=False
                    self.schedule_chrome_hide()
            elif kind in (QEvent.Type.FocusIn,QEvent.Type.FocusOut):
                if kind==QEvent.Type.FocusIn and self.editing_chrome(): self.chrome_timer.stop()
                else: QTimer.singleShot(0,self.schedule_chrome_hide)
        return super().eventFilter(obj,event)
    def toggle_ruler(self):
        if self.active:
            self.active.ruler = not self.active.ruler
            self.active.viewport().update()
            self.update_controls()
    def ruler_settings(self):
        if not self.active: return
        height, ok = DismissibleInputDialog.getInt(self,'Reading ruler','Height (pixels)', self.active.ruler_height, 4,200)
        if not ok: return
        opacity, ok = DismissibleInputDialog.getInt(self,'Reading ruler','Opacity (%)', int(self.active.ruler_opacity/2.55), 1,80)
        if ok:
            self.active.ruler_height = height
            self.active.ruler_opacity = int(opacity*2.55)
            self.active.viewport().update()
    def save_marker(self):
        self.run(lambda r:r.set_quick_jump())
    def return_marker(self):
        self.run(lambda r:r.return_quick_jump())
    def find_selection(self,reader,text):
        if not text.strip(): return
        if reader in self.readers or reader is self.secondary: self.focus_reader(reader)
        self.search_dialog(initial=' '.join(text.split()),reader=reader)
    def search_dialog(self,initial=None,reader=None):
        r=reader or self.active
        if r is None: return
        if (r in self.readers or r is self.secondary) and not self._on_home:
            self._search_open=True
            self.update_controls()
            if initial is not None: self.inline_search.text.setText(initial)
            self.toolbar.reflow()
            self.show_chrome()
            self.inline_search.text.setFocus()
            self.inline_search.text.selectAll()
            return
        dialog = SearchDialog(r,initial,self)
        dialog.finished.connect(dialog.deleteLater)
        dialog.show()
    def search_results(self):
        if not self.active or self._on_home:return
        self.close_page_thumbnails()
        dialog=SearchPanel(self.active,self)
        dialog.position_near(self.inline_search)
        dialog.finished.connect(dialog.deleteLater)
        dialog.show()
    def find_activated(self):
        self._search_open=True
    def close_search(self):
        self._search_open=False
        self.update_controls()
        self.toolbar.reflow()
        if self.active and not self._on_home: self.active.setFocus()
        self.schedule_chrome_hide()
    def refresh_saved_labels(self):
        # Reuse already-open PDF engines; unopened Favorites never load a PDF.
        for reader in self.readers:
            document=reader.document()
            saved=self.store.locations('favorite',reader.path)+self.store.locations('bookmark',reader.path)
            labels={}
            for row in saved:
                if 0<=row['page']<document.pageCount():
                    label=reader.page_label(row['page'])
                    if label!=row.get('label'): labels[row['page']]=label
            if labels: self.store.update_labels(reader.path,labels)
            self.store.refresh_history_labels(reader.path,reader.page_label)
    def close_page_thumbnails(self):
        for cls in (PagesPanel,SearchPanel,LocationsPanel):
            for dialog in self.findChildren(cls):dialog.reject()
    def page_thumbnails(self):
        if not self.active or self._on_home:return
        self.active.page_thumbnails()
    def locations(self, kind):
        if kind == 'bookmark' and (not self.active or self._on_home): return
        for existing in self.findChildren(LocationsPanel):existing.reject()
        dialog=LocationsPanel(self,kind)
        action=self.bookmarks_action if kind=='bookmark' else self.favorites_action
        anchor=self.toolbar.widgetForAction(action)
        if self._on_home: anchor=self.home.manage
        elif not anchor or not anchor.isVisible(): anchor=self.more_button
        dialog.position_near(anchor)
        dialog.finished.connect(self.refresh_home)
        dialog.finished.connect(dialog.deleteLater)
        dialog.show()
    def open_in_pane(self,path):
        if self._on_home: return self.open_pdf(path)
        if not self.secondary: return self.open_pdf(path)
        path=str(Path(path).resolve())
        secondary_focused=self.active is self.secondary
        target=self.open_pdf(path,activate=False)
        if not target: return None
        index=self.readers.index(target)
        if secondary_focused:
            if self.secondary.path==path: return self.secondary
            self.secondary.setDocument(target.document())
            self.secondary.links.setDocument(target.document())
            self.secondary.path=path
            self.secondary.restore(target.state(),defer=True)
            self.focus_reader(self.secondary)
            return self.secondary
        self.tabs.blockSignals(True)
        self.tabs.setCurrentIndex(index)
        self.tabs.blockSignals(False)
        self.select(index,keep_split=True)
        return target
    def open_saved(self,saved):
        if self._on_home: return self.open_recent(saved)
        path=saved['path']
        if not Path(path).is_file():
            path,_=QFileDialog.getOpenFileName(self,'Locate missing PDF','','PDF (*.pdf)')
            if not path: return None
            path=self.relocate_pdf(saved['path'],path)
            if not path:return None
        target=self.open_in_pane(path) if self.secondary else self.open_pdf(path)
        if target:
            # Defer past any pending pane layout restore; this is the final requested location.
            target.jump(saved['page'],QPointF(saved.get('x',0),saved.get('y',0)),defer=True)
        return target
    def preview(self,reader,target):
        if target is None:
            page,ok=DismissibleInputDialog.getInt(self,'Reference preview','Preview physical page:',reader.pageNavigator().currentPage()+1,1,reader.document().pageCount())
            if not ok: return
            target=Target(page-1,title=f'Page {page}')
        dialog=PreviewDialog(reader,target,self)
        self.popups.append(dialog)
        dialog.finished.connect(lambda *_: self.popups.remove(dialog) if dialog in self.popups else None)
        dialog.show()
        return dialog
    def preview_opposite(self,source,target):
        if self.secondary:
            other=self.readers[self.tabs.currentIndex()] if source is self.secondary else self.secondary
            self.focus_reader(other)
            other=self.open_in_pane(source.path)
        else:
            index=self.readers.index(source)
            self.split(self.tabs.currentIndex(),index)
            other=self.secondary
        if other:
            other.jump(target.page,target.point(),defer=True)
            self.focus_reader(other)
    def resolve_reference(self,reader,label,navigate=False):
        if not label:
            label,ok=DismissibleInputDialog.getText(self,'Find reference','Reference, such as Figure 3.8 or Equation (2.4):')
            if not ok: return
        from PySide6.QtWidgets import QProgressDialog
        source_document=reader.document()
        try: job=ReferenceResolver(reader.document(),label,reader.pageNavigator().currentPage(),self)
        except ValueError as error: self.error(error); return
        progress=QProgressDialog('Finding matching captions in this PDF…','Cancel',0,reader.document().pageCount(),self)
        progress.setWindowModality(Qt.WindowModality.NonModal)
        progress.setMinimumDuration(300)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        job.progress.connect(lambda current,total: progress.setValue(current))
        cleaned=[False]
        def cleanup():
            if cleaned[0]: return
            cleaned[0]=True
            job.cancel()
            progress.close()
            progress.deleteLater()
            if job in self.reference_jobs: self.reference_jobs.remove(job)
            job.deleteLater()
        def done(targets):
            usable=not self._closing and isValid(reader) and reader.document() is source_document
            cleanup()
            if not usable:return
            if len(targets)==1:
                if navigate:reader.jump(targets[0].page,targets[0].point())
                else:self.preview(reader,targets[0])
            else:
                from .reference_choices import ReferenceChoices
                choices=ReferenceChoices(reader,targets,self)
                if choices.exec():
                    if navigate:
                        target=choices.target
                        if choices.manual:
                            page,ok=DismissibleInputDialog.getInt(self,'Go to Reference','Physical PDF page:',reader.pageNavigator().currentPage()+1,1,reader.document().pageCount())
                            if ok:reader.jump(page-1)
                        elif target:reader.jump(target.page,target.point())
                    else:self.preview(reader,None if choices.manual else choices.target)
                choices.deleteLater()
        job.cancel_ui=cleanup
        job.finished.connect(done)
        progress.canceled.connect(cleanup)
        self.reference_jobs.append(job)
        job.start()
    def history_dialog(self):
        dialog=DismissibleDialog(self)
        dialog.setWindowTitle('Reading history')
        dialog.resize(620,360)
        box=QVBoxLayout(dialog)
        listing=QListWidget()
        rows=[]
        def refresh():
            rows[:]=self.store.history()
            listing.clear()
            for row in rows: listing.addItem(f"{Path(row['path']).name} · page {row['page']+1}")
        refresh()
        box.addWidget(listing)
        def opened():
            index=listing.currentRow()
            if index>=0 and self.open_saved(rows[index]): dialog.accept()
        listing.itemDoubleClicked.connect(lambda *_: opened())
        button=QPushButton('Open saved location')
        button.clicked.connect(opened)
        box.addWidget(button)
        from PySide6.QtWidgets import QCheckBox
        pause=QCheckBox('Pause reading history and Recent PDFs')
        pause.setChecked(self.store.get('history_paused',False))
        pause.toggled.connect(lambda value:self.store.set('history_paused',value))
        box.addWidget(pause)
        clear=QPushButton('Clear history and pause')
        def clear_rows():
            self.store.clear_history()
            pause.setChecked(True)
            refresh()
            self.refresh_home()
        clear.clicked.connect(clear_rows)
        box.addWidget(clear)
        note=QLabel('Clears Recent PDFs only. Favorites, PDFs, open tabs and session restoration remain available.')
        note.setWordWrap(True)
        box.addWidget(note)
        dialog.exec()
        self.refresh_home()
    def export_favorites(self):
        path,_ = QFileDialog.getSaveFileName(self,'Export Favorites','','JSON (*.json)')
        if path:
            try: self.store.export_favorites(path)
            except Exception as e: self.error(e)
    def import_favorites(self):
        path,_ = QFileDialog.getOpenFileName(self,'Import Favorites','','JSON (*.json)')
        if path:
            try:
                self.store.import_favorites(path)
                self.refresh_home()
            except Exception as e: self.error(e)
    def output(self):
        return QFileDialog.getSaveFileName(self,'Save a new PDF','','PDF (*.pdf)')[0]
    def utility_dialog(self,mode):
        paths=[self.active.path] if mode=='extract' and self.active and not self._on_home else []
        dialog=ToolDialog(mode,self,paths)
        if dialog.exec() and dialog.saved_path:
            path=dialog.saved_path
            choice=QMessageBox.question(self,'PDF saved',f'Saved new PDF:\n{path}\n\nOpen it in Mellow?')
            if choice==QMessageBox.StandardButton.Yes: self.open_pdf(path)
        dialog.deleteLater()
    def extract(self):
        self.utility_dialog('extract')
    def merge(self):
        self.utility_dialog('merge')
    def images(self):
        self.utility_dialog('images')
    def start_file_job(self,label,output,operation):
        from PySide6.QtWidgets import QProgressDialog
        dialog=QProgressDialog(label,'Cancel',0,0,self)
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        dialog.setMinimumDuration(0)
        job=FileJob(operation,output,self)
        self.file_jobs.append(job)
        dialog.canceled.connect(job.cancel)
        job.progress.connect(lambda current,total: (dialog.setMaximum(total),dialog.setValue(current)))
        job.failed.connect(self.error)
        job.succeeded.connect(lambda path: QMessageBox.information(self,'PDF saved',f'Saved new PDF:\n{path}'))
        def cleanup():
            dialog.close()
            dialog.deleteLater()
            if job in self.file_jobs: self.file_jobs.remove(job)
            job.deleteLater()
        job.finished.connect(cleanup)
        job.start()
        return job
    def save_session(self):
        if self._backup_restored:return
        active_index=self.tabs.currentIndex()
        for r in self.readers: self.remember_reader(r)
        if self.secondary: self.remember_reader(self.secondary)
        if self.active: self.remember_reader(self.active)
        primary=self.readers[active_index] if self.readers else None
        pane_order=[]
        if self.secondary:
            pane_order=['secondary' if self.splitter.widget(i) is self.secondary else 'primary' for i in range(self.splitter.count())]
        session=dict(window=window_record(self),home=self._on_home,documents=[r.state(include_history=True) for r in self.readers],
                     active_path=primary.path if primary else None,
                     secondary=self.secondary.state(include_history=True) if self.secondary else None,
                     active_secondary=self.active is self.secondary and self.secondary is not None,
                     orientation=self.splitter.orientation().value,sizes=self.splitter.sizes(),pane_order=pane_order)
        self.store.set('session',session)
    def restore_session(self):
        session=self.store.get('session',{})
        bounds=restored_bounds(session.get('window',{}),screen_records(QApplication.screens()))
        if bounds is not None:
            self.setGeometry(bounds)
            if session.get('window',{}).get('maximized'):self.showMaximized()
        wanted=session.get('documents',[])
        missing=[]
        for state in wanted:
            if not Path(state['path']).is_file(): missing.append(state['path']); continue
            self.open_pdf(state['path'],state,activate=False)
        if self.readers:
            active_path=session.get('active_path')
            # Migration from the original index-based format.
            if not active_path and wanted:
                old=min(max(session.get('active',0),0),len(wanted)-1)
                active_path=wanted[old]['path']
            index=next((i for i,r in enumerate(self.readers) if r.path==active_path),0)
            self.tabs.blockSignals(True)
            self.tabs.setCurrentIndex(index)
            self.tabs.blockSignals(False)
            secondary=session.get('secondary')
            target=next((i for i,r in enumerate(self.readers) if secondary and r.path==secondary['path']),None)
            if target is not None:
                self.split(index,target)
                self.splitter.setOrientation(Qt.Orientation(session.get('orientation',1)))
                if session.get('pane_order',[None])[0]=='secondary': self.swap()
                self.splitter.setSizes(session.get('sizes',[1000,1000]))
                self.secondary.restore(secondary,defer=True)
                if session.get('active_secondary'): self.focus_reader(self.secondary)
            else: self.select(index)
            for r in self.readers:
                saved=next((s for s in wanted if s['path']==r.path),None)
                if saved: r.restore(saved,defer=True)
        if session.get('home') and self.readers: QTimer.singleShot(0,self.show_home)
        if not self.readers: self.show_home()
        if missing:
            self.error('Some session files are missing. Other PDFs were restored.\n\n'+'\n'.join(missing))
    def closeEvent(self,event):
        self.auto_scroll.pause()
        if self._closing:
            super().closeEvent(event)
            return
        # A utility dialog can be dismissed outside. Also protect programmatic or
        # OS-level parent closure while its worker still owns preview files.
        tools=self.findChildren(ToolDialog)
        busy=any(dialog._job is not None for dialog in tools)
        for dialog in tools:
            if not dialog._disposed: dialog.reject()
        if busy:
            event.ignore()
            return
        if self.file_jobs:
            self.error('PDF tools are still running. Cancel them or wait for completion before closing.')
            event.ignore()
            return
        self.finish_fullscreen_transition(force=True)
        self.save_session()
        if self._pending_backup_data is not None:
            from . import backup
            import sqlite3
            try:backup.replace(self.store,self._pending_backup_data)
            except (ValueError,sqlite3.Error) as error:
                self._pending_backup_data=None
                self.error('Restore failed. Your current reading data was kept.\n\n'+str(error))
                event.ignore()
                return
            self._pending_backup_data=None
            self._backup_restored=True
        self.inline_search.bind(None)
        self.toolbar.timer.stop()
        self.closed_tabs.clear()
        self._closing=True
        self.chrome_timer.stop()
        self.chrome_restore_timer.stop()
        self._fullscreen_snapshots=None
        self.sync_timer.stop()
        QApplication.instance().removeEventFilter(self)
        for job in list(self.reference_jobs):
            job.cancel_ui()
        for popup in list(self.popups): popup.close()
        # QWidget.close() hides a window; it need not destroy the QObject tree.
        # Release sources now, including when another window keeps Qt running.
        for dialog in self.findChildren(MarginsDialog):
            dialog.reject()
        for dialog in self.findChildren(NumberingDialog):
            dialog.reject()
        self.close_page_thumbnails()
        self.home.thumbnail.release()
        for reader in self.readers+([self.secondary] if self.secondary else []):
            reader.suspend()
            reader.setDocument(None)
        for document in self.docs:
            document.close()
            document.source_file.close()
        super().closeEvent(event)

def main():
    import argparse
    import tempfile
    parser=argparse.ArgumentParser(description='Mellow PDF Reader — A softer way to read')
    parser.add_argument('--portable',action='store_true',help='Keep small metadata beside the application')
    parser.add_argument('--smoke-test',action='store_true',help='Verify packaged rendering and exit (requires a PDF path)')
    parser.add_argument('files',nargs='*')
    args=parser.parse_args()
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Mellow.PDFReader')
    app=QApplication([sys.argv[0]])
    app.setWindowIcon(application_icon())
    app.setApplicationName('Mellow PDF Reader')
    app.setOrganizationName('Mellow')
    temp=tempfile.TemporaryDirectory(prefix='mellow-smoke-') if args.smoke_test else None
    store=Store(Path(temp.name)/'test.sqlite3') if temp else None
    window=Window(store=store,restore=not bool(args.files),portable=args.portable)
    window.show()
    for path in args.files: window.open_pdf(path)
    if args.smoke_test:
        def verify():
            from PySide6.QtCore import QEventLoop
            def settle():
                loop=QEventLoop()
                QTimer.singleShot(100,loop.quit)
                loop.exec()
            passed=bool(window.readers)
            if passed:
                reader=window.readers[0]
                passed=not reader.document().render(0,reader.viewport().size()).isNull()
                window.change_theme('Sepia')
                passed=passed and not window.grab().isNull() and not window.windowIcon().pixmap(32,32).isNull()
                reader.select_page_text(0)
                passed=passed and reader.copy_selection() and bool(QApplication.clipboard().text())
                preserved=QApplication.clipboard().text()
                passed=passed and reader.copy_selection(True)
                passed=passed and ''.join(QApplication.clipboard().text().split())==''.join(preserved.split())
                reader.clear_selection()
                window.apply_numbering(dict(pdf=0,book=10))
                passed=passed and reader.page_label(0)=='10'
                window.navigate_page_text('10')
                passed=passed and reader.pageNavigator().currentPage()==0
                pages=PagesPanel(reader,window)
                pages.show()
                for _ in range(10):
                    settle()
                    if pages.grid.cache:break
                passed=passed and bool(pages.grid.cache) and pages.grid.pages.index(0,0).data()=='10 · Current'
                pages.reject()
                passed=passed and pages.grid.released and not pages.grid.cache and pages.grid.renderer is None
                pages.deleteLater()
                numbers=NumberingDialog(reader,window)
                passed=passed and numbers.mapping()==dict(pdf=0,book=10)
                numbers.reject();numbers.deleteLater()
                window.apply_margins((4,4,4,4))
                for _ in range(30):
                    settle()
                    tasks=reader.rotated_pages.tasks()
                    if tasks and all(key in reader.rotated_pages.cache for key,_,_ in tasks):break
                passed=passed and reader.custom_rendering and bool(reader.rotated_pages.cache)
                margins=MarginsDialog(reader,window)
                margins.show()
                for _ in range(10):
                    settle()
                    if margins.preview.image is not None:break
                passed=passed and margins.preview.image is not None and margins.margins()==(4,4,4,4)
                margins.reject();margins.deleteLater()
                window.apply_margins((0,0,0,0));window.apply_numbering(None)
                passed=passed and not reader.custom_rendering and not reader.rotated_pages.cache
                reader.setZoomMode(QPdfView.ZoomMode.Custom);reader.setZoomFactor(1.2)
                reader.jump(0);settle()
                start=reader.verticalScrollBar().value()
                window.auto_scroll_action.trigger()
                for _ in range(4):settle()
                passed=passed and window.auto_scroll.running and reader.verticalScrollBar().value()>start
                window.auto_scroll.pause()
                passed=passed and not window.auto_scroll.timer.isActive() and not window.auto_scroll_action.isChecked()
                window.show_home()
                for _ in range(20):
                    settle()
                    if window.home.thumbnail.image is not None: break
                passed=passed and window.pages.currentWidget() is window.home and window.home.listing.count()>0
                passed=passed and window.home.continuation['path']==reader.path
                passed=passed and window.home.thumbnail.image is not None and not window.home.thumbnail.source.isOpen()
                window.resume_reading()
                window.search_dialog(initial=QApplication.clipboard().text().split()[0])
                for _ in range(30):
                    settle()
                    if reader.search.rowCount(QModelIndex()): break
                window.inline_search.step(1)
                passed=passed and window.inline_search.status.text().startswith('1 of ')
                reader.search.set_options(whole_words=True,match_case=True)
                for _ in range(30):
                    settle()
                    if reader.search.status()==reader.search.Status.Finished:break
                results=SearchPanel(reader,window)
                results.show();settle()
                passed=passed and reader.search.rowCount()>0 and results.whole_words.isChecked() and results.match_case.isChecked()
                passed=passed and 'Page ' in reader.search.index(0,0).data()
                results.visit(reader.search.index(0,0))
                passed=passed and reader.currentSearchResultIndex()==0
                results.reject()
                passed=passed and results.results.model() is None and not results._filter_installed
                results.deleteLater()
                passed=passed and QApplication.activeModalWidget() is None
                window.close_search()
                information=DocumentInfoDialog(reader,window)
                passed=passed and information.fields['Pages']==str(reader.document().pageCount())
                passed=passed and information.fields['Full path']==reader.path
                information.reject()
                information.deleteLater()
                preferences=SettingsDialog(window.store,window)
                passed=passed and preferences.values()['theme']=='Sepia'
                passed=passed and preferences.values()['auto_scroll_speed']==24
                passed=passed and not preferences.preview.image.isNull()
                default_sample=preferences.preview.image.copy()
                preferences.warmth.setValue(20);preferences.contrast.setValue(10)
                passed=passed and preferences.preview.image!=default_sample and reader.effect.warmth==0
                tuned=preferences.values()
                preferences.reject()
                preferences.deleteLater()
                window.apply_settings(tuned)
                passed=passed and reader.effect.warmth==20 and reader.effect.contrast==10 and not window.grab().isNull()
                saved_panel=LocationsPanel(window,'favorite')
                saved_panel.add_current()
                saved_panel.title_edit.setText('Smoke saved page')
                saved_panel.save_edit()
                passed=passed and saved_panel.listing.count()==1 and bool(saved_panel.selected()['label'])
                saved_panel.reject()
                saved_panel.deleteLater()
                outline_panel=LocationsPanel(window,'bookmark')
                passed=passed and outline_panel.tabs.count()==2
                outline_panel.reject()
                outline_panel.deleteLater()
                reader.zoom_by(1.1)
                passed=passed and reader.zoomMode()==QPdfView.ZoomMode.Custom
                # Check the native fullscreen transition in the frozen and
                # installed Windows app, including both independent panes.
                window.split(0,0)
                settle()
                window.set_split_proportion(70);settle()
                sizes=window.splitter.sizes()
                passed=passed and abs(sizes[0]/sum(sizes)-.7)<.01 and window.ratio_actions[70].isChecked()
                window.set_split_proportion(50);settle()
                window.focus_reader(window.secondary)
                passed=passed and window.secondary.pane_active and not reader.pane_active
                window.set_page_layout('single')
                settle()
                passed=passed and window.secondary.page_layout_mode=='single' and reader.page_layout_mode=='continuous'
                passed=passed and window.layout_actions['single'].isChecked()
                window.set_page_layout('two_continuous')
                window.set_cover(False)
                for _ in range(50):
                    settle()
                    tasks=window.secondary.rotated_pages.tasks()
                    if tasks and all(key in window.secondary.rotated_pages.cache for key,_,_ in tasks):break
                passed=passed and window.secondary.facing_pages and bool(window.secondary.rotated_pages.cache)
                passed=passed and not window.secondary.cover_separate and reader.page_layout_mode=='continuous'
                window.fullscreen()
                settle()
                passed=passed and window.isFullScreen() and not window.toolbar.isVisible()
                panes=[reader,window.secondary]
                states=[r.state() for r in panes]
                window.show_chrome()
                settle()
                passed=passed and window.toolbar.isVisible() and all(r.state()==s for r,s in zip(panes,states))
                window.toggle_chrome()
                settle()
                passed=passed and not window.toolbar.isVisible() and all(r.state()==s for r,s in zip(panes,states))
                window.fullscreen()
                settle()
                passed=passed and not window.isFullScreen() and window.toolbar.isVisible()
                window.exit_split()
                reader.rotate_by(90)
                for _ in range(30):
                    settle()
                    if reader.rotated_pages.cache: break
                passed=passed and reader.rotation==90 and bool(reader.rotated_pages.cache)
                reader.select_page_text(0)
                passed=passed and reader.copy_selection() and bool(QApplication.clipboard().text())
                reader.clear_selection()
                reader.rotate_by(-90)
                settle()
                # Closed tabs are metadata-only and live for this run only.
                path=reader.path
                window.close_tab(0)
                window.reopen_closed_tab()
                settle()
                reader=window.readers[0]
                passed=passed and reader.path==path and reader.rotation==0 and not window.closed_tabs
                window.store.clear_history()
                window.save_session()
                passed=passed and not window.store.history() and window.store.get('history_paused')
                window.store.set('history_paused',False)
            if not passed:
                window.close()
                app.exit(2)
                return
            # Exercise utility output generation inside the frozen executable,
            # including Qt image export and temporary-preview cleanup.
            image_path=Path(temp.name)/'image.png'
            image=QImage(80,60,QImage.Format.Format_RGB32)
            image.fill(Qt.GlobalColor.blue)
            image.save(str(image_path))
            cases=[('extract',[reader.path],1),('merge',[reader.path,reader.path],reader.document().pageCount()*2),
                   ('images',[str(image_path)],1)]
            def tool_check(index):
                if index==len(cases):
                    # Exercise metadata backup inside source, frozen and installed
                    # executables, using a folder outside the live metadata root.
                    from . import backup
                    try:
                        window.save_session()
                        with tempfile.TemporaryDirectory(prefix='mellow-backup-smoke-') as saved:
                            path=Path(saved)/'reading.mellow-backup.json'
                            backup.write(window.store,path)
                            data=backup.read(path)
                            restored=Store(Path(saved)/'fresh'/'mellow.sqlite3')
                            try:
                                backup.replace(restored,data)
                                if backup.snapshot(restored)!=data:raise ValueError('Metadata backup differs after restore')
                            finally:restored.db.close()
                        print('Metadata backup roundtrip verified.',flush=True)
                    except Exception as error:
                        print('Metadata backup smoke failed:',error,flush=True)
                        window.close()
                        app.exit(2)
                        return
                    window.close()
                    app.exit(0)
                    return
                mode,paths,count=cases[index]
                dialog=ToolDialog(mode,window,paths)
                import time
                started=time.monotonic()
                output=Path(temp.name)/(mode+'.pdf')
                saving=False
                arranged=False
                def fail():
                    dialog.reject()
                    if dialog._job:
                        QTimer.singleShot(25,fail)
                        return
                    window.close()
                    app.exit(2)
                def poll():
                    nonlocal saving,arranged
                    if time.monotonic()-started>20:
                        fail()
                        return
                    if dialog._job or dialog.timer.isActive():
                        QTimer.singleShot(25,poll)
                        return
                    if saving:
                        if dialog.saved_path and output.is_file() and dialog._disposed:
                            dialog.deleteLater()
                            tool_check(index+1)
                        else: fail()
                        return
                    ok=bool(dialog.current_output) and dialog.document.pageCount()==count
                    ok=ok and not dialog.document.render(0,QSize(320,420)).isNull()
                    if not ok:
                        fail()
                        return
                    if not arranged:
                        workspace=ArrangePagesDialog(dialog._base_output,dialog)
                        workspace.show()
                        for _ in range(10):
                            settle()
                            if workspace.grid.cache:break
                        ok=bool(workspace.grid.cache)
                        workspace.grid.select_rows([0])
                        workspace.rotate(90)
                        entries=workspace.entries()
                        workspace.accept()
                        ok=ok and not workspace.source.isOpen() and workspace.grid.released
                        workspace.deleteLater()
                        if not ok or not dialog.apply_arrangement(entries):
                            fail()
                            return
                        arranged=True
                        QTimer.singleShot(25,poll)
                        return
                    from pypdf import PdfReader
                    with PdfReader(dialog.current_output) as result:
                        valid_rotation=result.pages[0].rotation==90
                    if not valid_rotation:
                        fail()
                        return
                    saving=True
                    if not dialog.save_to(output):
                        fail()
                        return
                    QTimer.singleShot(25,poll)
                # Observe completion through GUI state. Connecting finished()
                # after starting a tiny job could miss an already emitted signal.
                QTimer.singleShot(25,poll)
            tool_check(0)
        QTimer.singleShot(1000,verify)
    code=app.exec()
    window.store.db.close()
    if temp: temp.cleanup()
    sys.exit(code)
