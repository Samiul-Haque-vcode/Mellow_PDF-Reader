"""One adaptive toolbar; collapsing a button never disables its shared action."""
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtWidgets import QToolButton, QWidget, QHBoxLayout, QSizePolicy, QLayout
from PySide6.QtGui import QAction


class ReadingToolbar(QWidget):
    ROW_HEIGHT=32
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('readingToolbar')
        self.setAccessibleName('Reading controls')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        self._icon_size=QSize(18,18)
        self._button_style=Qt.ToolButtonStyle.ToolButtonIconOnly
        self.row=QHBoxLayout(self)
        self.row.setContentsMargins(8,0,8,0)
        self.row.setSpacing(4)
        self.row.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.setFixedHeight(self.ROW_HEIGHT)
        self.setMinimumWidth(440)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.entries = {}
        self.buttons = {}
        self.compact_buttons = set()
        self.collapsed = set()
        self._flowing = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.reflow)

    def minimumSizeHint(self):
        return QSize(440,self.ROW_HEIGHT)

    def sizeHint(self):return QSize(440,self.ROW_HEIGHT)
    def iconSize(self):return QSize(self._icon_size)
    def toolButtonStyle(self):return self._button_style

    def button(self, action, compact=False):
        button = QToolButton()
        button.setProperty('readingButton',True)
        button.setDefaultAction(action)
        button.setAccessibleName(action.toolTip().split(' (')[0] or action.text())
        button.setAutoRaise(True)
        button.setIconSize(self.iconSize())
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly if compact else self.toolButtonStyle())
        if action.menu():
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.buttons[action] = button
        if compact:
            self.compact_buttons.add(button)
        return button

    def group(self, key, controls, priority=0, compact=False):
        group = QWidget()
        group.setObjectName('readingControlGroup')
        box = QHBoxLayout(group)
        box.setContentsMargins(0, 0, 8, 0)
        box.setSpacing(2)
        for control in controls:
            box.addWidget(self.button(control, compact) if isinstance(control, QAction) else control)
        self.control(key, group, priority)
        return group

    def command(self, key, action, priority=0):
        return self.control(key, self.button(action,compact=key in ('home','more')), priority)

    def control(self, key, widget, priority=0):
        self.row.addWidget(widget)
        self.entries[key]=dict(widget=widget,priority=priority,available=True)
        return widget

    def stretch(self):
        self.row.addStretch(1)

    def widgetForAction(self, action):
        return self.buttons.get(action)

    def setToolButtonStyle(self, style):
        self._button_style=style
        for button in getattr(self, 'buttons', {}).values():
            if button not in self.compact_buttons:
                button.setToolButtonStyle(style)
        if hasattr(self, 'timer'):
            self.timer.start(0)

    def available(self, key, value):
        entry = self.entries[key]
        if entry['available'] != value:
            entry['available'] = value
            if not value:
                entry['widget'].hide()
            self.timer.start(0)

    def priority(self, key, value):
        if self.entries[key]['priority'] != value:
            self.entries[key]['priority'] = value
            self.timer.start(0)

    def reflow(self):
        if self._flowing:
            return
        self._flowing = True
        try:
            search=self.entries.get('inline_search')
            if search:search['widget'].set_compact(self.width()<900)
            selected = {key for key, entry in self.entries.items() if entry['available']}
            def required():
                # Budget the actual row's padding and gaps conservatively.
                # A single layout owns every visible control; there is no
                # second native overflow layout or QWidgetAction proxy.
                return 24 + sum(max(0, self.entries[key]['widget'].sizeHint().width()) + 4 for key in selected)
            for key, entry in sorted(self.entries.items(), key=lambda pair: pair[1]['priority'], reverse=True):
                if required() <= self.width():
                    break
                if key in selected and entry['priority'] > 0:
                    selected.remove(key)
            self.collapsed = {key for key, entry in self.entries.items() if entry['available'] and key not in selected}
            labels={'zoom':'Zoom','history':'Back / Forward','rotation':'Rotate pages',
                    'bookmarks':'Bookmarks','favorites':'Favorites','ruler':'Reading ruler',
                    'auto_scroll':'Auto-scroll','split':'Split view','fullscreen':'Fullscreen','theme':'Reading theme','pane':'Focused pane'}
            hidden=[labels.get(key,key) for key in self.entries if key in self.collapsed]
            self.setToolTip('In Menu: '+', '.join(hidden) if hidden else '')
            for key, entry in self.entries.items():
                entry['widget'].setVisible(key in selected)
            self.row.invalidate()
            self.row.activate()
        finally:
            self._flowing = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow()
