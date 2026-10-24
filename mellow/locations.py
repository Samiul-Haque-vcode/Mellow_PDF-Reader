"""Temporary, anchored saved-location panels; never load PDFs to populate lists."""
from pathlib import Path
from PySide6.QtCore import Qt,QPoint,QPointF,QEvent,QSortFilterProxyModel,QRect,QTimer
from PySide6.QtPdf import QPdfBookmarkModel
from PySide6.QtWidgets import (QApplication,QDialog,QVBoxLayout,QHBoxLayout,QLabel,
    QLineEdit,QToolButton,QPushButton,QListWidget,QListWidgetItem,QTabWidget,QTreeView,
    QWidget,QFrame,QMenu,QFileDialog,QStyledItemDelegate,QStyleOptionViewItem,QStyle,QToolTip)
from .home import HomeEntryDelegate,GROUP_ROLE,page_details
from .style import PALETTES
from .icons import icon
from .reading_options import page_label
from .saved_locations import destination_counts,destination_key,plain_tooltip
from .focus import owns,restore_focus


class OutlineFilter(QSortFilterProxyModel):
    def __init__(self,document,parent=None):
        super().__init__(parent)
        self.document=document
        self.needle=''
        self.setRecursiveFilteringEnabled(True)
    def filterAcceptsRow(self,row,parent):
        index=self.sourceModel().index(row,0,parent)
        title=str(index.data(QPdfBookmarkModel.Role.Title.value) or '')
        page=index.data(QPdfBookmarkModel.Role.Page.value)
        details=page_details(dict(page=page,label=page_label(self.document,page))) if isinstance(page,int) and page>=0 else ''
        return self.needle in (title+' '+details).casefold()
    def search(self,text):
        self.needle=text.strip().casefold()
        self.setFilterFixedString(text)


class OutlineDelegate(QStyledItemDelegate):
    def __init__(self,document,parent=None):
        super().__init__(parent)
        self.document=document
    def paint(self,painter,option,index):
        item=QStyleOptionViewItem(option)
        self.initStyleOption(item,index)
        page=index.data(QPdfBookmarkModel.Role.Page.value)
        detail=page_details(dict(page=page,label=page_label(self.document,page))) if isinstance(page,int) and page>=0 else ''
        width=min(item.rect.width()//2,item.fontMetrics.horizontalAdvance(detail)+18) if detail else 0
        title=item.text
        item.text=''
        option.widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem,item,painter,option.widget)
        painter.save()
        painter.setFont(item.font)
        painter.setPen(item.palette.text().color())
        painter.drawText(item.rect.adjusted(7,0,-width-7,0),Qt.AlignmentFlag.AlignVCenter,
                         item.fontMetrics.elidedText(title,Qt.TextElideMode.ElideRight,max(0,item.rect.width()-width-14)))
        painter.setPen(item.palette.text().color())
        painter.setOpacity(.72)
        painter.drawText(item.rect.adjusted(item.rect.width()-width,0,-7,0),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignRight,detail)
        painter.restore()
    def sizeHint(self,option,index):
        size=super().sizeHint(option,index)
        size.setHeight(max(34,size.height()))
        return size


class LocationEntryDelegate(HomeEntryDelegate):
    """Paint actions only for visible rows, without a widget per saved page."""
    def action_rects(self,rect,index):
        top=rect.top()+(26 if index.data(GROUP_ROLE) else 0)
        return (QRect(rect.right()-29,top+5,26,26),
                QRect(rect.right()-29,top+35,26,26))
    def paint(self,painter,option,index):
        content=QStyleOptionViewItem(option)
        content.rect=option.rect.adjusted(0,0,-34,0)
        super().paint(painter,content,index)
        edit,remove=self.action_rects(option.rect,index)
        gutter=QStyleOptionViewItem(option)
        self.initStyleOption(gutter,index)
        gutter.text=''
        gutter.rect=QRect(edit.left()-3,edit.top()-5,34,68)
        option.widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem,gutter,painter,option.widget)
        color=PALETTES[self.home.theme_name]['text']
        for name,rect in (('edit',edit),('close',remove)):
            icon(name,color).paint(painter,rect.adjusted(5,5,-5,-5))
    def editorEvent(self,event,model,option,index):
        if event.type() in (QEvent.Type.MouseButtonPress,QEvent.Type.MouseButtonRelease,QEvent.Type.MouseButtonDblClick):
            if event.button()==Qt.MouseButton.LeftButton:
                for rect,callback in zip(self.action_rects(option.rect,index),
                                         (self.home.rename_selected,self.home.remove_selected)):
                    if rect.contains(event.position().toPoint()):
                        if event.type()==QEvent.Type.MouseButtonRelease:
                            self.home.listing.setCurrentIndex(index)
                            callback()
                        return True
        return super().editorEvent(event,model,option,index)
    def helpEvent(self,event,view,option,index):
        for rect,text in zip(self.action_rects(option.rect,index),('Rename saved page (F2)','Remove saved page (Delete)')):
            if rect.contains(event.pos()):
                QToolTip.showText(event.globalPos(),text,view)
                return True
        return super().helpEvent(event,view,option,index)


class LocationsPanel(QDialog):
    def __init__(self,window,kind):
        # A transient tool window avoids native Popup dismissal while opening a
        # Locate File dialog. Outside clicks and Escape still dismiss the panel.
        super().__init__(window,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint)
        self.setObjectName('locationsPanel')
        self.window=window
        self.store=window.store
        self.kind=kind
        self.reader=window.active if not window._on_home else None
        self.theme_name=window.theme_name
        self.title_elide=Qt.TextElideMode.ElideRight
        self._editing=None
        self._filter_installed=False
        self._closed=False
        self._locating=False
        self.dismiss_timer=QTimer(self)
        self.dismiss_timer.setSingleShot(True)
        self.dismiss_timer.timeout.connect(self.dismiss_if_inactive)
        self.setWindowTitle('PDF Bookmarks' if kind=='bookmark' else 'Favorites')
        self.resize(480,510)
        self.setMinimumSize(340,340)
        root=QVBoxLayout(self)
        root.setContentsMargins(16,14,16,14)
        root.setSpacing(10)
        heading=QHBoxLayout()
        title=QLabel(self.windowTitle())
        title.setProperty('role','section')
        heading.addWidget(title,1)
        close=QToolButton()
        close.setIcon(icon('close',PALETTES[self.theme_name]['text']))
        close.setAccessibleName('Close '+self.windowTitle())
        close.clicked.connect(self.reject)
        heading.addWidget(close)
        root.addLayout(heading)
        subtitle=QLabel(Path(self.reader.path).name if kind=='bookmark' and self.reader else 'Saved pages across your PDFs')
        subtitle.setTextFormat(Qt.TextFormat.PlainText)
        subtitle.setProperty('role','muted')
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)
        self.search=QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText('Find a section or bookmark…' if kind=='bookmark' else 'Find a title or PDF…')
        self.search.setAccessibleName('Find saved location')
        self.search.installEventFilter(self)
        search_row=QHBoxLayout()
        search_row.addWidget(self.search,1)
        self.add_button=QToolButton()
        self.add_button.setIcon(icon('plus',PALETTES[self.theme_name]['text']))
        self.add_button.setToolTip('Bookmark current page' if kind=='bookmark' else 'Save current page to Favorites')
        self.add_button.setAccessibleName(self.add_button.toolTip())
        self.add_button.setEnabled(self.reader is not None)
        self.add_button.clicked.connect(self.add_current)
        search_row.addWidget(self.add_button)
        root.addLayout(search_row)
        self.listing=QListWidget()
        self.listing.setObjectName('locationEntries')
        self.listing.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.listing.setItemDelegate(LocationEntryDelegate(self,self.listing))
        self.listing.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.listing.customContextMenuRequested.connect(self.context_menu)
        self.listing.itemActivated.connect(lambda *_:self.open_selected())
        self.listing.installEventFilter(self)
        self.tabs=None
        self.outline=None
        if kind=='bookmark':
            self.tabs=QTabWidget()
            contents=QWidget()
            box=QVBoxLayout(contents)
            box.setContentsMargins(0,8,0,0)
            self.outline=QTreeView()
            self.outline.setHeaderHidden(True)
            self.outline.setUniformRowHeights(True)
            self.outline_model=QPdfBookmarkModel(self)
            self.outline_model.setDocument(self.reader.document())
            self.outline_filter=OutlineFilter(self.reader.document(),self)
            self.outline_filter.setSourceModel(self.outline_model)
            self.outline.setModel(self.outline_filter)
            self.outline.setItemDelegate(OutlineDelegate(self.reader.document(),self.outline))
            self.outline.clicked.connect(self.visit_outline)
            self.outline.installEventFilter(self)
            box.addWidget(self.outline,1)
            self.outline_empty=QLabel()
            self.outline_empty.setProperty('role','muted')
            self.outline_empty.setWordWrap(True)
            box.addWidget(self.outline_empty)
            self.tabs.addTab(contents,'Contents')
            personal=QWidget()
            box=QVBoxLayout(personal)
            box.setContentsMargins(0,8,0,0)
            box.addWidget(self.listing)
            self.tabs.addTab(personal,'My bookmarks')
            self.tabs.currentChanged.connect(self.tab_changed)
            root.addWidget(self.tabs,1)
        else: root.addWidget(self.listing,1)
        self.empty=QLabel()
        self.empty.setWordWrap(True)
        self.empty.setProperty('role','muted')
        root.addWidget(self.empty)
        self.editor=QFrame()
        form=QVBoxLayout(self.editor)
        form.setContentsMargins(0,0,0,0)
        form.setSpacing(6)
        self.edit_title=QLabel('Title')
        form.addWidget(self.edit_title)
        self.duplicate_hint=QLabel()
        self.duplicate_hint.setTextFormat(Qt.TextFormat.PlainText)
        self.duplicate_hint.setWordWrap(True)
        self.duplicate_hint.setProperty('role','muted')
        self.duplicate_hint.hide()
        form.addWidget(self.duplicate_hint)
        self.title_edit=QLineEdit()
        self.title_edit.setAccessibleName('Saved location title')
        self.title_edit.installEventFilter(self)
        form.addWidget(self.title_edit)
        buttons=QHBoxLayout()
        save=QPushButton('Save')
        save.setAutoDefault(False)
        save.setObjectName('primary')
        save.clicked.connect(self.save_edit)
        cancel=QPushButton('Cancel')
        cancel.setAutoDefault(False)
        cancel.clicked.connect(self.cancel_edit)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        form.addLayout(buttons)
        root.addWidget(self.editor)
        self.editor.hide()
        self.search.textChanged.connect(self.filtering)
        self.refresh()
    def refresh(self,selected_id=None):
        if selected_id is None:
            saved=self.selected()
            selected_id=saved['id'] if saved else None
        self.window.refresh_saved_labels()
        rows=self.store.locations(self.kind,self.reader.path if self.kind=='bookmark' else None)
        counts=destination_counts(rows)
        grouped={}
        for row in rows: grouped.setdefault(row['path'],[]).append(row)
        self.listing.clear()
        for row in (row for group in grouped.values() for row in group):
            filename=Path(row['path']).name
            count=counts.get(destination_key(row),0)
            detail=page_details(row)+(f' · {count} saved here' if count>1 else '')
            title=row['title'] or filename
            item=QListWidgetItem(f'{title}\n{detail}')
            item.setToolTip(plain_tooltip(title,row['path'],detail,'F2: rename · Delete: remove'))
            item.setData(Qt.ItemDataRole.AccessibleTextRole,title+' · '+filename+' · '+detail)
            item.setData(Qt.ItemDataRole.AccessibleDescriptionRole,row['path'])
            item.setData(Qt.ItemDataRole.UserRole,row)
            self.listing.addItem(item)
            if row['id']==selected_id: self.listing.setCurrentItem(item)
        self.filtering(self.search.text())
    def filtering(self,text):
        needle=text.strip().casefold()
        groups=set()
        first=None
        for index in range(self.listing.count()):
            item=self.listing.item(index)
            row=item.data(Qt.ItemDataRole.UserRole)
            item.setHidden(needle not in (item.text()+' '+Path(row['path']).name).casefold())
            group=Path(row['path']).name if not item.isHidden() and row['path'] not in groups and self.kind=='favorite' else ''
            item.setData(GROUP_ROLE,group)
            if not item.isHidden():
                groups.add(row['path'])
                if first is None: first=item
        if not self.listing.currentItem() or self.listing.currentItem().isHidden(): self.listing.setCurrentItem(first)
        self.empty.setText('No saved pages match your search.' if needle else ('No personal bookmarks yet. Save a page to return to it later.' if self.kind=='bookmark' else 'No Favorites yet. Save useful pages while you read.'))
        self.empty.setVisible(first is None and self.personal_tab())
        if self.outline:
            self.outline_filter.search(text)
            if needle: self.outline.expandAll()
            has_outline=self.outline_model.rowCount()>0
            self.outline_empty.setText('No sections match your search.' if has_outline else 'This PDF has no contents outline. You can add your own pages in My bookmarks.')
            self.outline_empty.setVisible(self.outline_filter.rowCount()==0)
            self.outline.setVisible(self.outline_filter.rowCount()>0)
        self.listing.doItemsLayout()
    def personal_tab(self):
        return self.tabs is None or self.tabs.currentIndex()==1
    def tab_changed(self,*_):
        self.cancel_edit()
        self.filtering(self.search.text())
    def selected(self):
        item=self.listing.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item and not item.isHidden() else None
    def add_current(self):
        if not self.reader: return
        if self.tabs: self.tabs.setCurrentIndex(1)
        state=self.reader.state()
        page=state.get('anchor_page',state['page'])
        self._editing=dict(path=self.reader.path,page=page,x=state['x'],y=state['y'],label=self.reader.page_label(page))
        self.edit_title.setText('Save '+page_details(self._editing))
        self.title_edit.setText('Page '+self._editing['label'])
        self.show_duplicate_notice()
        self.editor.show()
        self.title_edit.setFocus()
        self.title_edit.selectAll()
    def rename_selected(self):
        row=self.selected()
        if not row: return
        self._editing=dict(row)
        self.edit_title.setText('Rename saved page')
        self.title_edit.setText(row['title'])
        self.show_duplicate_notice()
        self.editor.show()
        self.title_edit.setFocus()
        self.title_edit.selectAll()
    def save_edit(self):
        if self._editing is None: return
        row=self._editing
        title=self.title_edit.text().strip() or 'Page '+(row.get('label') or str(row['page']+1))
        ident=row.get('id')
        if ident is not None:self.store.rename(ident,title)
        else:ident=self.store.add(self.kind,row['path'],row['page'],title,row['x'],row['y'],label=row['label'])
        self.cancel_edit()
        self.search.clear()
        self.refresh(ident)
    def show_duplicate_notice(self):
        row=self._editing
        matches=self.store.matching_locations(self.kind,row['path'],row['page'],row.get('x',0),row.get('y',0),row.get('id'))
        self.duplicate_hint.setVisible(bool(matches))
        if matches:
            title=' '.join(matches[0]['title'].split()) or 'Page '+str(row['page']+1)
            self.duplicate_hint.setText('Already saved: '+(title[:48]+'…' if len(title)>48 else title)+'. You can save another entry.')
            self.duplicate_hint.setToolTip(plain_tooltip(*(match['title'] for match in matches)))
    def cancel_edit(self):
        self._editing=None
        self.editor.hide()
        self.duplicate_hint.hide()
    def remove_selected(self):
        row=self.selected()
        if row:
            self.store.remove(row['id'])
            self.cancel_edit()
            self.refresh()
    def locate_selected(self):
        row=self.selected()
        if not row: return
        self._locating=True
        try:path,_=QFileDialog.getOpenFileName(self,'Locate PDF',str(Path(row['path']).parent),'PDF (*.pdf)')
        finally:self._locating=False
        if path:
            if self.window.relocate_pdf(row['path'],path):self.refresh(row['id'])
    def actions_menu(self):
        menu=QMenu(self)
        row=self.selected()
        if not row: return menu
        menu.addAction('Open saved page',self.open_selected)
        menu.addSeparator()
        menu.addAction('Rename…',self.rename_selected)
        menu.addAction('Remove',self.remove_selected)
        if not Path(row['path']).is_file():
            menu.addSeparator()
            menu.addAction('Locate File…',self.locate_selected)
        return menu
    def context_menu(self,point):
        item=self.listing.itemAt(point)
        if not item: return
        self.listing.setCurrentItem(item)
        menu=self.actions_menu()
        menu.exec(self.listing.viewport().mapToGlobal(point))
        menu.deleteLater()
    def open_selected(self):
        if not self.personal_tab(): return
        row=self.selected()
        if row and self.window.open_saved(row): self.accept()
    def visit_outline(self,index):
        if not index.isValid(): return
        page=index.data(QPdfBookmarkModel.Role.Page.value)
        if not isinstance(page,int) or page<0: return
        location=index.data(QPdfBookmarkModel.Role.Location.value)
        self.reader.jump(page,location if isinstance(location,QPointF) else QPointF())
        self.accept()
    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.KeyPress and obj is getattr(self,'listing',None):
            if event.key()==Qt.Key.Key_F2:
                self.rename_selected();return True
            if event.key()==Qt.Key.Key_Delete:
                self.remove_selected();return True
        if event.type()==QEvent.Type.ShortcutOverride and event.key()==Qt.Key.Key_Escape and isinstance(obj,QWidget) and (obj is self or self.isAncestorOf(obj)):
            event.accept()
            return True
        if event.type()==QEvent.Type.KeyPress and event.key()==Qt.Key.Key_Escape and owns(self,obj):
            if self.editor.isVisible():
                self.cancel_edit()
                self.search.setFocus()
            else:
                self.reject()
                restore_focus(self.window.home.manage if self.window._on_home else self.window.active)
            return True
        if event.type()==QEvent.Type.KeyPress and obj in (self.listing,self.outline) and (event.key()==Qt.Key.Key_Menu or
                event.key()==Qt.Key.Key_F10 and event.modifiers()==Qt.KeyboardModifier.ShiftModifier):
            if obj is self.listing and self.selected():
                menu=self.actions_menu()
                menu.exec(self.listing.viewport().mapToGlobal(self.listing.visualItemRect(self.listing.currentItem()).center()))
                menu.deleteLater()
            return True
        if event.type()==QEvent.Type.KeyPress and obj is self.search and event.key()==Qt.Key.Key_Down:
            target=self.listing if self.personal_tab() else self.outline
            if target is not None:
                target.setFocus()
                if not target.currentIndex().isValid(): target.setCurrentIndex(target.model().index(0,0))
            return True
        if event.type()==QEvent.Type.KeyPress and obj is self.title_edit and event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):
            self.save_edit()
            return True
        if event.type()==QEvent.Type.KeyPress and obj in (self.listing,self.outline) and event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):
            if obj is self.outline: self.visit_outline(self.outline.currentIndex())
            else: self.open_selected()
            return True
        if self._filter_installed and not self._locating and event.type()==QEvent.Type.MouseButtonPress:
            modal=QApplication.activeModalWidget()
            popup=QApplication.activePopupWidget()
            if modal is None and popup is None and not self.frameGeometry().contains(event.globalPosition().toPoint()):
                self.reject()
        if obj is self and event.type()==QEvent.Type.WindowDeactivate and self._filter_installed:
            # Defer until child menus/file dialogs have become active.
            self.dismiss_timer.start(0)
        return super().eventFilter(obj,event)
    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape and self.editor.isVisible():
            self.cancel_edit()
            self.search.setFocus()
            return
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and not self.editor.isVisible():
            if self.outline and not self.personal_tab():
                index=self.outline.currentIndex()
                self.visit_outline(index if index.isValid() else self.outline_filter.index(0,0))
            else: self.open_selected()
            return
        super().keyPressEvent(event)
    def dismiss_if_inactive(self):
        if not self.isVisible() or self._locating:return
        modal=QApplication.activeModalWidget()
        popup=QApplication.activePopupWidget()
        if modal is not None or popup is not None:return
        active=QApplication.activeWindow()
        if active is not self and (active is None or not self.isAncestorOf(active)):
            self.reject()
    def showEvent(self,event):
        super().showEvent(event)
        self._filter_installed=True
        QApplication.instance().installEventFilter(self)
        self.search.setFocus()
    def done(self,result):
        if self._closed:return
        self._closed=True
        self.dismiss_timer.stop()
        self._filter_installed=False
        QApplication.instance().removeEventFilter(self)
        super().done(result)
    def position_near(self,anchor):
        screen=anchor.screen() if anchor else self.window.screen()
        available=screen.availableGeometry()
        self.resize(min(480,available.width()-16),min(510,available.height()-16))
        point=anchor.mapToGlobal(QPoint(0,anchor.height()+4)) if anchor else self.window.mapToGlobal(QPoint(24,100))
        x=max(available.left()+8,min(point.x(),available.right()-self.width()-7))
        y=max(available.top()+8,min(point.y(),available.bottom()-self.height()-7))
        self.move(x,y)
