"""Organized Home: recent PDFs, favorite locations and basic offline tools."""
from pathlib import Path
from datetime import datetime, timezone
from PySide6.QtCore import Qt,Signal,QSize,QRect
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,
                              QToolButton,QLineEdit,QListWidget,QListWidgetItem,QSplitter,QMenu,QComboBox,QScrollArea,QFrame,
                              QStyledItemDelegate,QStyleOptionViewItem,QStyle,QSizePolicy)
from .icons import icon
from .style import PALETTES
from .thumbnail import PageThumbnail
from .saved_locations import destination_counts,destination_key,plain_tooltip


GROUP_ROLE=int(Qt.ItemDataRole.UserRole)+1


def page_details(row):
    state=row.get('state') or {}
    number=row['page']+1
    printed=row.get('label') or state.get('label')
    if not printed: return f'PDF page {number}'
    if printed=='#'+str(number):return f'PDF page {number}'
    return f'Page {printed}' if printed==str(number) else f'Page {printed} · PDF page {number}'


def last_read(value):
    if not value: return ''
    try:
        date=datetime.fromisoformat(value).replace(tzinfo=timezone.utc).astimezone()
        now=datetime.now().astimezone()
        return 'Today, '+date.strftime('%H:%M') if date.date()==now.date() else date.strftime('%d %b %Y, %H:%M')
    except (TypeError,ValueError):
        return ''


class HomeEntryDelegate(QStyledItemDelegate):
    """Two readable, elided lines; grouping adds no extra navigable list rows."""
    def __init__(self,home,parent=None):
        super().__init__(parent)
        self.home=home
    def sizeHint(self,option,index):
        return QSize(0,68+(26 if index.data(GROUP_ROLE) else 0))
    def paint(self,painter,option,index):
        c=PALETTES[self.home.theme_name]
        group=index.data(GROUP_ROLE)
        rect=QRect(option.rect)
        painter.save()
        if group:
            painter.setPen(QColor(c['muted']))
            font=option.font
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(rect.adjusted(10,0,-10,0),Qt.AlignmentFlag.AlignTop,
                             painter.fontMetrics().elidedText(group,Qt.TextElideMode.ElideMiddle,max(0,rect.width()-20)))
            rect.adjust(0,26,0,0)
        background=QStyleOptionViewItem(option)
        self.initStyleOption(background,index)
        background.text=''
        background.rect=rect
        option.widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem,background,painter,option.widget)
        title,_,details=str(index.data() or '').partition('\n')
        font=option.font
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(c['text']))
        painter.drawText(rect.adjusted(10,9,-10,0),Qt.AlignmentFlag.AlignTop,
                         painter.fontMetrics().elidedText(title,getattr(self.home,'title_elide',Qt.TextElideMode.ElideMiddle),max(0,rect.width()-20)))
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor(c['muted']))
        painter.drawText(rect.adjusted(10,34,-10,0),Qt.AlignmentFlag.AlignTop,
                         painter.fontMetrics().elidedText(details,Qt.TextElideMode.ElideRight,max(0,rect.width()-20)))
        painter.setPen(QColor(c['line']))
        painter.drawLine(rect.bottomLeft(),rect.bottomRight())
        painter.restore()


def label(text,role):
    result=QLabel(text)
    result.setProperty('role',role)
    return result


class Home(QWidget):
    openRequested=Signal()
    resumeRequested=Signal()
    settingsRequested=Signal()
    recentRequested=Signal(object)
    favoriteRequested=Signal(object)
    manageFavoritesRequested=Signal()
    toolRequested=Signal(str)
    recentRemoved=Signal(str)
    historyRequested=Signal()
    folderRequested=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setObjectName('home')
        self.theme_name='Sepia'
        root=QVBoxLayout(self)
        root.setContentsMargins(0,0,0,0)
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content=QWidget()
        content.setObjectName('homeContent')
        scroll.setWidget(content)
        root.addWidget(scroll)
        outer=QHBoxLayout(content)
        outer.setContentsMargins(26,20,26,20)
        outer.addStretch(1)
        self.body=QWidget()
        self.body.setMaximumWidth(1080)
        outer.addWidget(self.body,10)
        outer.addStretch(1)
        box=QVBoxLayout(self.body)
        box.setContentsMargins(0,0,0,0)
        box.setSpacing(14)
        hero=QHBoxLayout()
        title=QVBoxLayout()
        title.setSpacing(2)
        title.addWidget(label('Mellow','title'))
        hero.addLayout(title)
        hero.addStretch()
        self.opened=QPushButton('Open PDF')
        self.opened.setObjectName('primary')
        self.opened.clicked.connect(self.openRequested)
        hero.addWidget(self.opened)
        self.settings=QToolButton()
        self.settings.setToolTip('Settings')
        self.settings.setAccessibleName('Settings')
        self.settings.clicked.connect(self.settingsRequested)
        hero.addWidget(self.settings)
        box.addLayout(hero)
        self.continue_strip=QFrame()
        self.continue_strip.setObjectName('continueStrip')
        actions=QHBoxLayout(self.continue_strip)
        actions.setContentsMargins(0,10,0,10)
        actions.setSpacing(16)
        self.thumbnail=PageThumbnail()
        actions.addWidget(self.thumbnail)
        description=QVBoxLayout()
        description.setSpacing(4)
        description.addStretch()
        self.continue_name=QLabel()
        self.continue_name.setProperty('role','section')
        self.continue_name.setTextFormat(Qt.TextFormat.PlainText)
        self.continue_name.setWordWrap(True)
        self.continue_name.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.continue_details=label('','muted')
        description.addWidget(self.continue_name)
        description.addWidget(self.continue_details)
        description.addStretch()
        actions.addLayout(description,1)
        self.resume=QPushButton('Continue')
        self.resume.setObjectName('primary')
        self.resume.clicked.connect(self.continue_reading)
        actions.addWidget(self.resume)
        box.addWidget(self.continue_strip)
        self.continuation=None
        self.can_resume=False
        self.filter=QLineEdit()
        self.filter.setPlaceholderText('Search')
        self.filter.setAccessibleName('Search recent PDFs and favorites')
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self.apply_filter)
        searchrow=QHBoxLayout()
        searchrow.addWidget(self.filter,1)
        self.sort=QComboBox()
        self.sort.addItems(['Recent','Name'])
        self.sort.setAccessibleName('Sort recent PDFs')
        self.sort.currentIndexChanged.connect(self.sort_recent)
        searchrow.addWidget(self.sort)
        box.addLayout(searchrow)
        self.columns=QSplitter(Qt.Orientation.Horizontal)
        self.columns.setObjectName('homeColumns')
        self.columns.setHandleWidth(12)
        self.columns.setChildrenCollapsible(False)
        self.columns.setMinimumHeight(260)
        recent=QWidget()
        recent_box=QVBoxLayout(recent)
        recent_box.setContentsMargins(0,0,6,0)
        heading=QHBoxLayout()
        heading.addWidget(label('Recent','section'))
        heading.addStretch()
        self.recent_count=label('0','muted')
        heading.addWidget(self.recent_count)
        history=QToolButton()
        history.setText('History')
        history.setToolTip('Pause or clear reading history')
        history.clicked.connect(self.historyRequested)
        heading.addWidget(history)
        recent_header=QWidget()
        recent_header.setFixedHeight(30)
        heading.setContentsMargins(0,0,0,0)
        recent_header.setLayout(heading)
        recent_box.addWidget(recent_header)
        self.listing=QListWidget()
        self.listing.setObjectName('homeEntries')
        self.listing.setAccessibleName('Recent PDFs')
        self.listing.setItemDelegate(HomeEntryDelegate(self,self.listing))
        self.listing.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.listing.setMinimumSize(100,80)
        self.listing.itemActivated.connect(self.open_recent)
        self.listing.itemClicked.connect(self.open_recent)
        self.listing.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.listing.customContextMenuRequested.connect(self.recent_menu)
        recent_box.addWidget(self.listing,1)
        self.empty=label('No recent PDFs.','muted')
        self.empty.setWordWrap(True)
        recent_box.addWidget(self.empty)
        favorites=QWidget()
        favorites_box=QVBoxLayout(favorites)
        favorites_box.setContentsMargins(6,0,0,0)
        heading=QHBoxLayout()
        heading.addWidget(label('Favorites','section'))
        heading.addStretch()
        self.favorite_count=label('0','muted')
        heading.addWidget(self.favorite_count)
        self.manage=QToolButton()
        self.manage.setText('Manage')
        self.manage.clicked.connect(self.manageFavoritesRequested)
        heading.addWidget(self.manage)
        self.favorite_actions=heading
        favorite_header=QWidget()
        favorite_header.setFixedHeight(30)
        heading.setContentsMargins(0,0,0,0)
        favorite_header.setLayout(heading)
        favorites_box.addWidget(favorite_header)
        self.favorites=QListWidget()
        self.favorites.setObjectName('homeEntries')
        self.favorites.setAccessibleName('Favorite pages grouped by PDF')
        self.favorites.setItemDelegate(HomeEntryDelegate(self,self.favorites))
        self.favorites.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.favorites.setMinimumSize(100,80)
        self.favorites.itemActivated.connect(self.open_favorite)
        self.favorites.itemClicked.connect(self.open_favorite)
        favorites_box.addWidget(self.favorites,1)
        self.no_favorites=label('No favorites yet.','muted')
        self.no_favorites.setWordWrap(True)
        favorites_box.addWidget(self.no_favorites)
        self.columns.addWidget(recent)
        self.columns.addWidget(favorites)
        self.columns.setStretchFactor(0,1)
        self.columns.setStretchFactor(1,1)
        box.addWidget(self.columns,1)
        tools_heading=QHBoxLayout()
        tools_heading.addWidget(label('PDF tools','section'))
        tools_heading.addStretch()
        self.backup=QToolButton()
        self.backup.setToolTip('Favorites backup')
        self.backup.setAccessibleName('Favorites backup')
        self.backup.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.favorite_actions.addWidget(self.backup)
        box.insertLayout(2,tools_heading)
        tools=QGridLayout()
        self.tool_grid=tools
        tools.setSpacing(8)
        self.tools={}
        for index,(key,text,tip) in enumerate([
            ('images','Images to PDF','Arrange images, choose page size and preview the PDF'),
            ('merge','Merge PDFs','Arrange PDFs and preview the combined document'),
            ('extract','Split PDF','Choose pages and preview the new PDF'),
        ]):
            button=QPushButton(text)
            button.setObjectName('homeTool')
            button.setFixedHeight(52)
            button.setIconSize(QSize(22,22))
            button.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
            button.setToolTip(tip)
            button.clicked.connect(lambda checked=False,k=key: self.toolRequested.emit(k))
            tools.addWidget(button,0,index)
            self.tools[key]=button
        menu=QMenu(self.backup)
        menu.addAction('Export Favorites…',lambda: self.toolRequested.emit('export'))
        menu.addAction('Import Favorites…',lambda: self.toolRequested.emit('import'))
        self.backup.setMenu(menu)
        box.insertLayout(3,tools)
        self.rows=[]
        self.set_theme('Sepia')
    def resizeEvent(self,event):
        orientation=Qt.Orientation.Vertical if event.size().width()<700 else Qt.Orientation.Horizontal
        if self.columns.orientation()!=orientation:
            self.columns.setOrientation(orientation)
            self.columns.setMinimumHeight(320 if orientation==Qt.Orientation.Vertical else 260)
        for index,button in enumerate(self.tools.values()):
            self.tool_grid.removeWidget(button)
            self.tool_grid.addWidget(button,index if event.size().width()<620 else 0,
                                     0 if event.size().width()<620 else index)
        for index in range(3):self.tool_grid.setColumnStretch(index,0 if event.size().width()<620 else 1)
        super().resizeEvent(event)
    def set_theme(self,theme):
        self.theme_name=theme
        c=PALETTES[theme]
        self.settings.setIcon(icon('settings',c['text']))
        self.opened.setIcon(icon('open',c['onaccent']))
        self.resume.setIcon(icon('book',c['onaccent']))
        self.thumbnail.set_theme(theme)
        self.listing.viewport().update()
        self.favorites.viewport().update()
        for name,button in self.tools.items(): button.setIcon(icon(name,c['text']))
        self.backup.setIcon(icon('backup',c['text']))
    def refresh(self,rows,can_resume,favorites=None,continuation=None):
        self.rows=list(rows)
        favorites=favorites or []
        self.can_resume=can_resume
        self.continuation=continuation or (self.rows[0] if self.rows else None)
        self.continue_strip.setVisible(self.continuation is not None)
        if self.continuation:
            saved=self.continuation
            self.continue_name.setText(Path(saved['path']).name)
            self.continue_name.setToolTip(saved['path'])
            self.continue_details.setText(page_details(saved))
            self.thumbnail.set_source(saved['path'],saved['page'])
        else:
            self.thumbnail.set_source(None,0)
        self.listing.clear()
        for row in self.rows:
            visited=last_read(row.get('visited'))
            details=page_details(row)+(f' · {visited}' if visited else '')
            item=QListWidgetItem(f"{Path(row['path']).name}\n{details}")
            item.setToolTip(row['path'])
            item.setData(Qt.ItemDataRole.UserRole,row)
            self.listing.addItem(item)
        self.favorites.clear()
        duplicate_counts=destination_counts(favorites)
        # Keep all destinations for a PDF together, preserving group recency.
        grouped={}
        for row in favorites: grouped.setdefault(row['path'],[]).append(row)
        for row in (row for group in grouped.values() for row in group):
            filename=Path(row['path']).name
            title=row.get('title') or filename
            count=duplicate_counts.get(destination_key(row),0)
            detail=page_details(row)+(f' · {count} saved here' if count>1 else '')
            item=QListWidgetItem(f"{title}\n{detail}")
            item.setToolTip(plain_tooltip(title,row['path'],detail))
            item.setData(Qt.ItemDataRole.AccessibleTextRole,title+' · '+filename+' · '+detail)
            item.setData(Qt.ItemDataRole.AccessibleDescriptionRole,row['path'])
            item.setData(Qt.ItemDataRole.UserRole,row)
            self.favorites.addItem(item)
        self.sort_recent()
        self.recent_count.setText(str(len(rows)))
        self.favorite_count.setText(str(len(favorites)))
        self.empty.setVisible(not rows)
        self.no_favorites.setVisible(not favorites)
        self.apply_filter(self.filter.text())
    def apply_filter(self,text):
        needle=text.strip().casefold()
        for listing,count,empty,noun in ((self.listing,self.recent_count,self.empty,'recent PDFs'),(self.favorites,self.favorite_count,self.no_favorites,'Favorites')):
            groups=set()
            for index in range(listing.count()):
                item=listing.item(index)
                filename=Path(item.data(Qt.ItemDataRole.UserRole)['path']).name
                item.setHidden(needle not in (item.text()+' '+filename).casefold())
                if listing is self.favorites:
                    path=item.data(Qt.ItemDataRole.UserRole)['path']
                    group=Path(path).name if not item.isHidden() and path not in groups else ''
                    item.setData(GROUP_ROLE,group)
                    if not item.isHidden(): groups.add(path)
            visible=sum(not listing.item(i).isHidden() for i in range(listing.count()))
            count.setText(f'{visible} / {listing.count()}' if needle else str(listing.count()))
            empty.setVisible(visible==0)
            if needle: empty.setText(f'No {noun} match “{text.strip()}”.')
            elif listing is self.listing: empty.setText('Open a PDF to begin.' if not self.can_resume else 'Recent history is empty.')
            else: empty.setText('Save pages with the star while reading.')
    def sort_recent(self,*_):
        # Rearrange existing items so their path/state metadata stays intact.
        items=[self.listing.takeItem(0) for _ in range(self.listing.count())]
        if self.sort.currentIndex()==1:
            items.sort(key=lambda item: item.text().casefold())
        else:
            order={row['path']:i for i,row in enumerate(self.rows)}
            items.sort(key=lambda item: order.get(item.data(Qt.ItemDataRole.UserRole)['path'],0))
        for item in items: self.listing.addItem(item)
        self.apply_filter(self.filter.text())
    def recent_menu(self,point):
        item=self.listing.itemAt(point)
        if not item: return
        row=item.data(Qt.ItemDataRole.UserRole)
        menu=QMenu(self)
        menu.addAction('Open PDF' if Path(row['path']).is_file() else 'Locate File…',lambda: self.open_recent(item))
        menu.addAction('Show in folder',lambda:self.folderRequested.emit(row['path']))
        menu.addAction('Remove from recent list',lambda: self.recentRemoved.emit(row['path']))
        menu.exec(self.listing.viewport().mapToGlobal(point))
    def continue_reading(self):
        if self.can_resume: self.resumeRequested.emit()
        elif self.continuation: self.recentRequested.emit(self.continuation)
    def open_recent(self,item):
        row=item.data(Qt.ItemDataRole.UserRole)
        if row: self.recentRequested.emit(row)
    def open_favorite(self,item):
        row=item.data(Qt.ItemDataRole.UserRole)
        if row: self.favoriteRequested.emit(row)


def home_icon(color):
    return icon('home',color)
