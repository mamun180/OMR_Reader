import sys
import os
import json
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QGridLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QColorDialog, QHBoxLayout,
    QSlider, QCheckBox, QFontComboBox, QDialog, QListWidget, 
    QDialogButtonBox, QListWidgetItem, QTabWidget, QFormLayout, 
    QInputDialog, QFrame, QMessageBox, QComboBox
)
from PyQt6.QtCore import QSettings, Qt, QStandardPaths, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from ui_image_editor import ImageSettingsEditor
from theme import apply_stylesheet_and_floatation
from directory_manager import get_default_base_dir_path

class NamingOutputDialog(QDialog):
    pattern_saved = pyqtSignal(str)

    def __init__(self, template_path, student_data_path, panel_text_color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Naming and Output Patterns Setup")
        self.setMinimumWidth(800)
        self.settings = QSettings("OptiMark Pro", "OutputPatterns")
        self.defaults_settings = QSettings("OptiMark Pro", "Defaults")
        self.panel_text_color = panel_text_color

        try:
            with open(template_path, 'r') as f: self.template_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, TypeError): self.template_data = {}
        
        try:
            if student_data_path and os.path.exists(student_data_path):
                if student_data_path.lower().endswith(('.xlsx', '.xls')):
                    self.student_data = pd.read_excel(student_data_path)
                elif student_data_path.lower().endswith('.csv'):
                    self.student_data = pd.read_csv(student_data_path)
                else:
                    self.student_data = None
            else:
                self.student_data = None
        except Exception: self.student_data = None

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(QLabel("<b>Saved Patterns</b>"))
        saved_patterns_layout = QHBoxLayout()
        self.patterns_combo = QComboBox()
        self.patterns_combo.currentTextChanged.connect(self.load_pattern)
        saved_patterns_layout.addWidget(self.patterns_combo)
        self.delete_pattern_button = QPushButton("Delete"); self.delete_pattern_button.clicked.connect(self.delete_pattern)
        saved_patterns_layout.addWidget(self.delete_pattern_button)
        self.layout.addLayout(saved_patterns_layout)
        
        name_layout = QHBoxLayout(); name_layout.addWidget(QLabel("Pattern Name:"))
        self.pattern_name_edit = QLineEdit(); self.pattern_name_edit.setPlaceholderText("Enter a name for this new pattern")
        name_layout.addWidget(self.pattern_name_edit)
        self.layout.addLayout(name_layout)

        self.tab_widget = QTabWidget()
        self.excel_tab, self.rename_tab, self.ans_key_naming_tab = QWidget(), QWidget(), QWidget()
        self.tab_widget.addTab(self.excel_tab, "Excel Output")
        self.tab_widget.addTab(self.rename_tab, "Image Renaming")
        self.tab_widget.addTab(self.ans_key_naming_tab, "Answer Key Naming")
        self.layout.addWidget(self.tab_widget)

        self._create_excel_tab(); self._create_rename_tab(); self._create_ans_key_naming_tab()

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_and_accept); self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

        self.populate_all_widgets(); self.load_saved_patterns()

    def _create_excel_tab(self):
        excel_layout = QVBoxLayout(self.excel_tab)
        
        mid_layout = QHBoxLayout()
        
        filename_group = QGroupBox("Excel Filename Pattern")
        filename_main_layout = QVBoxLayout(filename_group)
        add_component_layout = QHBoxLayout()
        self.excel_component_combo = QComboBox()
        add_component_layout.addWidget(self.excel_component_combo)
        self.add_excel_filename_button = QPushButton("Add to Filename")
        self.add_excel_filename_button.clicked.connect(lambda: self.add_component_to_list(self.excel_component_combo, self.excel_filename_list))
        add_component_layout.addWidget(self.add_excel_filename_button)
        filename_main_layout.addLayout(add_component_layout)
        self.excel_filename_list = QListWidget()
        self.excel_filename_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        filename_main_layout.addWidget(self.excel_filename_list)
        filename_controls_layout = QHBoxLayout()
        self.remove_excel_filename_button = QPushButton("Remove")
        self.remove_excel_filename_button.clicked.connect(lambda: self.remove_component_from_list(self.excel_filename_list))
        filename_controls_layout.addWidget(self.remove_excel_filename_button)
        filename_controls_layout.addStretch()
        filename_main_layout.addLayout(filename_controls_layout)
        self.excel_filename_preview_label = QLabel("Preview: ")
        filename_main_layout.addWidget(self.excel_filename_preview_label)
        mid_layout.addWidget(filename_group)

        lookup_group = QGroupBox("Student Data Lookup")
        lookup_layout = QFormLayout(lookup_group)
        self.lookup_roi_combo = QComboBox()
        self.lookup_column_combo = QComboBox()
        lookup_layout.addRow("Match Scanned ROI:", self.lookup_roi_combo)
        lookup_layout.addRow("With Data Column:", self.lookup_column_combo)
        mid_layout.addWidget(lookup_group)
        
        excel_layout.addLayout(mid_layout)

        main_layout = QGridLayout()
        scan_group = QGroupBox("Scan Result Columns"); scan_layout = QVBoxLayout(scan_group); self.scan_columns_list = QListWidget(); scan_layout.addWidget(self.scan_columns_list); scan_group.setLayout(scan_layout); main_layout.addWidget(scan_group, 0, 0)
        student_group = QGroupBox("Student Data Columns"); student_layout = QVBoxLayout(student_group); self.student_columns_list = QListWidget(); student_layout.addWidget(self.student_columns_list); student_group.setLayout(student_layout); main_layout.addWidget(student_group, 1, 0)
        buttons_layout = QVBoxLayout(); buttons_layout.addStretch(); self.add_col_button = QPushButton(">>"); self.remove_col_button = QPushButton("<<"); buttons_layout.addWidget(self.add_col_button); buttons_layout.addWidget(self.remove_col_button); buttons_layout.addStretch(); main_layout.addLayout(buttons_layout, 0, 1, 2, 1)
        selected_group = QGroupBox("Selected Output Columns"); selected_layout = QVBoxLayout(selected_group); self.selected_columns_list = QListWidget(); self.selected_columns_list.setDragDropMode(QListWidget.DragDropMode.InternalMove); selected_layout.addWidget(self.selected_columns_list)
        reorder_layout = QHBoxLayout(); reorder_layout.addStretch(); self.move_up_button = QPushButton("Up"); self.move_down_button = QPushButton("Down"); reorder_layout.addWidget(self.move_up_button); reorder_layout.addWidget(self.move_down_button); selected_layout.addLayout(reorder_layout)
        selected_group.setLayout(selected_layout); main_layout.addWidget(selected_group, 0, 2, 2, 1)
        main_layout.setColumnStretch(0, 3); main_layout.setColumnStretch(1, 1); main_layout.setColumnStretch(2, 3)
        excel_layout.addLayout(main_layout)

        self.add_col_button.clicked.connect(self.add_selected_columns)
        self.remove_col_button.clicked.connect(self.remove_selected_columns)
        self.move_up_button.clicked.connect(self.move_item_up)
        self.move_down_button.clicked.connect(self.move_item_down)
        self.excel_filename_list.model().rowsMoved.connect(lambda: self.update_filename_preview(self.excel_filename_list, self.excel_filename_preview_label, ".xlsx"))
        self.excel_filename_list.model().rowsRemoved.connect(lambda: self.update_filename_preview(self.excel_filename_list, self.excel_filename_preview_label, ".xlsx"))
        self.excel_filename_list.model().rowsInserted.connect(lambda: self.update_filename_preview(self.excel_filename_list, self.excel_filename_preview_label, ".xlsx"))

    def _create_rename_tab(self):
        rename_layout = QVBoxLayout(self.rename_tab)
        self._create_generic_naming_tab(rename_layout, "Image Filename Pattern", ".ext", "rename_components")

    def _create_ans_key_naming_tab(self):
        ans_key_layout = QVBoxLayout(self.ans_key_naming_tab)
        self._create_generic_naming_tab(ans_key_layout, "Answer Key Filename Pattern", ".json", "answer_key_naming_pattern")

    def _create_generic_naming_tab(self, parent_layout, group_title, extension, setting_key):
        group = QGroupBox(group_title)
        main_layout = QVBoxLayout(group)
        selection_layout = QHBoxLayout()
        combo = QComboBox()
        selection_layout.addWidget(combo)
        add_button = QPushButton("Add"); selection_layout.addWidget(add_button)
        add_text_button = QPushButton("Add Text"); selection_layout.addWidget(add_text_button)
        main_layout.addLayout(selection_layout)
        list_widget = QListWidget()
        list_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        main_layout.addWidget(list_widget)
        remove_button = QPushButton("Remove Selected"); main_layout.addWidget(remove_button)
        preview_label = QLabel("Preview: ")
        main_layout.addWidget(preview_label)
        parent_layout.addWidget(group)
        parent_layout.addStretch()
        
        add_button.clicked.connect(lambda: self.add_component_to_list(combo, list_widget))
        add_text_button.clicked.connect(lambda: self.add_free_text_to_list(list_widget))
        remove_button.clicked.connect(lambda: self.remove_component_from_list(list_widget))
        list_widget.model().rowsMoved.connect(self.update_previews)
        list_widget.itemChanged.connect(self.update_previews)

        setattr(self, f"{setting_key}_combo", combo)
        setattr(self, f"{setting_key}_list", list_widget)
        setattr(self, f"{setting_key}_preview_label", preview_label)

    def add_selected_columns(self):
        for source_list in [self.scan_columns_list, self.student_columns_list]:
            for item in source_list.selectedItems(): self.selected_columns_list.addItem(item.text())

    def remove_selected_columns(self):
        for item in self.selected_columns_list.selectedItems(): self.selected_columns_list.takeItem(self.selected_columns_list.row(item))

    def move_item_up(self):
        row = self.selected_columns_list.currentRow()
        if row > 0:
            item = self.selected_columns_list.takeItem(row)
            self.selected_columns_list.insertItem(row - 1, item)
            self.selected_columns_list.setCurrentRow(row - 1)

    def move_item_down(self):
        row = self.selected_columns_list.currentRow()
        if row < self.selected_columns_list.count() - 1:
            item = self.selected_columns_list.takeItem(row)
            self.selected_columns_list.insertItem(row + 1, item)
            self.selected_columns_list.setCurrentRow(row + 1)

    def add_component_to_list(self, combo, list_widget):
        component = combo.currentText()
        if component and component != "<Select Component>": list_widget.addItem(component); self.update_previews()

    def add_free_text_to_list(self, list_widget):
        text, ok = QInputDialog.getText(self, "Add Free Text", "Enter static text for filename:")
        if ok and text: list_widget.addItem(f'"{text}"'); self.update_previews()

    def remove_component_from_list(self, list_widget):
        for item in list_widget.selectedItems(): list_widget.takeItem(list_widget.row(item)); self.update_previews()

    def populate_all_widgets(self):
        id_rois = [roi['name'] for roi in self.template_data.get('rois', []) if roi.get('type') in ['Identifier', 'qrcode']] if self.template_data else []
        ans_key_rois = [roi['name'] for roi in self.template_data.get('rois', []) if roi.get('subtype') == 'Answer Script Identifier'] if self.template_data else []
        student_cols_for_naming = [f"Data: {col}" for col in self.student_data.columns] if self.student_data is not None else []
        date_time_comps = ["YYYY", "MM", "DD", "hh", "mm", "ss", "year", "date"]
        
        # Populate Naming Tabs
        self.rename_components_combo.addItems(["<Select Component>"] + sorted(id_rois) + date_time_comps + sorted(student_cols_for_naming))
        self.answer_key_naming_pattern_combo.addItems(["<Select Component>"] + sorted(ans_key_rois) + date_time_comps)

        # Populate Excel Tab
        self.excel_component_combo.addItems(["<Select Component>"] + sorted(id_rois) + date_time_comps + sorted(student_cols_for_naming))
        self.scan_columns_list.addItems(['Timestamp', 'Image_Path', 'Score', 'Correct', 'Unanswered', 'Total_Questions'] + sorted(id_rois) + ["Student Answers (per question)", "Correctness Status (per question)"])
        self.student_columns_list.addItems(self.student_data.columns.tolist() if self.student_data is not None else [])
        self.lookup_roi_combo.addItems(["<Select ROI>"] + sorted(id_rois))
        self.lookup_column_combo.addItems(["<Select Column>"] + (self.student_data.columns.tolist() if self.student_data is not None else []))

    def update_previews(self):
        self.update_filename_preview(getattr(self, "rename_components_list"), getattr(self, "rename_components_preview_label"), ".ext")
        self.update_filename_preview(getattr(self, "answer_key_naming_pattern_list"), getattr(self, "answer_key_naming_pattern_preview_label"), ".json")

    def update_filename_preview(self, list_widget, label, extension):
        items = [list_widget.item(i).text() for i in range(list_widget.count())]
        preview_parts = [item.strip('"') if item.startswith('"') else f"<{item}>" for item in items]
        label.setText(f"<b>Preview:</b> {'_'.join(preview_parts)}{extension}")

    def load_saved_patterns(self):
        self.patterns_combo.blockSignals(True); self.patterns_combo.clear(); self.patterns_combo.addItem("<Create New Pattern>")
        pattern_names = self.settings.childGroups(); self.patterns_combo.addItems(sorted(pattern_names) if pattern_names else [])
        self.patterns_combo.blockSignals(False); self.load_pattern(self.patterns_combo.currentText())

    def load_pattern(self, pattern_name):
        is_new = not pattern_name or pattern_name == "<Create New Pattern>"
        self.pattern_name_edit.setText("" if is_new else pattern_name); self.pattern_name_edit.setReadOnly(not is_new)
        
        # Clear all lists
        self.rename_components_list.clear()
        self.answer_key_naming_pattern_list.clear()
        self.excel_filename_list.clear()
        self.selected_columns_list.clear()

        # Clear combos
        self.lookup_roi_combo.setCurrentIndex(0)
        self.lookup_column_combo.setCurrentIndex(0)

        if not is_new:
            self.settings.beginGroup(pattern_name)
            self.rename_components_list.addItems(self.settings.value("rename_components", [], type=list))
            self.answer_key_naming_pattern_list.addItems(self.settings.value("answer_key_naming_pattern", [], type=list))
            self.excel_filename_list.addItems(self.settings.value("excel_filename_components", [], type=list))
            self.selected_columns_list.addItems(self.settings.value("selected_columns", [], type=list))
            self.lookup_roi_combo.setCurrentText(self.settings.value("lookup_roi", ""))
            self.lookup_column_combo.setCurrentText(self.settings.value("lookup_column", ""))
            self.settings.endGroup()
            
        self.update_previews()

    def delete_pattern(self):
        pattern_name = self.patterns_combo.currentText()
        if not pattern_name or pattern_name == "<Create New Pattern>": return
        if QMessageBox.question(self, "Delete Pattern", f"Are you sure you want to delete '{pattern_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.settings.remove(pattern_name); self.load_saved_patterns()

    def save_and_accept(self):
        pattern_name = self.pattern_name_edit.text().strip()
        if not pattern_name:
            QMessageBox.warning(self, "Input Error", "Pattern name cannot be empty.")
            return
        if self.patterns_combo.findText(pattern_name) != -1 and self.patterns_combo.currentText() != pattern_name:
            QMessageBox.warning(self, "Input Error", "A pattern with this name already exists.")
            return

        self.settings.beginGroup(pattern_name)
        
        # Save Excel Output tab
        self.settings.setValue("excel_filename_components", [self.excel_filename_list.item(i).text() for i in range(self.excel_filename_list.count())])
        self.settings.setValue("selected_columns", [self.selected_columns_list.item(i).text() for i in range(self.selected_columns_list.count())])
        self.settings.setValue("lookup_roi", self.lookup_roi_combo.currentText() if self.lookup_roi_combo.currentText() != "<Select ROI>" else "")
        self.settings.setValue("lookup_column", self.lookup_column_combo.currentText() if self.lookup_column_combo.currentText() != "<Select Column>" else "")

        # Save Image Renaming tab
        self.settings.setValue("rename_components", [self.rename_components_list.item(i).text() for i in range(self.rename_components_list.count())])
        
        # Save Answer Key Naming tab
        self.settings.setValue("answer_key_naming_pattern", [self.answer_key_naming_pattern_list.item(i).text() for i in range(self.answer_key_naming_pattern_list.count())])

        self.settings.endGroup()
        self.defaults_settings.setValue("last_output_pattern", pattern_name)
        self.pattern_saved.emit(pattern_name)
        self.accept()

class SettingsPage(QWidget):
    settings_saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Default Settings")
        self.settings = QSettings("OptiMark Pro", "Defaults")
        self.output_settings = QSettings("OptiMark Pro", "OutputPatterns")
        self.selected_color = None
        self.selected_panel_text_color = None
        self.selected_header_text_color = None
        self.selected_button_color = None

        main_layout = QHBoxLayout(self)
        main_layout.addStretch()
        content_widget = QWidget()
        content_widget.setMaximumWidth(800)
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(0,0,0,0)
        main_layout.addWidget(content_widget)
        main_layout.addStretch()
        
        top_section_layout = QHBoxLayout()

        paths_group_box = QGroupBox("Default Paths")
        grid_layout = QGridLayout(paths_group_box)
        self.paths = {
            "base_directory": ("Base Data Directory:", None),
            "student_data_sheet": ("Student Data Sheet:", "Excel Files (*.xlsx *.xls);;CSV Files (*.csv)"),
            "master_template": ("Master Template:", "JSON Files (*.json)"),
        }
        self.line_edits = {}
        for i, (key, (label_text, file_filter)) in enumerate(self.paths.items()):
            label = QLabel(label_text)
            self.line_edits[key] = QLineEdit()
            self.line_edits[key].setReadOnly(True)
            browse_button = QPushButton("Browse...")
            if file_filter is None:
                browse_button.clicked.connect(lambda ch=False, k=key, cap=label_text: self.browse_folder(k, f"Select {cap}"))
            else:
                browse_button.clicked.connect(lambda ch=False, k=key, cap=label_text, f=file_filter: self.browse_file(k, f"Select {cap}", f))
            grid_layout.addWidget(label, i, 0)
            grid_layout.addWidget(self.line_edits[key], i, 1)
            grid_layout.addWidget(browse_button, i, 2)
        top_section_layout.addWidget(paths_group_box)

        naming_group_box = QGroupBox("File Naming & Output Patterns")
        naming_layout = QVBoxLayout(naming_group_box)
        
        active_pattern_layout = QHBoxLayout()
        active_pattern_layout.addWidget(QLabel("Active Pattern:"))
        self.active_pattern_combo = QComboBox()
        active_pattern_layout.addWidget(self.active_pattern_combo)
        naming_layout.addLayout(active_pattern_layout)

        btn_setup_patterns = QPushButton("Setup/Edit Naming & Output Patterns...")
        btn_setup_patterns.clicked.connect(self.open_naming_output_dialog)
        naming_layout.addWidget(btn_setup_patterns)
        self.pattern_summary_label = QLabel("Active Pattern: <None>")
        self.pattern_summary_label.setStyleSheet("font-style: italic; color: #888;")
        self.pattern_summary_label.setWordWrap(True)
        naming_layout.addWidget(self.pattern_summary_label)
        top_section_layout.addWidget(naming_group_box)
        layout.addLayout(top_section_layout)

        theme_group_box = QGroupBox("Theme")
        theme_grid_layout = QGridLayout(theme_group_box)
        theme_grid_layout.addWidget(QLabel("Font Family:"), 0, 0)
        self.font_combo = QFontComboBox()
        theme_grid_layout.addWidget(self.font_combo, 0, 1, 1, 2)
        theme_grid_layout.addWidget(QLabel("Base Font Size:"), 1, 0)
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setRange(8, 18)
        self.font_size_label = QLabel("12px")
        self.font_size_slider.valueChanged.connect(lambda v: self.font_size_label.setText(f"{v}px"))
        theme_grid_layout.addWidget(self.font_size_slider, 1, 1)
        theme_grid_layout.addWidget(self.font_size_label, 1, 2)
        self.color_label = QLabel(); self.color_label.setFixedWidth(100); self.color_label.setAutoFillBackground(True)
        btn_select_color = QPushButton("Select Theme Color..."); btn_select_color.clicked.connect(self.select_theme_color)
        theme_grid_layout.addWidget(QLabel("Theme Base Color:"), 2, 0); theme_grid_layout.addWidget(self.color_label, 2, 1); theme_grid_layout.addWidget(btn_select_color, 2, 2)
        self.panel_text_color_label = QLabel(); self.panel_text_color_label.setFixedWidth(100); self.panel_text_color_label.setAutoFillBackground(True)
        btn_select_panel_text_color = QPushButton("Select Panel Text Color..."); btn_select_panel_text_color.clicked.connect(self.select_panel_text_color)
        theme_grid_layout.addWidget(QLabel("Panel Text Color:"), 3, 0); theme_grid_layout.addWidget(self.panel_text_color_label, 3, 1); theme_grid_layout.addWidget(btn_select_panel_text_color, 3, 2)
        self.header_text_color_label = QLabel(); self.header_text_color_label.setFixedWidth(100); self.header_text_color_label.setAutoFillBackground(True)
        btn_select_header_text_color = QPushButton("Select Header Text Color..."); btn_select_header_text_color.clicked.connect(self.select_header_text_color)
        theme_grid_layout.addWidget(QLabel("Header Text Color:"), 4, 0); theme_grid_layout.addWidget(self.header_text_color_label, 4, 1); theme_grid_layout.addWidget(btn_select_header_text_color, 4, 2)
        self.button_color_label = QLabel(); self.button_color_label.setFixedWidth(100); self.button_color_label.setAutoFillBackground(True)
        btn_select_button_color = QPushButton("Select Button Color..."); btn_select_button_color.clicked.connect(self.select_button_color)
        theme_grid_layout.addWidget(QLabel("Button Color:"), 5, 0); theme_grid_layout.addWidget(self.button_color_label, 5, 1); theme_grid_layout.addWidget(btn_select_button_color, 5, 2)
        self.transparency_slider = QSlider(Qt.Orientation.Horizontal); self.transparency_slider.setRange(0, 100); self.transparency_label = QLabel("70%")
        self.transparency_slider.valueChanged.connect(lambda v: self.transparency_label.setText(f"{v}%"))
        theme_grid_layout.addWidget(QLabel("Panel Opacity:"), 6, 0); theme_grid_layout.addWidget(self.transparency_slider, 6, 1); theme_grid_layout.addWidget(self.transparency_label, 6, 2)
        theme_grid_layout.addWidget(QLabel("Button Height:"), 7, 0)
        self.button_height_slider = QSlider(Qt.Orientation.Horizontal)
        self.button_height_slider.setRange(15, 80)
        self.button_height_label = QLabel("50px")
        self.button_height_slider.valueChanged.connect(lambda v: self.button_height_label.setText(f"{v}px"))
        theme_grid_layout.addWidget(self.button_height_slider, 7, 1)
        theme_grid_layout.addWidget(self.button_height_label, 7, 2)

        self.dark_mode_checkbox = QCheckBox("Enable Dark Mode")
        theme_grid_layout.addWidget(self.dark_mode_checkbox, 8, 0, 1, 3)
        layout.addWidget(theme_group_box)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        revert_button = QPushButton("Revert to Defaults"); revert_button.clicked.connect(self.revert_settings)
        button_layout.addWidget(revert_button)
        save_button = QPushButton("Save Settings"); save_button.clicked.connect(self.accept)
        button_layout.addWidget(save_button)
        layout.addLayout(button_layout)
        layout.addStretch()
        self.load_settings()
        self.active_pattern_combo.currentTextChanged.connect(self.set_active_pattern)

    def _update_pattern_summary(self):
        pattern_name = self.settings.value("last_output_pattern")
        if not pattern_name:
            self.pattern_summary_label.setText("Active Pattern: <None>")
            return
        summary = [f"<b>Active Pattern: '{pattern_name}'</b>"]
        self.output_settings.beginGroup(pattern_name)
        def format_pattern(key, ext):
            p = self.output_settings.value(key, [], type=list)
            if not p: return f"<i>Not configured.</i>"
            parts = [item.strip('"') if item.startswith('"') else f"&lt;{item}&gt;" for item in p]
            return '_'.join(parts) + ext
        summary.append(f"• <b>Answer Key File:</b> {format_pattern('answer_key_naming_pattern', '.json')}")
        summary.append(f"• <b>Renamed Image File:</b> {format_pattern('rename_components', '.ext')}")
        summary.append(f"• <b>Excel Result File:</b> {format_pattern('excel_filename_components', '.xlsx')}")
        cols = self.output_settings.value("selected_columns", [], type=list)
        summary.append(f"• <b>Excel Columns:</b> {', '.join(cols) if cols else 'None selected'}")
        self.output_settings.endGroup()
        self.pattern_summary_label.setText("<br>".join(summary))

    def set_active_pattern(self, pattern_name):
        if not pattern_name:
            return
        self.settings.setValue("last_output_pattern", pattern_name)
        self._update_pattern_summary()

    def populate_active_pattern_combo(self):
        self.active_pattern_combo.blockSignals(True)
        
        self.active_pattern_combo.clear()
        pattern_names = self.output_settings.childGroups()
        if pattern_names:
            self.active_pattern_combo.addItems(sorted(pattern_names))
        
        current_pattern = self.settings.value("last_output_pattern", "")
        if current_pattern in pattern_names:
            self.active_pattern_combo.setCurrentText(current_pattern)
        
        self.active_pattern_combo.blockSignals(False)

    def open_naming_output_dialog(self):
        master_template_path = self.line_edits["master_template"].text()
        student_data_path = self.line_edits["student_data_sheet"].text()
        if not master_template_path or not os.path.exists(master_template_path):
            QMessageBox.warning(self, "Template Missing", "Please select a valid Master Template file first.")
            return
        
        # Retrieve panel_text_color from settings
        settings = QSettings("OptiMark Pro", "Defaults")
        panel_text_color = settings.value("panel_text_color", "#FFFFFF") # Default to white if not set

        dialog = NamingOutputDialog(master_template_path, student_data_path, panel_text_color, self)
        apply_stylesheet_and_floatation(dialog)

        dialog.exec()
        self.populate_active_pattern_combo()
        self._update_pattern_summary()

    def browse_file(self, key, caption, file_filter):
        path, _ = QFileDialog.getOpenFileName(self, caption, "", file_filter)
        if path: self.line_edits[key].setText(path)

    def browse_folder(self, key, caption):
        path = QFileDialog.getExistingDirectory(self, caption)
        if path: self.line_edits[key].setText(path)

    def select_theme_color(self):
        color = QColorDialog.getColor();
        if color.isValid(): self.selected_color = color; self.update_color_label()
    def update_color_label(self):
        if self.selected_color and self.selected_color.isValid():
            palette = self.color_label.palette(); palette.setColor(QPalette.ColorRole.Window, self.selected_color)
            self.color_label.setPalette(palette); self.color_label.setText(self.selected_color.name())
        else: self.color_label.setText("No Color"); self.color_label.setPalette(QPalette())
    def select_panel_text_color(self):
        color = QColorDialog.getColor();
        if color.isValid(): self.selected_panel_text_color = color; self.update_panel_text_color_label()
    def update_panel_text_color_label(self):
        if self.selected_panel_text_color and self.selected_panel_text_color.isValid():
            palette = self.panel_text_color_label.palette(); palette.setColor(QPalette.ColorRole.Window, self.selected_panel_text_color)
            self.panel_text_color_label.setPalette(palette); self.panel_text_color_label.setText(self.selected_panel_text_color.name())
        else: self.panel_text_color_label.setText("No Color"); self.panel_text_color_label.setPalette(QPalette())
    def select_header_text_color(self):
        color = QColorDialog.getColor();
        if color.isValid(): self.selected_header_text_color = color; self.update_header_text_color_label()
    def update_header_text_color_label(self):
        if self.selected_header_text_color and self.selected_header_text_color.isValid():
            palette = self.header_text_color_label.palette(); palette.setColor(QPalette.ColorRole.Window, self.selected_header_text_color)
            self.header_text_color_label.setPalette(palette); self.header_text_color_label.setText(self.selected_header_text_color.name())
        else: self.header_text_color_label.setText("No Color"); self.header_text_color_label.setPalette(QPalette())
    def select_button_color(self):
        color = QColorDialog.getColor();
        if color.isValid(): self.selected_button_color = color; self.update_button_color_label()
    def update_button_color_label(self):
        if self.selected_button_color and self.selected_button_color.isValid():
            palette = self.button_color_label.palette(); palette.setColor(QPalette.ColorRole.Window, self.selected_button_color)
            self.button_color_label.setPalette(palette); self.button_color_label.setText(self.selected_button_color.name())
        else: self.button_color_label.setText("No Color"); self.button_color_label.setPalette(QPalette())

    def load_settings(self):
        for key in self.paths: self.line_edits[key].setText(self.settings.value(key, ""))
        if not self.line_edits["base_directory"].text(): self.line_edits["base_directory"].setText(get_default_base_dir_path())
        self.font_combo.setCurrentText(self.settings.value("font_family", "Segoe UI"))
        font_size = self.settings.value("font_size", 12, type=int)
        self.font_size_slider.setValue(font_size); self.font_size_label.setText(f"{font_size}px")
        self.selected_color = QColor(self.settings.value("theme_color", "")) if self.settings.value("theme_color") else None; self.update_color_label()
        self.selected_panel_text_color = QColor(self.settings.value("panel_text_color", "")) if self.settings.value("panel_text_color") else None; self.update_panel_text_color_label()
        self.selected_header_text_color = QColor(self.settings.value("header_text_color", "")) if self.settings.value("header_text_color") else None; self.update_header_text_color_label()
        self.selected_button_color = QColor(self.settings.value("button_color", "")) if self.settings.value("button_color") else None; self.update_button_color_label()
        transparency = self.settings.value("theme_opacity_percent", 70, type=int)
        self.transparency_slider.setValue(transparency); self.transparency_label.setText(f"{transparency}%")
        button_height = self.settings.value("button_height", 30, type=int)
        self.button_height_slider.setValue(button_height)
        self.button_height_label.setText(f"{button_height}px")
        self.dark_mode_checkbox.setChecked(self.settings.value("dark_mode_enabled", "false", type=str).lower() == 'true')
        self.populate_active_pattern_combo()
        self._update_pattern_summary()

    def revert_settings(self):
        self.settings.clear(); self.output_settings.clear(); self.load_settings()

    def save_settings(self):
        if old_student_data_path := self.settings.value("student_data_sheet", "") != self.line_edits["student_data_sheet"].text():
            cache_file = os.path.join(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation), "student_data_cache.xlsx")
            if os.path.exists(cache_file):
                try: os.remove(cache_file)
                except OSError: pass
        for key, line_edit in self.line_edits.items(): self.settings.setValue(key, line_edit.text())
        self.settings.setValue("font_family", self.font_combo.currentFont().family())
        self.settings.setValue("font_size", self.font_size_slider.value())
        if self.selected_color and self.selected_color.isValid(): self.settings.setValue("theme_color", self.selected_color.name())
        if self.selected_panel_text_color and self.selected_panel_text_color.isValid(): self.settings.setValue("panel_text_color", self.selected_panel_text_color.name())
        if self.selected_header_text_color and self.selected_header_text_color.isValid(): self.settings.setValue("header_text_color", self.selected_header_text_color.name())
        if self.selected_button_color and self.selected_button_color.isValid(): self.settings.setValue("button_color", self.selected_button_color.name())
        self.settings.setValue("theme_opacity_percent", self.transparency_slider.value())
        self.settings.setValue("button_height", self.button_height_slider.value())
        self.settings.setValue("dark_mode_enabled", self.dark_mode_checkbox.isChecked())
        self.settings_saved.emit()

    def accept(self):
        self.save_settings()