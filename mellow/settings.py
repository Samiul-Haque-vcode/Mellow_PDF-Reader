"""Compact preferences; previews and section resets stay local until Save."""
from .dialogs import DismissibleDialog
from PySide6.QtCore import Qt,QRectF,Signal
from PySide6.QtGui import QKeySequence,QImage,QPainter,QColor,QFont,QPixmap
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QComboBox,QCheckBox,
    QDialogButtonBox,QSpinBox,QTabWidget,QWidget,QLabel,QKeySequenceEdit,QPushButton,
    QScrollArea,QLineEdit,QSizePolicy,QHBoxLayout)
from .theme import COLORS,normalize_theme,recolor,theme_tunings
from .shortcuts import COMMANDS,bindings,validate,FORMAT,migrate_navigation,category
from .caption import supported as caption_supported
from .autoscroll import scroll_speed
from .config import fullscreen_hide_delay


class ThemePreview(QLabel):
    """Small sample processed by the same page-color compositor as the reader."""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAccessibleName('Reading theme sample')
        self.setFixedHeight(130)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
        self.original=QImage(430,124,QImage.Format.Format_RGB32)
        self.original.fill(Qt.GlobalColor.white)
        painter=QPainter(self.original)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor('#1f4057'))
        painter.setFont(QFont('Segoe UI',12,QFont.Weight.DemiBold))
        painter.drawText(18,28,'A softer way to read')
        painter.setPen(Qt.GlobalColor.black)
        painter.setFont(QFont('Segoe UI',10))
        painter.drawText(18,53,'Comfortable pages. Clear text and diagrams.')
        painter.setFont(QFont('Cambria',13))
        painter.drawText(18,88,'E = mc²    ∫ f(x) dx')
        for index,color in enumerate(('#27827e','#bf5649','#3e69ad')):
            painter.fillRect(QRectF(314+index*26,75,18,24),QColor(color))
        painter.end()
        self.update_sample('Sepia',True)
    def update_sample(self,theme,preserve,warmth=0,contrast=0):
        self.image=recolor(self.original,theme,preserve,warmth,contrast)
        self.show_sample()
        mode='contrast adjusted' if theme in ('Dark','Black') and preserve else ('preserved' if preserve else 'toned')
        self.setToolTip(f'{theme} sample · figure colors '+mode)
    def show_sample(self):
        self.setPixmap(QPixmap.fromImage(self.image).scaled(max(1,min(self.width(),430)),130,
            Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'image'):self.show_sample()


def note(text):
    label=QLabel(text)
    label.setWordWrap(True)
    label.setProperty('role','muted')
    return label


def section(layout,title):
    heading=QLabel(title)
    heading.setProperty('role','section')
    layout.addWidget(heading)
    form=QFormLayout()
    form.setSpacing(10)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    layout.addLayout(form)
    return form


class SettingsDialog(DismissibleDialog):
    backupRequested=Signal()
    restoreRequested=Signal()
    clearHistoryRequested=Signal()
    exportFavoritesRequested=Signal()
    importFavoritesRequested=Signal()
    def __init__(self,store,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Mellow settings')
        self.resize(570,650)
        self.setMinimumSize(480,460)
        outer=QVBoxLayout(self)
        outer.setContentsMargins(20,18,20,16)
        title=QLabel('Settings')
        title.setProperty('role','section')
        outer.addWidget(title)
        self.tabs=QTabWidget()
        outer.addWidget(self.tabs,1)
        self.reset_buttons={}
        self.theme_name=normalize_theme(store.get('theme','Sepia'))
        self.tunings=theme_tunings(store.get('theme_tuning',{}))
        general,box=self.page('General')
        form=section(box,'Startup')
        self.startup=QComboBox()
        self.startup.addItems(['Continue previous session','Show Home'])
        self.startup.setCurrentIndex(0 if store.get('restore_session',True) else 1)
        form.addRow('On startup',self.startup)
        form=section(box,'History')
        self.record_history=QCheckBox('Record recently read PDFs')
        self.record_history.setChecked(not store.get('history_paused',False))
        form.addRow(self.record_history)
        self.clear_history=QPushButton('Clear reading history…')
        self.clear_history.setAutoDefault(False)
        self.clear_history.clicked.connect(self.clearHistoryRequested)
        form.addRow(self.clear_history)
        form=section(box,'Backup and restore')
        form.addRow(note('Back up saved preferences, Favorites, bookmarks and reading positions. PDFs are not included. Save preference changes first.'))
        buttons=QHBoxLayout()
        self.backup_data=QPushButton('Create app backup…')
        self.restore_data=QPushButton('Restore app backup…')
        for button in (self.backup_data,self.restore_data):
            button.setAutoDefault(False);buttons.addWidget(button)
        self.backup_data.clicked.connect(self.backupRequested)
        self.restore_data.clicked.connect(self.restoreRequested)
        form.addRow(buttons)
        form.addRow(note('Keep the backup outside Mellow’s folders. Restore replaces local data and closes Mellow; reopen it to continue.'))
        form=section(box,'Favorites only')
        self.export_favorites=QPushButton('Export Favorites…')
        self.import_favorites=QPushButton('Import Favorites…')
        buttons=QHBoxLayout()
        for button in (self.export_favorites,self.import_favorites):
            button.setAutoDefault(False);buttons.addWidget(button)
        self.export_favorites.clicked.connect(self.exportFavoritesRequested)
        self.import_favorites.clicked.connect(self.importFavoritesRequested)
        form.addRow(buttons)
        box.addStretch()
        self.section_reset(box,'general',self.reset_general)

        reading,box=self.page('Reading')
        form=section(box,'Defaults for newly opened PDFs')
        self.default_layout=QComboBox()
        for title,key in [('Continuous','continuous'),('Single Page','single'),('Two Pages','two'),('Two Pages Continuous','two_continuous')]:
            self.default_layout.addItem(title,key)
        index=self.default_layout.findData(store.get('default_layout','continuous'))
        self.default_layout.setCurrentIndex(max(0,index))
        form.addRow('Page layout',self.default_layout)
        self.fit=QComboBox();self.fit.addItems(['Fit Page','Fit Width','Actual Size'])
        self.fit.setCurrentText(store.get('default_fit','Fit Page'))
        form.addRow('Zoom',self.fit)
        form.addRow(note('Saved document preferences and reading sessions take precedence.'))
        form=section(box,'Scrolling and zoom')
        self.speed=QComboBox();self.speed.addItems(['Gentle','Normal','Fast'])
        self.speed.setCurrentText(store.get('zoom_speed','Normal'))
        form.addRow('Gesture zoom speed',self.speed)
        self.auto_scroll_speed=QSpinBox();self.auto_scroll_speed.setRange(5,200)
        self.auto_scroll_speed.setSuffix(' px/s')
        self.auto_scroll_speed.setValue(scroll_speed(store.get('auto_scroll_speed',24)))
        self.auto_scroll_speed.setAccessibleName('Auto-scroll speed')
        form.addRow('Auto-scroll speed',self.auto_scroll_speed)
        form.addRow(note('Use the toolbar Auto-scroll button. Manual input pauses scrolling.'))
        form=section(box,'Text copying')
        self.copy_format=QComboBox()
        self.copy_format.addItem('Preserve Line Breaks','preserve')
        self.copy_format.addItem('Join Paragraphs','paragraphs')
        self.copy_format.setCurrentIndex(max(0,self.copy_format.findData(store.get('copy_format','preserve'))))
        form.addRow('Default Ctrl+C format',self.copy_format)
        form.addRow(note('The two-point selection popup always offers both copy formats.'))
        form=section(box,'Reading ruler')
        self.height=QSpinBox();self.height.setRange(4,200);self.height.setSuffix(' px')
        self.height.setValue(store.get('ruler_height',28));form.addRow('Height',self.height)
        self.opacity=QSpinBox();self.opacity.setRange(1,80);self.opacity.setSuffix(' %')
        self.opacity.setValue(store.get('ruler_opacity',14));form.addRow('Opacity',self.opacity)
        box.addStretch();self.section_reset(box,'reading',self.reset_reading)

        appearance,box=self.page('Appearance')
        form=section(box,'Current theme tuning')
        self.theme=QComboBox();self.theme.addItems(COLORS);self.theme.setCurrentText(self.theme_name)
        form.addRow('Reading theme',self.theme)
        self.theme.currentTextChanged.connect(self.change_tuning_theme)
        self.warmth=QSpinBox();self.warmth.setRange(-50,50)
        self.warmth.setAccessibleName('Paper warmth');form.addRow('Paper warmth',self.warmth)
        self.contrast=QSpinBox();self.contrast.setRange(-30,30)
        self.contrast.setAccessibleName('Text contrast');form.addRow('Text contrast',self.contrast)
        self.reset_theme=QPushButton('Reset this theme');self.reset_theme.setAutoDefault(False)
        self.reset_theme.clicked.connect(self.reset_current_theme);form.addRow(self.reset_theme)
        self.preview=ThemePreview();box.addWidget(self.preview)
        self.preserve=QCheckBox('Keep figure colors');self.preserve.setChecked(store.get('preserve',True))
        box.addWidget(self.preserve)
        box.addWidget(note('Dark ink is brightened in Dark mode. Grayscale images may be tinted.'))
        self.warmth.valueChanged.connect(self.update_tuning)
        self.contrast.valueChanged.connect(self.update_tuning)
        self.preserve.toggled.connect(self.update_preview)
        self.load_tuning()
        form=section(box,'Window and toolbar')
        self.labels=QCheckBox('Show toolbar button labels');self.labels.setChecked(store.get('toolbar_labels',False));form.addRow(self.labels)
        self.caption_tabs=QCheckBox('Tabs in the Windows title bar');self.caption_tabs.setChecked(store.get('caption_tabs',True))
        self.caption_tabs.setEnabled(caption_supported());form.addRow(self.caption_tabs)
        form.addRow(note('Restart Mellow to apply the title-bar preference.'))
        form=section(box,'Fullscreen')
        self.autohide=QCheckBox('Auto-hide controls in fullscreen');self.autohide.setChecked(store.get('fullscreen_autohide',True));form.addRow(self.autohide)
        self.hide_delay=QSpinBox();self.hide_delay.setRange(200,5000);self.hide_delay.setSingleStep(100);self.hide_delay.setSuffix(' ms')
        self.hide_delay.setValue(fullscreen_hide_delay(store.get('fullscreen_hide_delay',600)))
        self.hide_delay.setAccessibleName('Fullscreen controls hide delay');self.hide_delay.setEnabled(self.autohide.isChecked())
        self.autohide.toggled.connect(self.hide_delay.setEnabled);form.addRow('Hide after',self.hide_delay)
        box.addStretch();self.section_reset(box,'appearance',self.reset_appearance)
        shortcuts=QWidget()
        box=QVBoxLayout(shortcuts)
        self.filter=QLineEdit()
        self.filter.setPlaceholderText('Find a command or category…')
        self.filter.setClearButtonEnabled(True)
        box.addWidget(self.filter)
        box.addWidget(note('Select a shortcut and press new keys. Clear it to disable. Escape stays reserved; reader selection shortcuts leave text-field editing unchanged.'))
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        content=QWidget()
        groups=QVBoxLayout(content)
        groups.setContentsMargins(8,8,8,8)
        self.shortcut_edits={}
        self.shortcut_labels={}
        self.shortcut_groups={}
        try: saved=validate(migrate_navigation(store.get('shortcuts',{})))
        except (ValueError,TypeError): saved=bindings()
        group_order=('Documents and Tabs','Navigation and Zoom','Text Selection and Copying','Quick Jump','Split Reading','Window and Fullscreen','PDF Tools')
        commands=sorted(COMMANDS.items(),key=lambda item:group_order.index(category(item[0])))
        for key,(name,group,default) in commands:
            group=category(key)
            if group not in self.shortcut_groups:
                heading=QLabel(group)
                heading.setProperty('role','section')
                groups.addWidget(heading)
                rows=QFormLayout()
                rows.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
                groups.addLayout(rows)
                self.shortcut_groups[group]=(heading,rows)
            edit=QKeySequenceEdit(QKeySequence(saved[key]))
            edit.setMaximumSequenceLength(1)
            edit.setClearButtonEnabled(True)
            edit.setAccessibleName(name+' shortcut')
            label=QLabel(name)
            label.setToolTip(group)
            self.shortcut_edits[key]=edit
            self.shortcut_labels[key]=label
            self.shortcut_groups[group][1].addRow(label,edit)
        self.no_commands=note('No commands match your search.')
        self.no_commands.hide()
        groups.addWidget(self.no_commands)
        groups.addStretch()
        scroll.setWidget(content)
        box.addWidget(scroll,1)
        self.section_reset(box,'shortcuts',self.reset_shortcuts)
        self.tabs.addTab(shortcuts,'Shortcuts')
        self.shortcuts_page=shortcuts
        self.tabs.setCurrentIndex(0)
        self.filter.textChanged.connect(self.filter_shortcuts)
        self.error=QLabel()
        self.error.setWordWrap(True)
        self.error.setProperty('role','error')
        self.error.hide()
        outer.addWidget(self.error)
        self.dirty_note=note('')
        self.dirty_note.setAccessibleName('Settings change status')
        outer.addWidget(self.dirty_note)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Save')
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName('primary')
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)
        self._baseline=self.values()
        for control in self.findChildren(QComboBox):control.currentIndexChanged.connect(self.update_dirty)
        for control in self.findChildren(QSpinBox):control.valueChanged.connect(self.update_dirty)
        for control in self.findChildren(QCheckBox):control.toggled.connect(self.update_dirty)
        for edit in self.shortcut_edits.values():edit.keySequenceChanged.connect(self.update_dirty)
        self.update_dirty()
    def page(self,title):
        content=QWidget()
        layout=QVBoxLayout(content)
        layout.setContentsMargins(16,16,16,16)
        layout.setSpacing(12)
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        self.tabs.addTab(scroll,title)
        return content,layout
    def section_reset(self,layout,key,callback):
        button=QPushButton('Reset this section')
        button.setAutoDefault(False)
        button.clicked.connect(callback)
        layout.addWidget(button,0,Qt.AlignmentFlag.AlignLeft)
        self.reset_buttons[key]=button
    def change_tuning_theme(self,name):
        self.theme_name=name
        self.load_tuning()

    def load_tuning(self,*_):
        name=self.theme_name
        for key,control in (('warmth',self.warmth),('contrast',self.contrast)):
            control.blockSignals(True)
            control.setValue(self.tunings[name][key])
            control.setEnabled(name!='Light' and not (name=='Black' and key=='warmth'))
            control.blockSignals(False)
        self.warmth.setToolTip('Black keeps pure black paper.' if name=='Black' else
            'Negative is cooler; positive is warmer. Zero keeps the original theme.')
        self.reset_theme.setEnabled(name!='Light')
        self.update_preview()
    def update_tuning(self,*_):
        self.tunings[self.theme_name]=dict(warmth=self.warmth.value(),contrast=self.contrast.value())
        self.update_preview()
    def reset_current_theme(self):
        self.tunings[self.theme_name]=dict(warmth=0,contrast=0)
        self.load_tuning()
    def update_preview(self,*_):
        self.preview.update_sample(self.theme_name,self.preserve.isChecked(),self.warmth.value(),self.contrast.value())
        self.update_dirty()
    def update_dirty(self,*_):
        if not hasattr(self,'_baseline'):return
        dirty=self.values()!=self._baseline
        self.dirty_note.setText('Unsaved changes' if dirty else '')
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(dirty)
    def reset_appearance(self):
        self.tunings=theme_tunings({})
        self.theme.setCurrentText('Sepia')
        self.load_tuning()
        self.preserve.setChecked(True)
        self.labels.setChecked(False)
        self.caption_tabs.setChecked(True)
        self.autohide.setChecked(True)
        self.hide_delay.setValue(600)
        self.update_dirty()
    def reset_general(self):
        self.startup.setCurrentIndex(0)
        self.record_history.setChecked(True)
        self.update_dirty()
    def reset_navigation(self):
        self.fit.setCurrentText('Fit Page')
        self.speed.setCurrentText('Normal')
        self.auto_scroll_speed.setValue(24)
        self.update_dirty()
    def reset_reading(self):
        self.reset_navigation()
        self.default_layout.setCurrentIndex(0)
        self.copy_format.setCurrentIndex(0)
        self.height.setValue(28)
        self.opacity.setValue(14)
        self.update_dirty()
    def filter_shortcuts(self,text):
        visible_groups=set()
        for key,(name,group,_) in COMMANDS.items():
            group=category(key)
            visible=text.strip().casefold() in (name+' '+group).casefold()
            self.shortcut_labels[key].setVisible(visible)
            self.shortcut_edits[key].setVisible(visible)
            if visible: visible_groups.add(group)
        for group,(heading,_) in self.shortcut_groups.items(): heading.setVisible(group in visible_groups)
        self.no_commands.setVisible(not visible_groups)
    def reset_shortcuts(self):
        for key,(_,_,default) in COMMANDS.items(): self.shortcut_edits[key].setKeySequence(QKeySequence(default))
        self.error.clear()
        self.error.hide()
    def shortcut_values(self):
        return {key:edit.keySequence().toString(FORMAT) for key,edit in self.shortcut_edits.items()}
    def accept(self):
        try: validate(self.shortcut_values())
        except ValueError as error:
            self.error.setText(str(error))
            self.error.show()
            self.tabs.setCurrentWidget(self.shortcuts_page)
            self.filter.clear()
            return
        super().accept()
    def values(self):
        return dict(theme=self.theme_name,theme_tuning=theme_tunings(self.tunings),default_fit=self.fit.currentText(),
                    default_layout=self.default_layout.currentData(),copy_format=self.copy_format.currentData(),
                    zoom_speed=self.speed.currentText(),restore_session=self.startup.currentIndex()==0,
                    auto_scroll_speed=self.auto_scroll_speed.value(),
                    preserve=self.preserve.isChecked(),fullscreen_autohide=self.autohide.isChecked(),
                    fullscreen_hide_delay=self.hide_delay.value(),
                    ruler_height=self.height.value(),ruler_opacity=self.opacity.value(),
                    toolbar_labels=self.labels.isChecked(),caption_tabs=self.caption_tabs.isChecked(),history_paused=not self.record_history.isChecked(),shortcuts=self.shortcut_values())
