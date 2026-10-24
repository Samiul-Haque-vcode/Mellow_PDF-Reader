from shiboken6 import isValid
from PySide6.QtCore import Qt, QPointF, Signal, QTimer, QModelIndex, QMargins, QEvent,QRectF
from PySide6.QtGui import QColor,QPainter,QPalette,QAction,QKeySequence,QTransform,QPen
from PySide6.QtPdf import QPdfLinkModel
from PySide6.QtPdfWidgets import QPdfView
from .theme import PageTheme, normalize_theme, canvas_color, tuning_values,overlay_colors
from .geometry import page_layout, page_at, viewport_point, page_transform
from .references import Target,references_in
from .selection import TextSelection
from .selection_controls import SelectionControls
from .search_model import SearchModel
from .icons import icon


class Reader(SelectionControls,QPdfView):
    focused = Signal(object)
    previewRequested = Signal(object, object)
    referenceRequested = Signal(object, str)
    locationChanged = Signal()
    selectionChanged = Signal(bool)
    zoomLockChanged = Signal(bool)
    findRequested = Signal(object,str)
    marginsRequested = Signal(object)
    referenceNavigationRequested = Signal(object,str)

    def __init__(self, document, path, parent=None):
        super().__init__(parent)
        self.zoom_locked=False
        self._positioning=False
        self._custom_search_index=-1
        self.rotation=0
        self.crop=(0.,0.,0.,0.)
        self._page_layout_mode='continuous'
        self.cover_separate=True
        self.pane_active=False
        self._wheel_last=0.0
        self._wheel_distance=0.0
        self._wheel_direction=0
        self._wheel_page_turned=False
        self.path = path
        self.text_selection=TextSelection(document)
        self.setup_selection_controls()
        self._left_down=False
        self._selection_drag=False
        self._press_position=QPointF()
        self._selection_pointer=QPointF()
        self._pressed_link=None
        self._pressed_url=None
        self._selection_timer=QTimer(self)
        self._selection_timer.setInterval(30)
        self._selection_timer.timeout.connect(self.selection_autoscroll)
        self.copy_action=QAction(icon('copy'),'Copy selected text',self)
        self.copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.copy_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.copy_action.setEnabled(False)
        self.copy_action.triggered.connect(lambda:self.copy_selection())
        self.addAction(self.copy_action)
        self.copy_joined_action=QAction('Join paragraph lines',self)
        self.copy_joined_action.setEnabled(False)
        self.copy_joined_action.triggered.connect(lambda:self.copy_selection(True))
        self.reading_actions={'copy':self.copy_action}
        self.find_selection_action=QAction('Find selected text',self)
        self.find_selection_action.triggered.connect(lambda:self.findRequested.emit(self,self.selected_text()))
        self.find_selection_action.setEnabled(False)
        self.reading_actions['find_selection']=self.find_selection_action
        commands={'screen_next':lambda:self.scroll_screen(1),'screen_previous':lambda:self.scroll_screen(-1),
                  'line_up':lambda:self.scroll_line(-1),'line_down':lambda:self.scroll_line(1),
                  'page_left':lambda:self.jump(self.pageNavigator().currentPage()-1),
                  'page_right':lambda:self.jump(self.pageNavigator().currentPage()+1),
                  'select_page':self.select_page_text,'select_document':self.select_document_text}
        from .shortcuts import COMMANDS
        for key,callback in commands.items():
            action=QAction(COMMANDS[key][0],self)
            action.triggered.connect(callback)
            action.setShortcut(QKeySequence(COMMANDS[key][2]))
            self.reading_actions[key]=action
        for key,action in self.reading_actions.items():
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            if key!='copy': self.addAction(action)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setDocument(document)
        from PySide6.QtWidgets import QFrame
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setPageMode(QPdfView.PageMode.MultiPage)
        self.setDocumentMargins(QMargins(6,6,6,6))
        self.setZoomMode(QPdfView.ZoomMode.FitInView)
        self.search = SearchModel(self)
        self.search.setDocument(document)
        self.links = QPdfLinkModel(self)
        self.links.setDocument(document)
        self.effect = PageTheme(self)
        self.setGraphicsEffect(self.effect)
        self.ruler = False
        self.ruler_y = 100
        self.ruler_height = 28
        self.ruler_opacity = 35
        self.default_copy_format = 'preserve'
        self.marker = None
        self.zoom_speed = 1.0
        self._zoom_target = None
        self._zoom_anchor = None
        self._zoom_timer = QTimer(self)
        self._zoom_timer.setSingleShot(True)
        self._zoom_timer.setInterval(16)
        self._zoom_timer.timeout.connect(self.flush_zoom)
        for bar in (self.verticalScrollBar(),self.horizontalScrollBar()):
            bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            bar.customContextMenuRequested.connect(lambda point,b=bar:self.scrollbar_context(b,point))
            for signal in (bar.sliderPressed,bar.sliderMoved,bar.actionTriggered):
                signal.connect(self.scrollbar_input)
        self.viewport().grabGesture(Qt.GestureType.PinchGesture)
        self._layout_key = None
        self._layout = []
        self._layout_tops = []
        self._pending = None
        self._revision = 0
        self._past = []
        self._future = []
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context)
        self.horizontalScrollBar().valueChanged.connect(self.locationChanged)
        self.verticalScrollBar().valueChanged.connect(self.locationChanged)
        self.zoomFactorChanged.connect(self.locationChanged)
        self.zoomModeChanged.connect(self.locationChanged)
        from .rotation import RotatedPages
        self.rotated_pages=RotatedPages(self)
        self.zoomFactorChanged.connect(self.rotated_pages.queue_sync)
        self.zoomModeChanged.connect(self.rotated_pages.queue_sync)
        self.search.rowsInserted.connect(lambda *_:self.viewport().update())
        self.search.modelReset.connect(lambda:self.setCurrentSearchResultIndex(-1))
        self.search.searchStringChanged.connect(lambda *_:self.setCurrentSearchResultIndex(-1))
        self.currentSearchResultIndexChanged.connect(lambda *_:self.viewport().update())
        from .reading_aids import ReadingAids
        self.aids=ReadingAids(self)

    def set_zoom_locked(self,locked):
        locked=bool(locked and self.document())
        if locked==self.zoom_locked:return
        if locked:
            self.flush_zoom()
            factor=self.effective_zoom();state=self.state()
            self.setZoomMode(QPdfView.ZoomMode.Custom);self.setZoomFactor(factor)
            self.restore_view_anchor(state)
        self.zoom_locked=locked
        self.zoomLockChanged.emit(locked);self.locationChanged.emit()

    def setZoomMode(self,mode):
        if getattr(self,'zoom_locked',False) and mode!=self.ZoomMode.Custom:return
        super().setZoomMode(mode)

    def setZoomFactor(self,factor):
        if getattr(self,'zoom_locked',False) and factor!=self.zoomFactor():return
        super().setZoomFactor(factor)

    def set_pane_active(self,active):
        if active==self.pane_active: return
        self.pane_active=active
        self.setAccessibleDescription('Active split reading pane' if active else '')
        self.viewport().update()

    def pageNavigator(self):
        if self.custom_rendering and hasattr(self,'rotated_pages'): return self.rotated_pages.navigator
        return super().pageNavigator()
    @property
    def facing_pages(self):
        return getattr(self,'_page_layout_mode','continuous') in ('two','two_continuous')
    @property
    def custom_rendering(self):
        return bool(getattr(self,'rotation',0) or self.facing_pages or any(getattr(self,'crop',())))
    def page_label(self,page):
        from .reading_options import page_label
        return page_label(self.document(),page)
    def set_crop(self,margins):
        from .reading_options import crop_values
        margins=crop_values(margins)
        if margins==self.crop:return
        current=self.pageNavigator().currentPage()
        was_custom=self.custom_rendering
        index=self.currentSearchResultIndex()
        self.crop=margins
        if not was_custom and self.custom_rendering:self._custom_search_index=index
        self._layout_key=None
        self.rotated_pages.set_document(self.document() if self.custom_rendering else None)
        self.pageNavigator().jump(current,QPointF())
        if was_custom and not self.custom_rendering:
            self.setCurrentSearchResultIndex(index)
            factor=self.zoomFactor();self.setZoomFactor(factor+1e-6);self.setZoomFactor(factor)
        self.rotated_pages.queue_sync()
        self.viewport().update()
    def change_crop(self,margins):
        self.flush_zoom()
        state=self.state()
        state.update(crop=list(margins),page=state.get('anchor_page',state['page']),viewport=None)
        self.restore(state)
    @property
    def page_layout_mode(self):
        return self._page_layout_mode
    def currentSearchResultIndex(self):
        return self._custom_search_index
    def setCurrentSearchResultIndex(self,index):
        self._custom_search_index=index
        self.currentSearchResultIndexChanged.emit(index)
        self.viewport().update()
    def set_page_layout(self,name):
        name=name if name in ('continuous','single','two','two_continuous') else 'continuous'
        if self.page_layout_mode==name: return
        current=max(0,self.pageNavigator().currentPage())
        was_custom=self.custom_rendering
        index=self.currentSearchResultIndex()
        self._page_layout_mode=name
        if not was_custom and self.custom_rendering:self._custom_search_index=index
        self.setPageMode(self.PageMode.SinglePage if name in ('single','two') else self.PageMode.MultiPage)
        self._layout_key=None
        self._wheel_distance=0
        self._wheel_page_turned=False
        if hasattr(self,'rotated_pages'):
            if was_custom!=self.custom_rendering: self.rotated_pages.set_document(self.document() if self.custom_rendering else None)
            self.pageNavigator().jump(current,QPointF())
            self.rotated_pages.queue_sync()
        if was_custom and not self.custom_rendering:self.setCurrentSearchResultIndex(index)
    def change_cover(self,separate):
        if bool(separate)==self.cover_separate: return
        self.flush_zoom();snapshot=self.state()
        snapshot.update(cover=bool(separate),viewport=None)
        self.restore(snapshot)
    def change_layout(self,name):
        name=name if name in ('continuous','single','two','two_continuous') else 'continuous'
        if name==self.state().get('layout',self.page_layout_mode): return
        self.flush_zoom()
        snapshot=self.state()
        snapshot.update(layout=name,page=snapshot.get('anchor_page',snapshot['page']),viewport=None)
        self.restore(snapshot)
    def set_rotation(self,angle):
        angle=int(angle)%360
        if angle not in (0,90,180,270): angle=0
        if angle==self.rotation: return
        was_custom=self.custom_rendering
        index=self.currentSearchResultIndex()
        self.rotation=angle
        if not was_custom and self.custom_rendering:self._custom_search_index=index
        self._layout_key=None
        self.rotated_pages.set_document(self.document() if self.custom_rendering else None)
        if self.custom_rendering: self.rotated_pages.queue_sync()
        else:
            # Ask the native view to recompute its unrotated scroll ranges.
            factor=self.zoomFactor()
            self.setZoomFactor(factor+1e-6)
            self.setZoomFactor(factor)
        if was_custom and not self.custom_rendering:self.setCurrentSearchResultIndex(index)
        self.viewport().update()
    def rotate_by(self,angle):
        self.flush_zoom()
        point=QPointF(self.viewport().rect().center())
        hit=self.selection_hit(point)
        self.cancel_zoom()
        self._revision+=1
        self._pending=None
        self.set_rotation(self.rotation+angle)
        if hit:
            page,location=hit
            self.pageNavigator().jump(page,location)
            for number,rect,scale in self.page_entries(page):
                if number==page:
                    rotated=page_transform(self,page).map(location)
                    self.horizontalScrollBar().setValue(round(rect.x()+rotated.x()*scale-point.x()))
                    self.verticalScrollBar().setValue(round(rect.y()+rotated.y()*scale-point.y()))
                    break
        self.locationChanged.emit()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'rotated_pages'): self.rotated_pages.queue_sync()
    def scrollContentsBy(self,dx,dy):
        if self.custom_rendering and hasattr(self,'rotated_pages'):
            self.rotated_pages.scrolled()
        else: super().scrollContentsBy(dx,dy)
    def turn_page(self,direction):
        if not self.document(): return False
        page=self.pageNavigator().currentPage()+direction
        if self.facing_pages:
            from .geometry import spreads
            rows=spreads(self.document().pageCount(),self.cover_separate)
            row=next((i for i,pair in enumerate(rows) if self.pageNavigator().currentPage() in pair),0)+direction
            if not 0<=row<len(rows): return False
            page=next(p for p in rows[row] if p is not None)
        if not 0<=page<self.document().pageCount(): return False
        self.jump(page,record=False)
        if direction<0: self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        return True
    def at_page_edge(self,direction):
        bar=self.verticalScrollBar()
        margins=self.documentMargins()
        # Fit Page can retain a few pixels of native Qt document margin.
        fits=self.zoomMode()==self.ZoomMode.FitInView and bar.maximum()<=margins.top()+margins.bottom()+self.pageSpacing()
        return fits or (bar.value()>=bar.maximum()-margins.bottom() if direction>0 else bar.value()<=bar.minimum()+margins.top())
    def scroll_screen(self,direction):
        self.flush_zoom()
        if self.page_layout_mode in ('single','two') and self.at_page_edge(direction):
            self.turn_page(direction)
            return
        self._revision+=1
        self._pending=None
        self.verticalScrollBar().setValue(self.verticalScrollBar().value()+direction*max(1,self.viewport().height()-self.fontMetrics().lineSpacing()*2))
        if self.custom_rendering:self.rotated_pages.update_navigation()
    def scroll_line(self,direction):
        self.flush_zoom()
        self._revision+=1
        self._pending=None
        self.verticalScrollBar().setValue(self.verticalScrollBar().value()+direction*self.fontMetrics().lineSpacing())
        if self.custom_rendering:self.rotated_pages.update_navigation()

    def layout_pages(self):
        m = self.documentMargins()
        key = (id(self.document()),self.document().pageCount() if self.document() else 0,
               self.viewport().width(),self.viewport().height(),self.zoomFactor(),self.zoomMode(),
               m.left(),m.top(),m.right(),m.bottom(),self.pageSpacing(), self.pageMode(),self.page_layout_mode,self.cover_separate,self.logicalDpiX(),
               self.crop,self.rotation,
               self.pageNavigator().currentPage() if self.pageMode()==QPdfView.PageMode.SinglePage else -1)
        if key != self._layout_key:
            self._layout_key, self._layout = key, page_layout(self)
            self._layout_tops=self._layout.tops
            self._layout_by_page=self._layout.by_page
            self._layout_bottoms=self._layout.bottoms
            self._layout_extent=self._layout.extent
        return self._layout

    def layout_for_page(self,page):
        self.layout_pages()
        return self._layout_by_page.get(page)

    def page_entries(self,page):
        entry=self.layout_for_page(page)
        return (entry,) if entry is not None else ()

    def visible_pages(self):
        """Intersect only candidate rows, including unequal-height spreads."""
        import bisect
        layouts=self.layout_pages()
        sy=self.verticalScrollBar().value();sx=self.horizontalScrollBar().value()
        visible=QRectF(self.viewport().rect()).translated(sx,sy)
        first=bisect.bisect_right(self._layout_bottoms,visible.top())
        last=bisect.bisect_right(self._layout_tops,visible.bottom())
        return [entry for entry in layouts[first:last] if entry[1].intersects(visible)]

    def point_on_page(self, point):
        return page_at(self,point)

    def point_in_view(self, page, point):
        return viewport_point(self,page,point)

    def internal_link(self, point):
        hit = self.point_on_page(point)
        if not hit:
            return None
        page, location = hit
        self.links.setPage(page)
        link = self.links.linkAt(location)
        if link.isValid() and not link.url().isValid() and 0 <= link.page() < self.document().pageCount():
            return Target(link.page(),max(0,link.location().x()),max(0,link.location().y()),f'Linked reference · page {link.page()+1}')
        return None

    def selected_text(self):
        return self.text_selection.text()
    def selection_updated(self):
        selected=bool(self.text_selection.ranges)
        self.copy_action.setEnabled(selected)
        self.copy_joined_action.setEnabled(selected)
        self.find_selection_action.setEnabled(selected and len(self.text_selection.ranges)==1)
        self.selectionChanged.emit(selected)
        self.viewport().update()
    def clear_selection(self):
        self.cancel_selection_work()
        self.text_selection.clear()
        self.selection_updated()
    def copy_selection(self,join_paragraphs=None):
        if join_paragraphs is None:join_paragraphs=self.default_copy_format=='paragraphs'
        return self.copy_text_selection(join_paragraphs)
    def select_page_text(self,page=None):
        if page is None: page=self.pageNavigator().currentPage()
        self.clear_selection()
        self.text_selection.select_page(page)
        self.selection_updated()
        if not self.text_selection.ranges:
            self.selection_hint('This page has no selectable text. Scanned PDFs may have no text layer.')
    def setDocument(self,document):
        if hasattr(self,'aids'):self.aids.set_lens_enabled(False)
        if self.document() is not document:self.zoom_locked=False
        if hasattr(self,'marker') and self.document() is not document:self.marker=None
        if hasattr(self,'_two_point_mode'):self.cancel_selection_work()
        if hasattr(self,'_zoom_timer'):self.cancel_zoom()
        if hasattr(self,'effect'):self.effect.clear_cache()
        if hasattr(self,'links'):self.links.setDocument(document)
        if hasattr(self,'_layout'):
            self._layout_key=None;self._layout=[];self._layout_tops=[]
            self._layout_by_page={};self._layout_bottoms=[];self._layout_extent=(0,0)
        if hasattr(self,'rotated_pages'): self.rotated_pages.set_document(document if self.custom_rendering else None)
        if hasattr(self,'text_selection'):
            self.text_selection.set_document(document)
            self.copy_action.setEnabled(False)
            self.copy_joined_action.setEnabled(False)
            self.find_selection_action.setEnabled(False)
        if hasattr(self,'search'):self.search.setDocument(document)
        super().setDocument(document)
        if hasattr(self,'aids'):self.aids.set_document(document)
    def scroll_here(self,bar,point):
        from PySide6.QtWidgets import QStyle,QStyleOptionSlider,QAbstractSlider
        option=QStyleOptionSlider()
        bar.initStyleOption(option)
        style=bar.style()
        groove=style.subControlRect(QStyle.ComplexControl.CC_ScrollBar,option,QStyle.SubControl.SC_ScrollBarGroove,bar)
        slider=style.subControlRect(QStyle.ComplexControl.CC_ScrollBar,option,QStyle.SubControl.SC_ScrollBarSlider,bar)
        vertical=bar.orientation()==Qt.Orientation.Vertical
        length=slider.height() if vertical else slider.width()
        span=(groove.height() if vertical else groove.width())-length
        position=(point.y()-groove.top() if vertical else point.x()-groove.left())-length//2
        value=QStyle.sliderValueFromPosition(bar.minimum(),bar.maximum(),position,max(0,span),option.upsideDown)
        self.scrollbar_input()
        bar.setSliderPosition(value)
        bar.triggerAction(QAbstractSlider.SliderAction.SliderMove)

    def scrollbar_menu(self,bar,point=None):
        from PySide6.QtWidgets import QMenu,QAbstractSlider
        point=point if point is not None else bar.rect().center()
        menu=QMenu(bar)
        start=menu.addAction('Start',lambda:bar.triggerAction(QAbstractSlider.SliderAction.SliderToMinimum))
        here=menu.addAction('Scroll here',lambda:self.scroll_here(bar,point))
        preview=menu.addAction('Page preview',lambda:self.page_thumbnails(bar))
        end=menu.addAction('End',lambda:bar.triggerAction(QAbstractSlider.SliderAction.SliderToMaximum))
        start.setEnabled(bar.value()>bar.minimum())
        end.setEnabled(bar.value()<bar.maximum())
        here.setEnabled(bar.maximum()>bar.minimum())
        preview.setEnabled(bool(self.document() and self.document().pageCount()))
        return menu

    def scrollbar_context(self,bar,point):
        self.focused.emit(self)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        menu=self.scrollbar_menu(bar,point)
        menu.exec(bar.mapToGlobal(point))
        if isValid(menu):menu.deleteLater()

    def page_thumbnails(self,anchor=None):
        from .pages import PagesPanel
        if not self.document() or not self.document().pageCount():return
        self.focused.emit(self)
        for existing in self.window().findChildren(PagesPanel):existing.reject()
        dialog=PagesPanel(self,self.window())
        dialog.position_near(anchor if anchor is not None else self.verticalScrollBar())
        dialog.exec()
        if isValid(self) and self.isVisible() and self.document():self.setFocus()
        if isValid(dialog):dialog.deleteLater()

    def set_quick_jump(self,hit=None):
        self.flush_zoom()
        self.marker=self.state()
        if hit:
            page,point=hit
            self.marker.update(page=page,anchor_page=page,x=point.x(),y=point.y(),viewport=None)

    def return_quick_jump(self):
        if self.marker is None or not self.document():return
        self.flush_zoom()
        # Returning is navigation too: retain the place we are leaving so
        # Back/Forward can retrace the visit without changing the marker.
        self.remember()
        self.restore(self.marker)

    def page_context_menu(self,point):
        from PySide6.QtWidgets import QMenu
        menu=QMenu(self)
        hit=self.point_on_page(QPointF(point))
        action=menu.addAction('Set Quick Jump Here',lambda:self.set_quick_jump(hit))
        action.setEnabled(hit is not None)
        action=menu.addAction('Return to Quick Jump',self.return_quick_jump)
        action.setEnabled(self.marker is not None)
        menu.addSeparator()
        menu.addAction('Select Between Two Points…',self.start_point_selection)
        if self.find_selection_action.isEnabled():menu.addAction(self.find_selection_action)
        menu.addSeparator()
        menu.addAction('Trim Reading Margins…',lambda:self.marginsRequested.emit(self))
        link=self.internal_link(QPointF(point)) if hit else None
        labels=references_in(self.document().getAllText(hit[0]).text()) if hit and not link else []
        if link:
            menu.addSeparator()
            menu.addAction('Preview Reference',lambda:self.previewRequested.emit(self,link))
            menu.addAction('Go to Reference',lambda:self.jump(link.page,link.point()))
        elif labels:
            menu.addSeparator()
            previews=menu.addMenu('Preview Reference')
            destinations=menu.addMenu('Go to Reference')
            for label in labels[:40]:
                previews.addAction(label,lambda checked=False,label=label:self.referenceRequested.emit(self,label))
                destinations.addAction(label,lambda checked=False,label=label:self.referenceNavigationRequested.emit(self,label))
        return menu

    def context(self,point):
        self.focused.emit(self)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        menu=self.page_context_menu(point)
        menu.exec(self.viewport().mapToGlobal(point))
        if isValid(menu):menu.deleteLater()

    def focusInEvent(self,event):
        super().focusInEvent(event)
        self.focused.emit(self)

    def mousePressEvent(self,event):
        self.focused.emit(self)
        if event.button()==Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            if self._two_point_mode:
                self.point_selection_click(event)
                return
            self.cancel_selection_work()
            self._left_down=True
            self._selection_drag=False
            self._press_position=event.position()
            self._selection_pointer=event.position()
            self._pressed_link=self.internal_link(event.position())
            self._pressed_url=None
            hit=self.point_on_page(event.position())
            if hit:
                page,point=hit
                if self.facing_pages:
                    self.pageNavigator().update(page,QPointF(),self.zoomFactor())
                    self.locationChanged.emit()
                self.links.setPage(page)
                url=self.links.linkAt(point).url()
                if url.isValid(): self._pressed_url=url
                extending=bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier) and self.text_selection.anchor is not None
                self.text_selection.begin(page,point,extending)
                if extending:
                    self._selection_drag=True
                    self._pressed_link=None
                    self._pressed_url=None
            else: self.text_selection.clear()
            self.selection_updated()
            event.accept()
            return
        super().mousePressEvent(event)
    def selection_hit(self,point):
        hit=self.point_on_page(point)
        if hit: return hit
        layouts=self.layout_pages()
        if not layouts: return None
        pos=point+QPointF(self.horizontalScrollBar().value(),self.verticalScrollBar().value())
        page,rect,scale=min(layouts,key=lambda row: max(row[1].left()-pos.x(),0,pos.x()-row[1].right())**2+max(row[1].top()-pos.y(),0,pos.y()-row[1].bottom())**2)
        return (page,page_transform(self,page).inverted()[0].map((pos-rect.topLeft())/scale)) if scale>0 else None
    def update_drag_selection(self):
        hit=self.selection_hit(self._selection_pointer)
        if hit:
            self.text_selection.select_to(*hit)
            self.selection_updated()
    def mouseMoveEvent(self,event):
        self.ruler_y=event.position().y()
        if self.ruler: self.viewport().update()
        if self._left_down:
            self._selection_pointer=event.position()
            if (event.position()-self._press_position).manhattanLength()>=3: self._selection_drag=True
            if self._selection_drag:
                self.update_drag_selection()
                y=event.position().y()
                if y<12 or y>self.viewport().height()-12:
                    if not self._selection_timer.isActive(): self._selection_timer.start()
                else: self._selection_timer.stop()
            event.accept()
            return
        if self._two_point_mode:
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)
            event.accept();return
        if self.internal_link(event.position()): self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else: self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self._point_release:
            self.point_selection_release(event)
            return
        if event.button()==Qt.MouseButton.LeftButton and self._left_down:
            self._selection_timer.stop()
            self._left_down=False
            if self._selection_drag:
                self._selection_pointer=event.position()
                self.update_drag_selection()
            elif self._pressed_link:
                self.previewRequested.emit(self,self._pressed_link)
            elif self._pressed_url:
                from .platform import open_external_link
                if not open_external_link(self._pressed_url):
                    self.selection_hint('Link could not be opened. Only web and email links are supported.')
            self._pressed_link=None
            self._pressed_url=None
            event.accept()
            return
        super().mouseReleaseEvent(event)
    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self._two_point_mode:
            self.point_selection_click(event)
            return
        if event.button()==Qt.MouseButton.LeftButton:
            hit=self.point_on_page(event.position())
            if hit:
                self.text_selection.select_word(*hit)
                self.selection_updated()
            self._selection_drag=True
            self._left_down=False
            self._pressed_link=None
            self._pressed_url=None
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
    def selection_autoscroll(self):
        if not self._left_down or not self._selection_drag:
            self._selection_timer.stop()
            return
        y=self._selection_pointer.y()
        height=self.viewport().height()
        delta=-min(80,16+int(abs(y))) if y<12 else min(80,16+int(max(0,y-height)))
        self.verticalScrollBar().setValue(self.verticalScrollBar().value()+delta)
        self.update_drag_selection()
    def paint_selection(self,painter):
        if not self.text_selection.ranges: return
        sx,sy=self.horizontalScrollBar().value(),self.verticalScrollBar().value()
        visible=self.viewport().rect().translated(sx,sy)
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(overlay_colors(self.effect.theme)[0])
        for page,rect,scale in self.visible_pages():
            if not rect.intersects(visible): continue
            selected=self.text_selection.page(page)
            if not selected: continue
            painter.save()
            painter.setClipRect(rect.translated(-sx,-sy),Qt.ClipOperation.IntersectClip)
            transform=page_transform(self,page)*QTransform().translate(rect.x()-sx,rect.y()-sy).scale(scale,scale)
            for polygon in selected.bounds(): painter.drawPolygon(transform.map(polygon))
            painter.restore()
        painter.restore()
    def paintEvent(self,event):
        if not self.custom_rendering: super().paintEvent(event)
        painter=QPainter(self.viewport())
        if self.custom_rendering: self.rotated_pages.paint(painter)
        if self.ruler:
            painter.fillRect(0,int(self.ruler_y-self.ruler_height/2),self.viewport().width(),
                             self.ruler_height,QColor(170,145,65,self.ruler_opacity))
        if not self.effect.isEnabled(): self.paint_overlays(painter)
        painter.end()
    def paint_overlays(self,painter):
        # Draw these after page toning, so their contrast survives every theme.
        self.paint_search_results(painter)
        self.paint_selection(painter)
        index=self.currentSearchResultIndex()
        if self.search.searchString() and 0<=index<self.search.rowCount(QModelIndex()):
            result=self.search.resultAtIndex(index)
            sx,sy=self.horizontalScrollBar().value(),self.verticalScrollBar().value()
            for page,rect,scale in self.visible_pages():
                if page!=result.page(): continue
                transform=page_transform(self,page)*QTransform().translate(rect.x()-sx,rect.y()-sy).scale(scale,scale)
                color=overlay_colors(self.effect.theme)[2]
                painter.save()
                painter.setClipRect(rect.translated(-sx,-sy),Qt.ClipOperation.IntersectClip)
                painter.setPen(QPen(color,2))
                color.setAlpha(45)
                painter.setBrush(color)
                for bounds in result.rectangles(): painter.drawRect(transform.mapRect(bounds).adjusted(-1,-1,1,1))
                painter.restore()
                break
        if self.pane_active:
            color='#acd8bd' if normalize_theme(self.effect.theme) in ('Dark','Black') else '#527c64'
            painter.fillRect(0,0,self.viewport().width(),2,QColor(color))
    def paint_search_results(self,painter):
        if not self.search.searchString(): return
        sx,sy=self.horizontalScrollBar().value(),self.verticalScrollBar().value()
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(overlay_colors(self.effect.theme)[1])
        for page,rect,scale in self.visible_pages():
            if not rect.translated(-sx,-sy).intersects(self.viewport().rect()): continue
            painter.save()
            painter.setClipRect(rect.translated(-sx,-sy),Qt.ClipOperation.IntersectClip)
            transform=page_transform(self,page)*QTransform().translate(rect.x()-sx,rect.y()-sy).scale(scale,scale)
            for result in self.search.resultsOnPage(page):
                for bounds in result.rectangles(): painter.drawRect(transform.mapRect(bounds))
            painter.restore()
        painter.restore()
    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape and self.aids.lens_enabled:
            self.aids.set_lens_enabled(False);event.accept();return
        if event.key()==Qt.Key.Key_Escape and (self.text_selection.ranges or self._two_point_mode or self._copy_job):
            self.clear_selection()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Space,Qt.Key.Key_Up,Qt.Key.Key_Down,Qt.Key.Key_Left,Qt.Key.Key_Right) and event.modifiers() in (Qt.KeyboardModifier.NoModifier,Qt.KeyboardModifier.ShiftModifier):
            # A disabled/remapped reading action must not fall through to the
            # scroll area's different built-in arrow/Space behavior.
            event.accept()
            return
        super().keyPressEvent(event)

    def state(self, include_history=False):
        if self._pending:
            result = dict(self._pending)
        else:
            nav=self.pageNavigator()
            sx,sy=self.horizontalScrollBar().value(),self.verticalScrollBar().value()
            layouts=self.layout_pages()
            anchor=self.layout_for_page(nav.currentPage())
            if anchor and not anchor[1].top()<=sy+self.documentMargins().top()<=anchor[1].bottom():anchor=None
            if anchor is None:
                import bisect
                index=bisect.bisect_left(self._layout_bottoms,sy)
                anchor=layouts[index] if index<len(layouts) else None
            if anchor and anchor[2]>0:
                page,rect,scale=anchor
                point=page_transform(self,page).inverted()[0].map(QPointF((sx-rect.x())/scale,(sy-rect.y())/scale))
                x,y=point.x(),point.y()
            else:
                page,x,y=nav.currentPage(),0,0
            result=dict(path=self.path,page=nav.currentPage(),anchor_page=page,x=x,y=y,
                        zoom=self.zoomFactor(),mode=self.zoomMode().value,
                        horizontal=sx,vertical=sy,viewport=[self.viewport().width(),self.viewport().height()])
        result.pop('past',None)
        result.setdefault('rotation',self.rotation)
        result.setdefault('layout',self.page_layout_mode)
        result.setdefault('cover',self.cover_separate)
        result.setdefault('crop',list(self.crop))
        result.setdefault('dpi',self.logicalDpiX())
        result.setdefault('dpr',self.devicePixelRatioF())
        result.pop('future',None)
        if include_history:
            result['past']=self._past[-50:]
            result['future']=self._future[-50:]
        return result

    def restore(self,state,defer=False):
        if self.zoom_locked:
            state=dict(state,mode=self.ZoomMode.Custom.value,zoom=self.zoomFactor(),viewport=None)
        self.cancel_zoom()
        self._revision+=1
        revision=self._revision
        self._pending=dict(state)
        def apply():
            if revision!=self._revision or not self.document(): return
            self.cover_separate=bool(state.get('cover',self.cover_separate))
            self.set_crop(state.get('crop',self.crop))
            self._layout_key=None
            self.set_page_layout(state.get('layout',self.page_layout_mode))
            self.set_rotation(state.get('rotation',0))
            self.setZoomFactor(state.get('zoom',self.zoomFactor()))
            self.setZoomMode(QPdfView.ZoomMode(state.get('mode',self.zoomMode().value)))
            self.pageNavigator().jump(max(0,min(state.get('page',0),self.document().pageCount()-1)),QPointF())
            self._position_state(state)
            # Native page-mode changes can settle scrollbar ranges after this
            # call. Reapply once against the final viewport, unless newer input
            # has invalidated this restoration.
            def settled():
                if revision==self._revision and self.document():
                    self._position_state(state)
                    self.locationChanged.emit()
            QTimer.singleShot(0,settled)
            self._pending=None
            if 'past' in state: self._past=list(state['past'])[-50:]
            if 'future' in state: self._future=list(state['future'])[-50:]
            self.locationChanged.emit()
        if defer: QTimer.singleShot(0,apply)
        else: apply()

    def _position_state(self,state):
        self._positioning=True
        try:
            if self.custom_rendering: self.rotated_pages.sync()
            if (state.get('viewport')==[self.viewport().width(),self.viewport().height()] and
                    state.get('dpi',self.logicalDpiX())==self.logicalDpiX() and state.get('dpr',self.devicePixelRatioF())==self.devicePixelRatioF()):
                self.horizontalScrollBar().setValue(state.get('horizontal',0))
                self.verticalScrollBar().setValue(state.get('vertical',0))
            else:
                anchor=state.get('anchor_page',state.get('page',0))
                for page,rect,scale in self.page_entries(anchor):
                    if page==anchor:
                        point=page_transform(self,page).map(QPointF(state.get('x',0),state.get('y',0)))
                        if state.get('viewport') is None and any(self.crop):
                            point=QPointF(max(0,min(rect.width()/scale,point.x())),max(0,min(rect.height()/scale,point.y())))
                        self.horizontalScrollBar().setValue(round(rect.x()+point.x()*scale))
                        self.verticalScrollBar().setValue(round(rect.y()+point.y()*scale))
                        break
        finally:self._positioning=False

    def restore_view_anchor(self,state):
        """Keep the same PDF coordinate after a window resize, without a jump.

        Fullscreen/layout changes are not navigation: leave zoom and navigation
        history untouched and invalidate older queued location corrections.
        """
        if not self.document(): return
        self._revision+=1
        self._pending=None
        page=state.get('anchor_page',state.get('page',0))
        for number,rect,scale in self.page_entries(page):
            if number==page:
                point=page_transform(self,page).map(QPointF(state.get('x',0),state.get('y',0)))
                self.horizontalScrollBar().setValue(round(rect.x()+point.x()*scale))
                self.verticalScrollBar().setValue(round(rect.y()+point.y()*scale))
                break
        self.locationChanged.emit()

    def suspend(self):
        self._selection_timer.stop()
        self._left_down=False
        self.flush_zoom()
        snapshot=self.state()
        self._revision+=1
        self._pending=snapshot
        self.hide()

    def hideEvent(self,event):
        if hasattr(self,'aids'):self.aids.set_lens_enabled(False)
        if self._two_point_mode:self.clear_selection()
        else:self.cancel_selection_work()
        if hasattr(self,'effect'):self.effect.clear_cache()
        if hasattr(self,'rotated_pages'):self.rotated_pages.pause()
        if hasattr(self,'search'):self.search.set_paused(True)
        super().hideEvent(event)

    def showEvent(self,event):
        super().showEvent(event)
        if hasattr(self,'search'):self.search.set_paused(False)
        if hasattr(self,'rotated_pages') and self.custom_rendering:
            self.rotated_pages.resume()

    def jump(self,page,location=QPointF(),record=True,defer=False):
        if not self.document(): return
        self.flush_zoom()
        if record: self.remember()
        if defer:
            snapshot=self.state()
            self._revision+=1
            revision=self._revision
            snapshot.update(page=page,anchor_page=page,x=location.x(),y=location.y(),viewport=None)
            self._pending=snapshot
            def settled():
                if revision==self._revision:
                    self.jump(page,location,record=False)
            QTimer.singleShot(0,settled)
            return
        self._revision+=1
        self._pending=None
        page=max(0,min(page,self.document().pageCount()-1))
        self._positioning=True
        try:
            self.pageNavigator().jump(page,location)
            for index,rect,scale in self.page_entries(page):
                if index==page:
                    point=page_transform(self,page).map(location) if not location.isNull() else QPointF()
                    if any(self.crop):
                        point=QPointF(max(0,min(rect.width()/scale,point.x())),max(0,min(rect.height()/scale,point.y())))
                    self.verticalScrollBar().setValue(round(rect.top()+point.y()*scale))
                    if location.x()>0 or self.custom_rendering:
                        self.horizontalScrollBar().setValue(round(rect.left()+point.x()*scale))
                    break
        finally:self._positioning=False
        self.locationChanged.emit()

    def remember(self):
        self._past.append(self.state())
        self._past=self._past[-50:]
        self._future.clear()
    def visit_search(self,index):
        if index<0 or not self.search.searchString(): return
        # Only published filtered matches have stable result indices.
        result=self.search.resultAtIndex(index)
        if not result.isValid(): return
        self.remember()
        self.setCurrentSearchResultIndex(index)
        self.jump(result.page(),result.location(),record=False)
    def back(self):
        if self._past:
            self._future.append(self.state())
            self.restore(self._past.pop())
    def forward(self):
        if self._future:
            self._past.append(self.state())
            self.restore(self._future.pop())
    def theme(self,name,preserve=True,tuning=None):
        name=normalize_theme(name)
        warmth,contrast=tuning_values(tuning)
        canvas=canvas_color(name,warmth,contrast)
        palette=self.palette()
        palette.setColor(QPalette.ColorRole.Dark,QColor(canvas))
        palette.setColor(QPalette.ColorRole.Base,QColor(canvas))
        palette.setColor(QPalette.ColorRole.Window,QColor(canvas))
        self.setPalette(palette)
        self.viewport().setPalette(palette)
        self.viewport().setBackgroundRole(QPalette.ColorRole.Dark)
        self.viewport().setAutoFillBackground(True)
        self.effect.theme,self.effect.preserve=name,preserve
        self.effect.warmth,self.effect.contrast=warmth,contrast
        self.effect.clear_cache()
        self.effect.setEnabled(name!='Light')
        self.effect.update()
        if hasattr(self,'aids'):self.aids.refresh()
        self.viewport().update()

    def cancel_zoom(self):
        self._zoom_timer.stop()
        self._zoom_target=None
        self._zoom_anchor=None

    def scrollbar_input(self,*_):
        # A real thumb drag/page-step is newer input than queued zoom or
        # session positioning. Do not snap back on the next event turn.
        self.cancel_zoom()
        self._revision+=1
        self._pending=None

    def zoom_by(self,factor,point=None,smooth=False):
        if self.zoom_locked:return
        import math
        if not math.isfinite(factor) or factor<=0: return
        base=self._zoom_target if self._zoom_target is not None else self.effective_zoom()
        self.zoom_to(base*factor,point,smooth)

    def zoom_to(self,factor,point=None,smooth=False):
        if self.zoom_locked:return
        import math
        if not math.isfinite(factor) or factor<=0 or not self.document(): return
        point=QPointF(point) if point is not None else QPointF(self.viewport().rect().center())
        hit=self.point_on_page(point)
        if hit is None:
            # Margins/gaps still anchor to the closest page, rather than jumping
            # to the document origin when a gesture starts outside its text.
            layouts=self.layout_pages()
            if not layouts: return
            pos=point+QPointF(self.horizontalScrollBar().value(),self.verticalScrollBar().value())
            page,rect,scale=min(layouts,key=lambda item: max(item[1].left()-pos.x(),0,pos.x()-item[1].right())**2+max(item[1].top()-pos.y(),0,pos.y()-item[1].bottom())**2)
            if scale<=0: return
            hit=(page,page_transform(self,page).inverted()[0].map((pos-rect.topLeft())/scale))
        if self.facing_pages:self.pageNavigator().update(hit[0],QPointF(),self.zoomFactor())
        self._zoom_target=max(.1,min(8,factor))
        self._zoom_anchor=(hit[0],QPointF(hit[1]),point)
        if smooth:
            if not self._zoom_timer.isActive(): self._zoom_timer.start()
        else: self.flush_zoom()

    def flush_zoom(self):
        if self._zoom_target is None: return
        factor,anchor=self._zoom_target,self._zoom_anchor
        self.cancel_zoom()
        self._revision+=1
        revision=self._revision
        self._pending=None
        page,location,point=anchor
        self.setZoomMode(QPdfView.ZoomMode.Custom)
        self.setZoomFactor(factor)
        def position():
            if revision!=self._revision or not self.document(): return
            for index,rect,scale in self.page_entries(page):
                if index==page:
                    rotated=page_transform(self,page).map(location)
                    self.horizontalScrollBar().setValue(round(rect.x()+rotated.x()*scale-point.x()))
                    self.verticalScrollBar().setValue(round(rect.y()+rotated.y()*scale-point.y()))
                    break
            self.locationChanged.emit()
        position()
        # Scrollbars can change the viewport while transitioning from Fit Page.
        # A queued correction uses the final layout and never overrides newer input.
        QTimer.singleShot(0,position)

    def wheelEvent(self,event):
        self.focused.emit(self)
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta=event.pixelDelta().y()/80 if not event.pixelDelta().isNull() else event.angleDelta().y()/120
            if delta:
                self.setFocus(Qt.FocusReason.MouseFocusReason)
                # Clamp one event to keep malformed drivers from jumping to 800%.
                steps=max(-6,min(6,delta*self.zoom_speed))
                self.zoom_by(1.15**steps,event.position(),smooth=True)
            event.accept()
            return
        self.flush_zoom()
        self._revision+=1
        self._pending=None
        if self.page_layout_mode in ('single','two') and self.single_page_wheel(event): return
        super().wheelEvent(event)
        if self.custom_rendering:self.rotated_pages.update_navigation()

    def single_page_wheel(self,event):
        """Turn at page boundaries without skipping pages on touchpad momentum."""
        import time
        phase=event.phase()
        if phase==Qt.ScrollPhase.ScrollEnd:
            self._wheel_page_turned=False
            self._wheel_distance=0
            return False
        if event.modifiers()!=Qt.KeyboardModifier.NoModifier: return False
        pixel=event.pixelDelta()
        delta=pixel.y() if not pixel.isNull() else event.angleDelta().y()
        horizontal=pixel.x() if not pixel.isNull() else event.angleDelta().x()
        if not delta or abs(horizontal)>abs(delta): return False
        direction=1 if delta<0 else -1
        now=time.monotonic()
        if phase==Qt.ScrollPhase.ScrollBegin or now-self._wheel_last>.3 or direction!=self._wheel_direction:
            self._wheel_page_turned=False
            self._wheel_distance=0
        self._wheel_last=now
        self._wheel_direction=direction
        if self._wheel_page_turned:
            event.accept()
            return True
        if not self.at_page_edge(direction):
            self._wheel_distance=0
            return False
        if phase!=Qt.ScrollPhase.ScrollMomentum:
            self._wheel_distance+=abs(delta)
            threshold=60 if not pixel.isNull() else 120
            if self._wheel_distance>=threshold:
                self.turn_page(direction)
                self._wheel_distance=0
                self._wheel_page_turned=phase!=Qt.ScrollPhase.NoScrollPhase
        event.accept()
        return True

    def _gesture(self,event,offset=QPointF()):
        from PySide6.QtCore import QEvent
        if event.type()==QEvent.Type.NativeGesture:
            if event.gestureType()==Qt.NativeGestureType.ZoomNativeGesture:
                value=max(-.8,min(.8,event.value()*self.zoom_speed))
                self.focused.emit(self)
                self.setFocus(Qt.FocusReason.MouseFocusReason)
                self.zoom_by(1+value,event.position()-offset,smooth=True)
                event.accept()
                return True
        elif event.type()==QEvent.Type.Gesture:
            gesture=event.gesture(Qt.GestureType.PinchGesture)
            if gesture:
                previous=gesture.lastScaleFactor()
                if previous>0:
                    self.focused.emit(self)
                    self.setFocus(Qt.FocusReason.MouseFocusReason)
                    ratio=gesture.scaleFactor()/previous
                    self.zoom_by(max(.2,min(5,ratio))**self.zoom_speed,
                                 gesture.centerPoint()-offset,smooth=True)
                event.accept(gesture)
                return True
        return False

    def viewportEvent(self,event):
        if self._gesture(event): return True
        return super().viewportEvent(event)

    def event(self,event):
        # Native touchpad gestures may target either the viewport or scroll area.
        if event.type() in (QEvent.Type.NativeGesture,QEvent.Type.Gesture):
            if self._gesture(event,QPointF(self.viewport().pos())): return True
        return super().event(event)

    def effective_zoom(self):
        from PySide6.QtWidgets import QApplication
        layouts=self.layout_pages()
        if not layouts: return self.zoomFactor()
        page=self.pageNavigator().currentPage()
        entry=next((row for row in layouts if row[0]==page),layouts[0])
        return entry[2]/(self.logicalDpiX()/72)
