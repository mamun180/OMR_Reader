import sys
import os
import json
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QGridLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QColorDialog, QHBoxLayout,
    QSlider, QCheckBox, QFontComboBox, QDialog, QListWidget,
    QDialogButtonBox, QListWidgetItem, QTabWidget, QFormLayout,
    QInputDialog, QFrame, QMessageBox, QComboBox, QTableWidget,
    QHeaderView, QTableWidgetItem, QStyledItemDelegate, QAbstractItemView,
    QScrollArea, QStackedWidget
)
from PyQt6.QtCore import QSettings, Qt, QStandardPaths, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from ui_image_editor import ImageSettingsEditor
from theme import apply_stylesheet_and_floatation
from directory_manager import get_default_base_dir_path
from settings_manager import save_last_path, load_last_path
from cache_manager import get_student_data, get_template_data, refresh_identifier_references

class IdentifierReferenceDialog(QDialog):
    def __init__(self, master_template_path, panel_text_color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Identifier Reference Values")
        self.setMinimumSize(600, 400)
        self.master_template_path = master_template_path
        self.panel_text_color = panel_text_color # Store panel_text_color
        self.identifier_references = {} # Stores all references: {roi_name: [{"scanned": "...", "used": "..."}, ...]}
        self.settings = QSettings("OptiMark Pro", "IdentifierReferences") # QSettings for persistence

        self.template_data = self._load_template_data()
        self.target_rois = self._get_target_identifier_rois()

        main_layout = QVBoxLayout(self)

        # ROI Selection
        roi_selection_layout = QHBoxLayout()
        roi_selection_layout.addWidget(QLabel("Select Identifier ROI:"))
        self.roi_combo = QComboBox()
        for roi in self.target_rois:
            self.roi_combo.addItem(roi['name'])
        self.roi_combo.currentIndexChanged.connect(self._load_current_roi_references)
        roi_selection_layout.addWidget(self.roi_combo)
        main_layout.addLayout(roi_selection_layout)

        # Reference Table
        self.table_widget = QTableWidget(0, 2)
        self.table_widget.setHorizontalHeaderLabels(["Scanned Value", "Used Value"])
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        main_layout.addWidget(self.table_widget)

        # Table Control Buttons
        table_buttons_layout = QHBoxLayout()
        self.add_row_button = QPushButton("Add Row")
        self.add_row_button.clicked.connect(self._add_row)
        self.remove_row_button = QPushButton("Remove Selected Row(s)")
        self.remove_row_button.clicked.connect(self._remove_rows)
        table_buttons_layout.addWidget(self.add_row_button)
        table_buttons_layout.addWidget(self.remove_row_button)
        main_layout.addLayout(table_buttons_layout)

        # Dialog Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self._save_references_and_accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        # Load initial data
        self._load_all_identifier_references()
        if self.target_rois:
            self._load_current_roi_references()
        else:
            QMessageBox.information(self, "No Identifiers", "No 'Answer Script Identifier' ROIs found in the master template.")
            self.roi_combo.setEnabled(False)
            self.add_row_button.setEnabled(False)
            self.remove_row_button.setEnabled(False)
            self.button_box.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

    def _load_template_data(self):
        if not self.master_template_path or not os.path.exists(self.master_template_path):
            return {}
        try:
            with open(self.master_template_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load master template for identifier references:\n{str(e)}")
            return {}

    def _get_target_identifier_rois(self):
        if not self.template_data:
            return []
        # Filter for Identifier ROIs with subtype "Answer Script Identifier"
        return [roi for roi in self.template_data.get('rois', [])
                if roi.get('type') == 'Identifier' and roi.get('subtype') == 'Answer Script Identifier']

    def _load_all_identifier_references(self):
        """Loads all identifier references from QSettings."""
        self.identifier_references.clear()
        self.settings.beginGroup("IdentifierMappings")
        for roi in self.target_rois:
            roi_name = roi['name']
            # QSettings stores lists of strings, so convert to list of dicts
            raw_data = self.settings.value(roi_name, [], type=list)
            parsed_data = []
            for item in raw_data:
                try:
                    scanned, used = item.split("::", 1) # Use a clear separator
                    parsed_data.append({"scanned": scanned, "used": used})
                except ValueError:
                    # Handle malformed data if any
                    pass
            self.identifier_references[roi_name] = parsed_data
        self.settings.endGroup()

    def _save_all_identifier_references(self):
        """Saves all identifier references to QSettings."""
        self.settings.beginGroup("IdentifierMappings")
        for roi_name, mappings in self.identifier_references.items():
            # Convert list of dicts to list of strings for QSettings
            string_data = [f"{m['scanned']}::{m['used']}" for m in mappings]
            self.settings.setValue(roi_name, string_data)
        self.settings.endGroup()

    def _load_current_roi_references(self):
        """Loads and displays references for the currently selected ROI."""
        current_roi_name = self.roi_combo.currentText()
        self.table_widget.setRowCount(0) # Clear existing rows

        if current_roi_name and current_roi_name in self.identifier_references:
            for mapping in self.identifier_references[current_roi_name]:
                row_position = self.table_widget.rowCount()
                self.table_widget.insertRow(row_position)
                self.table_widget.setItem(row_position, 0, QTableWidgetItem(mapping["scanned"]))
                self.table_widget.setItem(row_position, 1, QTableWidgetItem(mapping["used"]))

    def _add_row(self):
        row_position = self.table_widget.rowCount()
        self.table_widget.insertRow(row_position)
        self.table_widget.setItem(row_position, 0, QTableWidgetItem(""))
        self.table_widget.setItem(row_position, 1, QTableWidgetItem(""))
        self.table_widget.scrollToBottom()
        self.table_widget.editItem(self.table_widget.item(row_position, 0)) # Start editing the first cell

    def _remove_rows(self):
        selected_rows = sorted(list(set(index.row() for index in self.table_widget.selectedIndexes())), reverse=True)
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select one or more rows to remove.")
            return

        for row in selected_rows:
            self.table_widget.removeRow(row)

    def _save_references_and_accept(self):
        """Gathers data from the table, saves it, and closes the dialog."""
        current_roi_name = self.roi_combo.currentText()
        if not current_roi_name:
            self.accept() # Nothing to save if no ROI is selected
            return

        current_roi_mappings = []
        for row in range(self.table_widget.rowCount()):
            scanned_item = self.table_widget.item(row, 0)
            used_item = self.table_widget.item(row, 1)

            scanned_value = scanned_item.text().strip() if scanned_item else ""
            used_value = used_item.text().strip() if used_item else ""

            if scanned_value or used_value: # Only save if at least one value is provided
                current_roi_mappings.append({"scanned": scanned_value, "used": used_value})

        self.identifier_references[current_roi_name] = current_roi_mappings
        self._save_all_identifier_references()
        refresh_identifier_references() # Refresh the cache after saving
        QMessageBox.information(self, "Saved", f"Reference values for '{current_roi_name}' saved successfully.")
        self.accept()


class NamingOutputDialog(QDialog):
    pattern_saved = pyqtSignal(str)

    def __init__(self, template_path, student_data_path, panel_text_color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Naming and Output Patterns Setup")
        self.setMinimumWidth(800)
        self.settings = QSettings("OptiMark Pro", "OutputPatterns")
        self.defaults_settings = QSettings("OptiMark Pro", "Defaults")
        self.panel_text_color = panel_text_color

        # --- Load data using the new cache manager ---
        self.template_data = get_template_data(template_path)
        if self.template_data is None:
            self.template_data = {} # Fallback to empty dict
            if template_path: # Only show error if a path was actually provided
                QMessageBox.critical(self, "Template Load Error", f"Could not load the template file from:\n'{template_path}'\n\nNo valid cache was found. Please check the file path in the settings.")

        self.student_data = get_student_data(student_data_path)
        if self.student_data is None and student_data_path:
            QMessageBox.critical(self, "Student Data Load Error", f"Could not load the student data file from:\n'{student_data_path}'\n\nNo valid cache was found. Please check the file path and ensure the file is a valid Excel/CSV.")


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
        self.csv_tab, self.rename_tab, self.ans_key_naming_tab = QWidget(), QWidget(), QWidget()
        self.tab_widget.addTab(self.csv_tab, "CSV Output")
        self.tab_widget.addTab(self.rename_tab, "Image Renaming")
        self.tab_widget.addTab(self.ans_key_naming_tab, "Answer Key Naming")
        self.layout.addWidget(self.tab_widget)

        self._create_csv_tab(); self._create_rename_tab(); self._create_ans_key_naming_tab()

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_and_accept); self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

        self.populate_all_widgets(); self.load_saved_patterns()

    def _create_csv_tab(self):
        csv_layout = QVBoxLayout(self.csv_tab)

        mid_layout = QHBoxLayout()

        filename_group = QGroupBox("CSV Filename Pattern")
        filename_main_layout = QVBoxLayout(filename_group)
        add_component_layout = QHBoxLayout()
        self.csv_component_combo = QComboBox()
        add_component_layout.addWidget(self.csv_component_combo)
        self.add_csv_filename_button = QPushButton("Add to Filename")
        self.add_csv_filename_button.clicked.connect(lambda: self.add_component_to_list(self.csv_component_combo, self.csv_filename_list))
        add_component_layout.addWidget(self.add_csv_filename_button)
        filename_main_layout.addLayout(add_component_layout)
        self.csv_filename_list = QListWidget()
        self.csv_filename_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        filename_main_layout.addWidget(self.csv_filename_list)
        filename_controls_layout = QHBoxLayout()
        self.remove_csv_filename_button = QPushButton("Remove")
        self.remove_csv_filename_button.clicked.connect(lambda: self.remove_component_from_list(self.csv_filename_list))
        filename_controls_layout.addWidget(self.remove_csv_filename_button)
        filename_controls_layout.addStretch()
        filename_main_layout.addLayout(filename_controls_layout)
        self.csv_filename_preview_label = QLabel("Preview: ")
        filename_main_layout.addWidget(self.csv_filename_preview_label)
        mid_layout.addWidget(filename_group)

        lookup_group = QGroupBox("Student Data Lookup")
        lookup_layout = QFormLayout(lookup_group)
        self.lookup_roi_combo = QComboBox()
        self.lookup_column_combo = QComboBox()
        lookup_layout.addRow("Match Scanned ROI:", self.lookup_roi_combo)
        lookup_layout.addRow("With Data Column:", self.lookup_column_combo)
        mid_layout.addWidget(lookup_group)

        csv_layout.addLayout(mid_layout)

        main_layout = QGridLayout()
        scan_group = QGroupBox("Scan Result Columns"); scan_layout = QVBoxLayout(scan_group); self.scan_columns_list = QListWidget(); scan_layout.addWidget(self.scan_columns_list); scan_group.setLayout(scan_layout); main_layout.addWidget(scan_group, 0, 0)
        student_group = QGroupBox("Student Data Columns"); student_layout = QVBoxLayout(student_group); self.student_columns_list = QListWidget(); student_layout.addWidget(self.student_columns_list); student_group.setLayout(student_layout); main_layout.addWidget(student_group, 1, 0)
        buttons_layout = QVBoxLayout(); buttons_layout.addStretch(); self.add_col_button = QPushButton(">>"); self.remove_col_button = QPushButton("<<"); buttons_layout.addWidget(self.add_col_button); buttons_layout.addWidget(self.remove_col_button); buttons_layout.addStretch(); main_layout.addLayout(buttons_layout, 0, 1, 2, 1)
        selected_group = QGroupBox("Selected Output Columns"); selected_layout = QVBoxLayout(selected_group); self.selected_columns_list = QListWidget(); self.selected_columns_list.setDragDropMode(QListWidget.DragDropMode.InternalMove); selected_layout.addWidget(self.selected_columns_list)
        reorder_layout = QHBoxLayout(); reorder_layout.addStretch(); self.move_up_button = QPushButton("Up"); self.move_down_button = QPushButton("Down"); reorder_layout.addWidget(self.move_up_button); reorder_layout.addWidget(self.move_down_button); selected_layout.addLayout(reorder_layout)
        selected_group.setLayout(selected_layout); main_layout.addWidget(selected_group, 0, 2, 2, 1)
        main_layout.setColumnStretch(0, 3); main_layout.setColumnStretch(1, 1); main_layout.setColumnStretch(2, 3)
        csv_layout.addLayout(main_layout)

        self.add_col_button.clicked.connect(self.add_selected_columns)
        self.remove_col_button.clicked.connect(self.remove_selected_columns)
        self.move_up_button.clicked.connect(self.move_item_up)
        self.move_down_button.clicked.connect(self.move_item_down)
        self.csv_filename_list.model().rowsMoved.connect(lambda: self.update_filename_preview(self.csv_filename_list, self.csv_filename_preview_label, ".csv"))
        self.csv_filename_list.model().rowsRemoved.connect(lambda: self.update_filename_preview(self.csv_filename_list, self.csv_filename_preview_label, ".csv"))
        self.csv_filename_list.model().rowsInserted.connect(lambda: self.update_filename_preview(self.csv_filename_list, self.csv_filename_preview_label, ".csv"))

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

        # Populate CSV Tab
        self.csv_component_combo.addItems(["<Select Component>"] + sorted(id_rois) + date_time_comps + sorted(student_cols_for_naming))
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
        self.csv_filename_list.clear()
        self.selected_columns_list.clear()

        # Clear combos
        self.lookup_roi_combo.setCurrentIndex(0)
        self.lookup_column_combo.setCurrentIndex(0)

        if not is_new:
            self.settings.beginGroup(pattern_name)
            self.rename_components_list.addItems(self.settings.value("rename_components", [], type=list))
            self.answer_key_naming_pattern_list.addItems(self.settings.value("answer_key_naming_pattern", [], type=list))
            self.csv_filename_list.addItems(self.settings.value("csv_filename_components", [], type=list))
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

        # Save CSV Output tab
        self.settings.setValue("csv_filename_components", [self.csv_filename_list.item(i).text() for i in range(self.csv_filename_list.count())])
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

class AdvancedMatchingDialog(QDialog):
    matching_pattern_saved = pyqtSignal()

    def __init__(self, template_path, student_data_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Student Matching Setup")
        self.setMinimumSize(1000, 700)
        self.settings = QSettings("OptiMark Pro", "AdvancedMatchingPatterns")
        self.parent_settings = QSettings("OptiMark Pro", "Defaults") # To get active rule

        self.template_data = get_template_data(template_path)
        self.student_data_columns = list(get_student_data(student_data_path).columns) if get_student_data(student_data_path) is not None else []
        self.omr_identifiers = [roi['name'] for roi in self.template_data.get('rois', []) if roi.get('type') == 'Identifier'] if self.template_data else []

        outer_layout = QVBoxLayout(self)

        # --- Pattern Management (Stays at the top) ---
        pattern_management_group = QGroupBox("Matching Pattern Management")
        pattern_layout = QFormLayout(pattern_management_group)
        self.pattern_name_edit = QLineEdit()
        pattern_layout.addRow("Pattern Name:", self.pattern_name_edit)
        pattern_selection_layout = QHBoxLayout()
        self.pattern_list_combo = QComboBox()
        self.pattern_list_combo.currentTextChanged.connect(self._load_selected_pattern)
        self.save_pattern_btn = QPushButton("Save Current Pattern")
        self.save_pattern_btn.clicked.connect(self._save_current_pattern)
        self.delete_pattern_btn = QPushButton("Delete Selected Pattern")
        self.delete_pattern_btn.clicked.connect(self._delete_selected_pattern)
        pattern_selection_layout.addWidget(self.pattern_list_combo)
        pattern_selection_layout.addWidget(self.save_pattern_btn)
        pattern_selection_layout.addWidget(self.delete_pattern_btn)
        pattern_layout.addRow("Manage Existing Patterns:", pattern_selection_layout)
        outer_layout.addWidget(pattern_management_group)

        # --- Configuration Tabs ---
        config_tabs = QTabWidget()
        outer_layout.addWidget(config_tabs)

        # --- Tab 1: Primary and Secondary Matching ---
        matching_tab = QWidget()
        matching_layout = QFormLayout(matching_tab)

        # Primary Match Key
        self.primary_roi_combo = QComboBox()
        self.primary_roi_combo.addItems(["<Select OMR Identifier>"] + sorted(self.omr_identifiers))
        self.primary_excel_col_combo = QComboBox()
        self.primary_excel_col_combo.addItems(["<Select Excel Column>"] + sorted(self.student_data_columns))
        primary_layout = QHBoxLayout()
        primary_layout.addWidget(self.primary_roi_combo)
        primary_layout.addWidget(self.primary_excel_col_combo)
        matching_layout.addRow("<b>Primary Match Key (ROI -> Excel):</b>", primary_layout)

        # Secondary Matching Enable
        self.enable_secondary_checkbox = QCheckBox("Enable Secondary Matching (if primary match fails)")
        matching_layout.addRow(self.enable_secondary_checkbox)

        # Secondary Match Identifiers
        secondary_identifiers_group = QGroupBox("Secondary Match Identifiers (ALL must match)")
        secondary_group_layout = QVBoxLayout(secondary_identifiers_group)
        self.secondary_match_table = QTableWidget(0, 2)
        self.secondary_match_table.setHorizontalHeaderLabels(["OMR Identifier", "Excel Column"])
        self.secondary_match_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.secondary_match_table.horizontalHeader().setFixedHeight(40) # Set fixed height
        secondary_group_layout.addWidget(self.secondary_match_table)
        secondary_btns_layout = QHBoxLayout()
        self.add_secondary_btn = QPushButton("Add Secondary")
        self.add_secondary_btn.clicked.connect(self._add_secondary_row)
        self.remove_secondary_btn = QPushButton("Remove Selected")
        self.remove_secondary_btn.clicked.connect(self._remove_selected_secondary)
        secondary_btns_layout.addWidget(self.add_secondary_btn)
        secondary_btns_layout.addWidget(self.remove_secondary_btn)
        secondary_group_layout.addLayout(secondary_btns_layout)
        matching_layout.addRow(secondary_identifiers_group)

        config_tabs.addTab(matching_tab, "Matching Keys")

        # --- Tab 2: Display Columns for Multiple Matches ---
        display_tab = QWidget()
        display_layout = QVBoxLayout(display_tab)
        display_cols_group = QGroupBox("Columns from Student Data to Display When Multiple Matches are Found")
        display_cols_layout = QVBoxLayout(display_cols_group)
        self.display_columns_list = QListWidget()
        display_cols_layout.addWidget(self.display_columns_list)
        display_btns_layout = QHBoxLayout()
        self.add_display_col_btn = QPushButton("Add Column")
        self.add_display_col_btn.clicked.connect(self._add_display_column)
        self.remove_display_col_btn = QPushButton("Remove Selected Column")
        self.remove_display_col_btn.clicked.connect(self._remove_selected_display_column)
        display_btns_layout.addWidget(self.add_display_col_btn)
        display_btns_layout.addWidget(self.remove_display_col_btn)
        display_cols_layout.addLayout(display_btns_layout)
        display_layout.addWidget(display_cols_group)
        config_tabs.addTab(display_tab, "Multi-Match Display")

        # --- Tab 3: Dependent Mappings ---
        dependent_tab = QWidget()
        dependent_layout = QVBoxLayout(dependent_tab)
        self.dependent_mappings_group = QGroupBox("Dependent Identifier Mappings (e.g., 'If Class is 9, Then Section must be A')")
        dependent_group_layout = QVBoxLayout(self.dependent_mappings_group)
        self.dependent_mappings_table = QTableWidget(0, 5)
        self.dependent_mappings_table.setHorizontalHeaderLabels(["If This Identifier...", "...Has This Value", "And This Identifier...", "...Has This Value", "Then Set It To This Value"])
        self.dependent_mappings_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.dependent_mappings_table.horizontalHeader().setFixedHeight(40) # Set fixed height
        dependent_group_layout.addWidget(self.dependent_mappings_table)
        dependent_btns_layout = QHBoxLayout()
        self.add_dependency_btn = QPushButton("Add Dependency Rule")
        self.remove_dependency_btn = QPushButton("Remove Selected Rule")
        dependent_btns_layout.addWidget(self.add_dependency_btn)
        dependent_btns_layout.addWidget(self.remove_dependency_btn)
        dependent_group_layout.addLayout(dependent_btns_layout)
        dependent_layout.addWidget(self.dependent_mappings_group)
        config_tabs.addTab(dependent_tab, "Conditional Rules")

        # --- Dialog Buttons (at the bottom, outside tabs) ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Close)
        self.button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply_and_save_active)
        self.button_box.rejected.connect(self.reject)
        outer_layout.addWidget(self.button_box)

        # Initialize
        self._load_all_patterns()
        self._load_active_pattern_settings()

        # Connect signals for dirty checking
        self.primary_roi_combo.currentIndexChanged.connect(self._set_dirty)
        self.primary_excel_col_combo.currentIndexChanged.connect(self._set_dirty)
        self.enable_secondary_checkbox.stateChanged.connect(self._set_dirty)
        self.secondary_match_table.itemChanged.connect(self._set_dirty)
        self.display_columns_list.itemChanged.connect(self._set_dirty)
        self.pattern_name_edit.textChanged.connect(self._set_dirty)
        self.add_dependency_btn.clicked.connect(self._add_dependency_row)
        self.remove_dependency_btn.clicked.connect(self._remove_selected_dependency)
        self.dependent_mappings_table.itemChanged.connect(self._set_dirty)

        self.is_dirty = False
        self._set_clean()


    def _load_all_patterns(self):
        self.pattern_list_combo.blockSignals(True)
        self.pattern_list_combo.clear()
        self.pattern_list_combo.addItem("<Create New Pattern>")
        pattern_names = self.settings.childGroups()
        if pattern_names:
            self.pattern_list_combo.addItems(sorted(pattern_names))
        self.pattern_list_combo.blockSignals(False)

    def _load_selected_pattern(self, pattern_name):
        if pattern_name == "<Create New Pattern>" or not pattern_name:
            self._clear_form()
            self.pattern_name_edit.setText("")
            self.pattern_name_edit.setReadOnly(False)
            return

        self.pattern_name_edit.setText(pattern_name)
        self.pattern_name_edit.setReadOnly(True) # Existing patterns are read-only for name

        self.settings.beginGroup(pattern_name)
        self.primary_roi_combo.setCurrentText(self.settings.value("primary_roi", ""))
        self.primary_excel_col_combo.setCurrentText(self.settings.value("primary_excel_col", ""))
        self.enable_secondary_checkbox.setChecked(self.settings.value("enable_secondary", "false", type=str).lower() == 'true')

        # Load secondary match identifiers
        self.secondary_match_table.setRowCount(0)
        secondary_idents = self.settings.value("secondary_match_identifiers", [], type=list)
        for i, item_str in enumerate(secondary_idents):
            try:
                roi, col = item_str.split("::")
                self._add_secondary_row_with_data(roi, col)
            except ValueError:
                pass # Malformed data

        # Load display columns
        self.display_columns_list.clear()
        display_cols = self.settings.value("display_columns", [], type=list)
        self.display_columns_list.addItems(display_cols)

        # Load dependent mappings
        self.dependent_mappings_table.setRowCount(0)
        dependent_mappings_raw = self.settings.value("dependent_mappings", [], type=list)
        for item_str in dependent_mappings_raw:
            try:
                # Update to unpack five values
                if_ident, is_value, then_ident, from_value, to_value = item_str.split("::", 4)
                self._add_dependency_row_with_data(if_ident, is_value, then_ident, from_value, to_value)
            except ValueError:
                # Handle old 4-part format for backward compatibility if needed, or just skip
                pass

        self.settings.endGroup()
        self._set_clean()

    def _save_current_pattern(self):
        pattern_name = self.pattern_name_edit.text().strip()
        if not pattern_name or pattern_name == "<Create New Pattern>":
            QMessageBox.warning(self, "Input Error", "Please enter a valid pattern name.")
            return

        if self.pattern_list_combo.findText(pattern_name) == -1: # It's a new pattern
            reply = QMessageBox.question(self, "New Pattern", f"A new pattern '{pattern_name}' will be created. Do you want to save and set it as active?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Yes:
                self._save_pattern_data(pattern_name)
                self.parent_settings.setValue("active_matching_pattern", pattern_name)
                QMessageBox.information(self, "Pattern Saved", f"Pattern '{pattern_name}' saved and set as active.")
                self.matching_pattern_saved.emit()
                self.accept() # Close the dialog
            else: # No
                self._save_pattern_data(pattern_name)
                QMessageBox.information(self, "Pattern Saved", f"Pattern '{pattern_name}' saved (not set as active).")
        else: # Existing pattern, just save
            self._save_pattern_data(pattern_name)
            QMessageBox.information(self, "Pattern Saved", f"Pattern '{pattern_name}' updated.")

        self._load_all_patterns() # Refresh list
        self.pattern_list_combo.setCurrentText(pattern_name)
        self._set_clean()

    def _delete_selected_pattern(self):
        pattern_name = self.pattern_list_combo.currentText()
        if pattern_name == "<Create New Pattern>" or not pattern_name:
            QMessageBox.warning(self, "Selection Error", "Please select a pattern to delete.")
            return
        if QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete the pattern '{pattern_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.settings.remove(pattern_name)
            if self.parent_settings.value("active_matching_pattern") == pattern_name:
                self.parent_settings.remove("active_matching_pattern")
                self.matching_pattern_saved.emit() # Signal change in active pattern
            QMessageBox.information(self, "Pattern Deleted", f"Pattern '{pattern_name}' has been deleted.")
            self._load_all_patterns()
            self._clear_form() # Clear UI after deleting

    def _save_pattern_data(self, pattern_name):
        self.settings.beginGroup(pattern_name)
        self.settings.setValue("primary_roi", self.primary_roi_combo.currentText())
        self.settings.setValue("primary_excel_col", self.primary_excel_col_combo.currentText())
        self.settings.setValue("enable_secondary", self.enable_secondary_checkbox.isChecked())

        secondary_idents = []
        for row in range(self.secondary_match_table.rowCount()):
            omr_item = self.secondary_match_table.cellWidget(row, 0).currentText()
            excel_item = self.secondary_match_table.cellWidget(row, 1).currentText()
            if omr_item != "<Select OMR Identifier>" and excel_item != "<Select Excel Column>":
                secondary_idents.append(f"{omr_item}::{excel_item}")
        self.settings.setValue("secondary_match_identifiers", secondary_idents)

        display_cols = [self.display_columns_list.item(i).text() for i in range(self.display_columns_list.count())]
        self.settings.setValue("display_columns", display_cols)

        # Save dependent mappings
        dependent_mappings = []
        for row in range(self.dependent_mappings_table.rowCount()):
            if_ident_combo = self.dependent_mappings_table.cellWidget(row, 0)
            is_value_item = self.dependent_mappings_table.item(row, 1)
            then_ident_combo = self.dependent_mappings_table.cellWidget(row, 2)
            from_value_item = self.dependent_mappings_table.item(row, 3)
            to_value_item = self.dependent_mappings_table.item(row, 4)

            if if_ident_combo and is_value_item and then_ident_combo and from_value_item and to_value_item:
                if_ident = if_ident_combo.currentText()
                is_value = is_value_item.text()
                then_ident = then_ident_combo.currentText()
                from_value = from_value_item.text()
                to_value = to_value_item.text()

                if if_ident != "<Select Identifier>" and then_ident != "<Select Identifier>" and is_value:
                    dependent_mappings.append(f"{if_ident}::{is_value}::{then_ident}::{from_value}::{to_value}")
        self.settings.setValue("dependent_mappings", dependent_mappings)

        self.settings.endGroup()

    def _add_secondary_row(self):
        row_position = self.secondary_match_table.rowCount()
        self.secondary_match_table.insertRow(row_position)

        roi_combo = QComboBox()
        roi_combo.addItems(["<Select OMR Identifier>"] + sorted(self.omr_identifiers))
        excel_combo = QComboBox()
        excel_combo.addItems(["<Select Excel Column>"] + sorted(self.student_data_columns))

        self.secondary_match_table.setCellWidget(row_position, 0, roi_combo)
        self.secondary_match_table.setCellWidget(row_position, 1, excel_combo)

        roi_combo.currentIndexChanged.connect(self._set_dirty)
        excel_combo.currentIndexChanged.connect(self._set_dirty)
        self._set_dirty()

    def _add_secondary_row_with_data(self, omr_roi, excel_col):
        row_position = self.secondary_match_table.rowCount()
        self.secondary_match_table.insertRow(row_position)

        roi_combo = QComboBox()
        roi_combo.addItems(["<Select OMR Identifier>"] + sorted(self.omr_identifiers))
        roi_combo.setCurrentText(omr_roi)
        excel_combo = QComboBox()
        excel_combo.addItems(["<Select Excel Column>"] + sorted(self.student_data_columns))
        excel_combo.setCurrentText(excel_col)

        self.secondary_match_table.setCellWidget(row_position, 0, roi_combo)
        self.secondary_match_table.setCellWidget(row_position, 1, excel_combo)

        roi_combo.currentIndexChanged.connect(self._set_dirty)
        excel_combo.currentIndexChanged.connect(self._set_dirty)

    def _remove_selected_secondary(self):
        selected_rows = sorted(list(set(index.row() for index in self.secondary_match_table.selectedIndexes())), reverse=True)
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select one or more rows to remove.")
            return
        for row in selected_rows:
            self.secondary_match_table.removeRow(row)
        self._set_dirty()

    def _add_display_column(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Column to Display")
        dialog_layout = QVBoxLayout(dialog)

        combo = QComboBox()
        combo.addItems(["<Select Column>"] + sorted(self.student_data_columns))
        dialog_layout.addWidget(combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        dialog_layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_col = combo.currentText()
            if selected_col != "<Select Column>" and self.display_columns_list.findItems(selected_col, Qt.MatchFlag.MatchExactly) == []:
                self.display_columns_list.addItem(selected_col)
                self._set_dirty()

    def _remove_selected_display_column(self):
        for item in self.display_columns_list.selectedItems():
            self.display_columns_list.takeItem(self.display_columns_list.row(item))
        self._set_dirty()

    def _clear_form(self):
        self.primary_roi_combo.setCurrentIndex(0)
        self.primary_excel_col_combo.setCurrentIndex(0)
        self.enable_secondary_checkbox.setChecked(False)
        self.secondary_match_table.setRowCount(0)
        self.display_columns_list.clear()
        self.dependent_mappings_table.setRowCount(0)
        self._set_clean()

    def _load_active_pattern_settings(self):
        active_pattern_name = self.parent_settings.value("active_matching_pattern", "")
        if active_pattern_name and self.pattern_list_combo.findText(active_pattern_name) != -1:
            self.pattern_list_combo.setCurrentText(active_pattern_name)
        else:
            # If no active pattern or it's gone, default to create new
            self.pattern_list_combo.setCurrentIndex(0)
            self._clear_form()

    def _apply_and_save_active(self):
        pattern_name = self.pattern_name_edit.text().strip()
        if not pattern_name:
            QMessageBox.warning(self, "Input Error", "Please enter a pattern name before applying.")
            return

        # Save the current pattern
        self._save_pattern_data(pattern_name)

        # Set it as the active pattern in the Defaults settings
        self.parent_settings.setValue("active_matching_pattern", pattern_name)
        QMessageBox.information(self, "Pattern Applied", f"Pattern '{pattern_name}' saved and set as active.")
        self.matching_pattern_saved.emit() # Signal to SettingsPage
        self.accept()

    def _set_dirty(self):
        if not self.is_dirty:
            self.is_dirty = True
        self.button_box.button(QDialogButtonBox.StandardButton.Apply).setEnabled(True)

    def _set_clean(self):
        self.is_dirty = False
        self.button_box.button(QDialogButtonBox.StandardButton.Apply).setEnabled(False)

    def _add_dependency_row(self):
        row_position = self.dependent_mappings_table.rowCount()
        self.dependent_mappings_table.insertRow(row_position)

        # Columns with ComboBoxes
        if_combo = QComboBox(); if_combo.addItems(["<Select Identifier>"] + sorted(self.omr_identifiers))
        then_combo = QComboBox(); then_combo.addItems(["<Select Identifier>"] + sorted(self.omr_identifiers))

        self.dependent_mappings_table.setCellWidget(row_position, 0, if_combo)
        self.dependent_mappings_table.setCellWidget(row_position, 2, then_combo)

        # Add empty items for the line edit columns
        self.dependent_mappings_table.setItem(row_position, 1, QTableWidgetItem(""))
        self.dependent_mappings_table.setItem(row_position, 3, QTableWidgetItem(""))
        self.dependent_mappings_table.setItem(row_position, 4, QTableWidgetItem(""))

        # Connect signals for dirty checking
        if_combo.currentIndexChanged.connect(self._set_dirty)
        then_combo.currentIndexChanged.connect(self._set_dirty)

        self._set_dirty()

    def _add_dependency_row_with_data(self, if_ident, is_value, then_ident, from_value, to_value):
        row_position = self.dependent_mappings_table.rowCount()
        self.dependent_mappings_table.insertRow(row_position)

        # If Identifier
        if_combo = QComboBox(); if_combo.addItems(["<Select Identifier>"] + sorted(self.omr_identifiers)); if_combo.setCurrentText(if_ident)
        self.dependent_mappings_table.setCellWidget(row_position, 0, if_combo)

        # Is Value
        self.dependent_mappings_table.setItem(row_position, 1, QTableWidgetItem(is_value))

        # And Then Identifier
        then_combo = QComboBox(); then_combo.addItems(["<Select Identifier>"] + sorted(self.omr_identifiers)); then_combo.setCurrentText(then_ident)
        self.dependent_mappings_table.setCellWidget(row_position, 2, then_combo)

        # Has Value
        self.dependent_mappings_table.setItem(row_position, 3, QTableWidgetItem(from_value))

        # To Value
        self.dependent_mappings_table.setItem(row_position, 4, QTableWidgetItem(to_value))

        # Connect signals
        if_combo.currentIndexChanged.connect(self._set_dirty)
        then_combo.currentIndexChanged.connect(self._set_dirty)

    def _remove_selected_dependency(self):
        selected_rows = sorted(list(set(index.row() for index in self.dependent_mappings_table.selectedIndexes())), reverse=True)
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select one or more rows to remove.")
            return
        for row in selected_rows:
            self.dependent_mappings_table.removeRow(row)
        self._set_dirty()


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

        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # --- Sidebar ---
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(190)
        self.sidebar.setSpacing(2)
        for label in [
            "  1.  File Paths",
            "  2.  Output & Naming",
            "  3.  Student Matching",
            "  4.  Identifier References",
            "  5.  Cloud Export",
            "  6.  Appearance",
        ]:
            self.sidebar.addItem(label)
        self.sidebar.setCurrentRow(0)
        self.sidebar.currentRowChanged.connect(self._on_sidebar_changed)
        outer_layout.addWidget(self.sidebar)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        outer_layout.addWidget(sep)

        # --- Right side: panels + shared button bar ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(15, 10, 15, 10)

        self.settings_stack = QStackedWidget()
        right_layout.addWidget(self.settings_stack)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        revert_button = QPushButton("Revert to Defaults")
        revert_button.clicked.connect(self.revert_settings)
        button_layout.addWidget(revert_button)
        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self.accept)
        self.save_button.setEnabled(False)
        button_layout.addWidget(self.save_button)
        self.clear_cache_button = QPushButton("Clear Cache")
        self.clear_cache_button.clicked.connect(self._on_clear_cache_clicked)
        button_layout.addWidget(self.clear_cache_button)
        right_layout.addLayout(button_layout)

        outer_layout.addWidget(right_widget)

        # Build panels (order must match sidebar items 0-5)
        self._build_panel_paths()
        self._build_panel_output()
        self._build_panel_matching()
        self._build_panel_id_refs()
        self._build_panel_export()
        self._build_panel_appearance()

        self.is_dirty = False
        self.load_settings()
        self.active_pattern_combo.currentTextChanged.connect(self.set_active_pattern)

        self.font_combo.currentFontChanged.connect(self._set_dirty)
        self.font_size_slider.valueChanged.connect(self._set_dirty)
        self.transparency_slider.valueChanged.connect(self._set_dirty)
        self.button_height_slider.valueChanged.connect(self._set_dirty)
        self.dark_mode_checkbox.stateChanged.connect(self._set_dirty)
        self.active_pattern_combo.currentTextChanged.connect(self._set_dirty)

    # ------------------------------------------------------------------
    # Sidebar navigation
    # ------------------------------------------------------------------

    def _on_sidebar_changed(self, index):
        self.settings_stack.setCurrentIndex(index)

    # ------------------------------------------------------------------
    # Panel builders
    # ------------------------------------------------------------------

    def _build_panel_paths(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        hint = QLabel("<b>Start here.</b>  Set all file and folder locations first — Output and Matching panels depend on these paths.")
        hint.setWordWrap(True)
        hint.setStyleSheet("padding: 8px; border-left: 3px solid #4a90d9; margin-bottom: 4px;")
        layout.addWidget(hint)

        paths_group = QGroupBox("File and Folder Locations")
        grid = QGridLayout(paths_group)
        grid.setSpacing(8)

        self.paths = {
            "base_directory":           ("Base Data Directory:",  None),
            "scanned_images_directory": ("Scanned Images Folder:", None),
            "student_data_sheet":       ("Student Data Sheet:",    "Excel Files (*.xlsx *.xls);;CSV Files (*.csv)"),
            "master_template":          ("Master Template:",       "JSON Files (*.json)"),
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
            grid.addWidget(label, i, 0)
            grid.addWidget(self.line_edits[key], i, 1)
            grid.addWidget(browse_button, i, 2)

        layout.addWidget(paths_group)
        layout.addStretch()
        scroll.setWidget(panel)
        self.settings_stack.addWidget(scroll)

    def _build_panel_output(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        hint = QLabel("Configure how result CSV files are named, which columns they contain, and how scanned images are renamed."
                      "<br><i>Requires Master Template and Student Data Sheet to be set first (panel 1).</i>")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        naming_group = QGroupBox("Naming & Output Patterns")
        naming_layout = QVBoxLayout(naming_group)

        active_layout = QHBoxLayout()
        active_layout.addWidget(QLabel("Active Pattern:"))
        self.active_pattern_combo = QComboBox()
        active_layout.addWidget(self.active_pattern_combo)
        naming_layout.addLayout(active_layout)

        btn_setup = QPushButton("Setup / Edit Naming & Output Patterns...")
        btn_setup.clicked.connect(self.open_naming_output_dialog)
        naming_layout.addWidget(btn_setup)

        self.pattern_summary_label = QLabel("Active Pattern: <None>")
        self.pattern_summary_label.setStyleSheet("font-style: italic; color: #888;")
        self.pattern_summary_label.setWordWrap(True)
        naming_layout.addWidget(self.pattern_summary_label)

        layout.addWidget(naming_group)
        layout.addStretch()
        scroll.setWidget(panel)
        self.settings_stack.addWidget(scroll)

    def _build_panel_matching(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        hint = QLabel("Define how scanned student identifiers (e.g., Roll Number) are matched against your Student Data Sheet."
                      "<br><i>Requires Master Template and Student Data Sheet to be set first (panel 1).</i>")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        matching_group = QGroupBox("Advanced Student Matching Rules")
        matching_layout = QVBoxLayout(matching_group)

        self.active_matching_label = QLabel("Active Rule: <i>Not configured</i>")
        self.active_matching_label.setWordWrap(True)
        matching_layout.addWidget(self.active_matching_label)

        self.btn_advanced_matching = QPushButton("Setup Advanced Matching Rules...")
        self.btn_advanced_matching.clicked.connect(self.open_advanced_matching_dialog)
        matching_layout.addWidget(self.btn_advanced_matching)

        layout.addWidget(matching_group)
        layout.addStretch()
        scroll.setWidget(panel)
        self.settings_stack.addWidget(scroll)

    def _build_panel_id_refs(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        hint = QLabel("Map raw scanned bubble values to human-readable labels.<br><br>"
                      "Example: if bubble position '1' represents 'Class IX', add that mapping so the CSV "
                      "shows 'Class IX' instead of '1'.<br><br>"
                      "<i>Requires Master Template to be set first (panel 1).</i>")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        refs_group = QGroupBox("Identifier Reference Values")
        refs_layout = QVBoxLayout(refs_group)
        self.btn_manage_identifier_references = QPushButton("Manage Identifier References...")
        self.btn_manage_identifier_references.clicked.connect(self.open_identifier_reference_dialog)
        refs_layout.addWidget(self.btn_manage_identifier_references)

        layout.addWidget(refs_group)
        layout.addStretch()
        scroll.setWidget(panel)
        self.settings_stack.addWidget(scroll)

    def _build_panel_export(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        hint = QLabel("Optionally send each scan result to a remote server or database immediately after it is saved to CSV.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.export_group_box = QGroupBox("Cloud & Database Export Settings")
        export_layout = QVBoxLayout(self.export_group_box)

        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Export Type:"))
        self.export_type_combo = QComboBox()
        self.export_type_combo.addItems(["None", "REST/Supabase/Firebase", "MySQL"])
        self.export_type_combo.currentIndexChanged.connect(self._toggle_export_panels)
        type_layout.addWidget(self.export_type_combo)
        export_layout.addLayout(type_layout)

        # REST Panel
        self.rest_panel = QWidget()
        rest_layout = QFormLayout(self.rest_panel)
        self.export_url_edit = QLineEdit()
        rest_layout.addRow("Base URL:", self.export_url_edit)
        rest_layout.addRow(QLabel("Dynamic Headers (Key-Value):"))
        self.headers_table = QTableWidget(0, 2)
        self.headers_table.setHorizontalHeaderLabels(["Header Key", "Header Value"])
        self.headers_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        rest_layout.addRow(self.headers_table)
        headers_btn_layout = QHBoxLayout()
        self.add_header_btn = QPushButton("Add Header")
        self.add_header_btn.clicked.connect(self._add_header_row)
        self.remove_header_btn = QPushButton("Remove Selected Header")
        self.remove_header_btn.clicked.connect(self._remove_header_row)
        headers_btn_layout.addWidget(self.add_header_btn)
        headers_btn_layout.addWidget(self.remove_header_btn)
        rest_layout.addRow(headers_btn_layout)
        export_layout.addWidget(self.rest_panel)

        # MySQL Panel
        self.mysql_panel = QWidget()
        mysql_layout = QFormLayout(self.mysql_panel)
        self.mysql_host_edit = QLineEdit()
        self.mysql_user_edit = QLineEdit()
        self.mysql_pass_edit = QLineEdit()
        self.mysql_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.mysql_db_edit = QLineEdit()
        self.mysql_table_edit = QLineEdit()
        mysql_layout.addRow("Host:", self.mysql_host_edit)
        mysql_layout.addRow("User:", self.mysql_user_edit)
        mysql_layout.addRow("Password:", self.mysql_pass_edit)
        mysql_layout.addRow("Database:", self.mysql_db_edit)
        mysql_layout.addRow("Table:", self.mysql_table_edit)
        export_layout.addWidget(self.mysql_panel)

        layout.addWidget(self.export_group_box)
        layout.addStretch()
        scroll.setWidget(panel)
        self.settings_stack.addWidget(scroll)

    def _build_panel_appearance(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        theme_group = QGroupBox("Theme & Appearance")
        theme_grid = QGridLayout(theme_group)

        theme_grid.addWidget(QLabel("Font Family:"), 0, 0)
        self.font_combo = QFontComboBox()
        theme_grid.addWidget(self.font_combo, 0, 1, 1, 2)

        theme_grid.addWidget(QLabel("Base Font Size:"), 1, 0)
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setRange(8, 18)
        self.font_size_label = QLabel("12px")
        self.font_size_slider.valueChanged.connect(lambda v: self.font_size_label.setText(f"{v}px"))
        theme_grid.addWidget(self.font_size_slider, 1, 1)
        theme_grid.addWidget(self.font_size_label, 1, 2)

        self.color_label = QLabel()
        self.color_label.setFixedWidth(100)
        self.color_label.setAutoFillBackground(True)
        btn_color = QPushButton("Select Theme Color...")
        btn_color.clicked.connect(self.select_theme_color)
        theme_grid.addWidget(QLabel("Theme Base Color:"), 2, 0)
        theme_grid.addWidget(self.color_label, 2, 1)
        theme_grid.addWidget(btn_color, 2, 2)

        self.panel_text_color_label = QLabel()
        self.panel_text_color_label.setFixedWidth(100)
        self.panel_text_color_label.setAutoFillBackground(True)
        btn_panel_text = QPushButton("Select Panel Text Color...")
        btn_panel_text.clicked.connect(self.select_panel_text_color)
        theme_grid.addWidget(QLabel("Panel Text Color:"), 3, 0)
        theme_grid.addWidget(self.panel_text_color_label, 3, 1)
        theme_grid.addWidget(btn_panel_text, 3, 2)

        self.header_text_color_label = QLabel()
        self.header_text_color_label.setFixedWidth(100)
        self.header_text_color_label.setAutoFillBackground(True)
        btn_header_text = QPushButton("Select Header Text Color...")
        btn_header_text.clicked.connect(self.select_header_text_color)
        theme_grid.addWidget(QLabel("Header Text Color:"), 4, 0)
        theme_grid.addWidget(self.header_text_color_label, 4, 1)
        theme_grid.addWidget(btn_header_text, 4, 2)

        self.button_color_label = QLabel()
        self.button_color_label.setFixedWidth(100)
        self.button_color_label.setAutoFillBackground(True)
        btn_button_color = QPushButton("Select Button Color...")
        btn_button_color.clicked.connect(self.select_button_color)
        theme_grid.addWidget(QLabel("Button Color:"), 5, 0)
        theme_grid.addWidget(self.button_color_label, 5, 1)
        theme_grid.addWidget(btn_button_color, 5, 2)

        self.transparency_slider = QSlider(Qt.Orientation.Horizontal)
        self.transparency_slider.setRange(0, 100)
        self.transparency_label = QLabel("70%")
        self.transparency_slider.valueChanged.connect(lambda v: self.transparency_label.setText(f"{v}%"))
        theme_grid.addWidget(QLabel("Panel Opacity:"), 6, 0)
        theme_grid.addWidget(self.transparency_slider, 6, 1)
        theme_grid.addWidget(self.transparency_label, 6, 2)

        self.button_height_slider = QSlider(Qt.Orientation.Horizontal)
        self.button_height_slider.setRange(15, 80)
        self.button_height_label = QLabel("50px")
        self.button_height_slider.valueChanged.connect(lambda v: self.button_height_label.setText(f"{v}px"))
        theme_grid.addWidget(QLabel("Button Height:"), 7, 0)
        theme_grid.addWidget(self.button_height_slider, 7, 1)
        theme_grid.addWidget(self.button_height_label, 7, 2)

        self.dark_mode_checkbox = QCheckBox("Enable Dark Mode")
        theme_grid.addWidget(self.dark_mode_checkbox, 8, 0, 1, 3)

        layout.addWidget(theme_group)
        layout.addStretch()
        scroll.setWidget(panel)
        self.settings_stack.addWidget(scroll)

    # ------------------------------------------------------------------
    # Dirty / clean state
    # ------------------------------------------------------------------

    def _set_dirty(self):
        """Enable the save button and flag the state as dirty."""
        if not self.is_dirty:
            self.is_dirty = True
        self.save_button.setEnabled(True)

    def _set_clean(self):
        """Disable the save button and flag the state as clean."""
        self.is_dirty = False
        if hasattr(self, 'save_button'):
            self.save_button.setEnabled(False)

    # ------------------------------------------------------------------
    # Pattern summary helpers
    # ------------------------------------------------------------------

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
        summary.append(f"• <b>CSV Result File:</b> {format_pattern('csv_filename_components', '.csv')}")
        cols = self.output_settings.value("selected_columns", [], type=list)
        summary.append(f"• <b>Excel Columns:</b> {', '.join(cols) if cols else 'None selected'}")
        self.output_settings.endGroup()

        active_matching_pattern_name = self.settings.value("active_matching_pattern", "")
        if active_matching_pattern_name:
            summary.append(f"• <b>Active Match Logic:</b> '{active_matching_pattern_name}'")
        else:
            summary.append(f"• <b>Active Match Logic:</b> <i>Not configured.</i>")

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

    # ------------------------------------------------------------------
    # Dialog launchers
    # ------------------------------------------------------------------

    def open_naming_output_dialog(self):
        master_template_path = self.line_edits["master_template"].text()
        student_data_path = self.line_edits["student_data_sheet"].text()

        if student_data_path.startswith('#') and not os.path.exists(student_data_path):
            QMessageBox.warning(self, "Corrupted Setting",
                                "The 'Student Data Sheet' path appears to be corrupted. "
                                "It has been reset. Please select the correct file again.")
            self.settings.remove("student_data_sheet")
            self.line_edits["student_data_sheet"].setText("")
            student_data_path = ""

        if not master_template_path or not os.path.exists(master_template_path):
            QMessageBox.warning(self, "Template Missing", "Please select a valid Master Template file first.")
            return

        settings = QSettings("OptiMark Pro", "Defaults")
        panel_text_color = settings.value("panel_text_color", "#FFFFFF")

        dialog = NamingOutputDialog(master_template_path, student_data_path, panel_text_color, self)
        apply_stylesheet_and_floatation(dialog)

        dialog.exec()
        self.populate_active_pattern_combo()
        self._update_pattern_summary()

    def open_advanced_matching_dialog(self):
        master_template_path = self.line_edits["master_template"].text()
        student_data_path = self.line_edits["student_data_sheet"].text()

        if not master_template_path or not os.path.exists(master_template_path):
            QMessageBox.warning(self, "Template Missing", "Please select a valid Master Template file first to configure advanced matching.")
            return

        dialog = AdvancedMatchingDialog(master_template_path, student_data_path, self)
        apply_stylesheet_and_floatation(dialog)
        dialog.matching_pattern_saved.connect(self._update_matching_pattern_display)
        dialog.exec()

    def open_identifier_reference_dialog(self):
        master_template_path = self.line_edits["master_template"].text()
        if not master_template_path or not os.path.exists(master_template_path):
            QMessageBox.warning(self, "Template Missing", "Please select a valid Master Template file first.")
            return

        settings = QSettings("OptiMark Pro", "Defaults")
        panel_text_color = settings.value("panel_text_color", "#FFFFFF")

        dialog = IdentifierReferenceDialog(master_template_path, panel_text_color, self)
        apply_stylesheet_and_floatation(dialog)
        dialog.exec()

    def _update_matching_pattern_display(self):
        self._update_pattern_summary()
        active_matching = self.settings.value("active_matching_pattern", "")
        if active_matching:
            self.active_matching_label.setText(f"Active Rule: <b>{active_matching}</b>")
        else:
            self.active_matching_label.setText("Active Rule: <i>Not configured</i>")

    # ------------------------------------------------------------------
    # File / folder browsing
    # ------------------------------------------------------------------

    def browse_file(self, key, caption, file_filter):
        initial_path = load_last_path(caption)
        path, _ = QFileDialog.getOpenFileName(self, caption, initial_path, file_filter)
        if path:
            save_last_path(caption, path)
            self.line_edits[key].setText(path)
            self._set_dirty()

    def browse_folder(self, key, caption):
        initial_path = load_last_path(caption)
        path = QFileDialog.getExistingDirectory(self, caption, initial_path)
        if path:
            save_last_path(caption, path)
            self.line_edits[key].setText(path)
            self._set_dirty()

    # ------------------------------------------------------------------
    # Color pickers
    # ------------------------------------------------------------------

    def select_theme_color(self):
        color = QColorDialog.getColor()
        if color.isValid(): self.selected_color = color; self.update_color_label(); self._set_dirty()

    def _toggle_export_panels(self, index):
        export_type = self.export_type_combo.currentText()
        self.rest_panel.setVisible(export_type == "REST/Supabase/Firebase")
        self.mysql_panel.setVisible(export_type == "MySQL")

    def _add_header_row(self):
        row_position = self.headers_table.rowCount()
        self.headers_table.insertRow(row_position)
        self.headers_table.setItem(row_position, 0, QTableWidgetItem(""))
        self.headers_table.setItem(row_position, 1, QTableWidgetItem(""))
        self._set_dirty()

    def _remove_header_row(self):
        selected_rows = sorted(list(set(index.row() for index in self.headers_table.selectedIndexes())), reverse=True)
        for row in selected_rows:
            self.headers_table.removeRow(row)
        self._set_dirty()

    def update_color_label(self):
        if self.selected_color and self.selected_color.isValid():
            palette = self.color_label.palette(); palette.setColor(QPalette.ColorRole.Window, self.selected_color)
            self.color_label.setPalette(palette); self.color_label.setText(self.selected_color.name())
        else: self.color_label.setText("No Color"); self.color_label.setPalette(QPalette())

    def select_panel_text_color(self):
        color = QColorDialog.getColor()
        if color.isValid(): self.selected_panel_text_color = color; self.update_panel_text_color_label(); self._set_dirty()

    def update_panel_text_color_label(self):
        if self.selected_panel_text_color and self.selected_panel_text_color.isValid():
            palette = self.panel_text_color_label.palette(); palette.setColor(QPalette.ColorRole.Window, self.selected_panel_text_color)
            self.panel_text_color_label.setPalette(palette); self.panel_text_color_label.setText(self.selected_panel_text_color.name())
        else: self.panel_text_color_label.setText("No Color"); self.panel_text_color_label.setPalette(QPalette())

    def select_header_text_color(self):
        color = QColorDialog.getColor()
        if color.isValid(): self.selected_header_text_color = color; self.update_header_text_color_label(); self._set_dirty()

    def update_header_text_color_label(self):
        if self.selected_header_text_color and self.selected_header_text_color.isValid():
            palette = self.header_text_color_label.palette(); palette.setColor(QPalette.ColorRole.Window, self.selected_header_text_color)
            self.header_text_color_label.setPalette(palette); self.header_text_color_label.setText(self.selected_header_text_color.name())
        else: self.header_text_color_label.setText("No Color"); self.header_text_color_label.setPalette(QPalette())

    def select_button_color(self):
        color = QColorDialog.getColor()
        if color.isValid(): self.selected_button_color = color; self.update_button_color_label(); self._set_dirty()

    def update_button_color_label(self):
        if self.selected_button_color and self.selected_button_color.isValid():
            palette = self.button_color_label.palette(); palette.setColor(QPalette.ColorRole.Window, self.selected_button_color)
            self.button_color_label.setPalette(palette); self.button_color_label.setText(self.selected_button_color.name())
        else: self.button_color_label.setText("No Color"); self.button_color_label.setPalette(QPalette())

    # ------------------------------------------------------------------
    # Load / save settings
    # ------------------------------------------------------------------

    def _clean_path(self, path):
        """Helper to fix common drive letter typos like 'Dz:/' -> 'D:/'."""
        if not path: return ""
        import re
        if len(path) >= 3 and path[1:3].lower() == 'z:' or (len(path) >= 3 and path[1:3].lower() == 'z/' ) or (len(path) >= 3 and path[1:3].lower() == 'z\\' ):
             return path[0] + ":" + path[3:]
        return path

    def load_settings(self):
        for key in self.paths:
            raw_path = self.settings.value(key, "")
            self.line_edits[key].setText(self._clean_path(raw_path))
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

        # Load Export Settings
        export_settings = QSettings("OptiMark Pro", "ExportSettings")
        self.export_type_combo.setCurrentText(export_settings.value("type", "None"))
        self.export_url_edit.setText(export_settings.value("url", ""))
        self.mysql_host_edit.setText(export_settings.value("mysql_host", ""))
        self.mysql_user_edit.setText(export_settings.value("mysql_user", ""))
        self.mysql_pass_edit.setText(export_settings.value("mysql_pass", ""))
        self.mysql_db_edit.setText(export_settings.value("mysql_db", ""))
        self.mysql_table_edit.setText(export_settings.value("mysql_table", ""))

        # Load Headers Table
        headers = export_settings.value("headers", {}, type=dict)
        self.headers_table.setRowCount(0)
        for key, value in headers.items():
            row = self.headers_table.rowCount()
            self.headers_table.insertRow(row)
            self.headers_table.setItem(row, 0, QTableWidgetItem(key))
            self.headers_table.setItem(row, 1, QTableWidgetItem(value))

        self._toggle_export_panels(0)
        self.populate_active_pattern_combo()
        self._update_pattern_summary()

        active_matching = self.settings.value("active_matching_pattern", "")
        if active_matching:
            self.active_matching_label.setText(f"Active Rule: <b>{active_matching}</b>")
        else:
            self.active_matching_label.setText("Active Rule: <i>Not configured</i>")

        self._set_clean()

    def revert_settings(self):
        self.settings.clear(); self.output_settings.clear()
        self.load_settings()
        self._set_clean()

    def save_settings(self):
        from cache_manager import clear_student_cache, clear_template_cache

        for key in self.line_edits:
            self.line_edits[key].setText(self._clean_path(self.line_edits[key].text().strip()))

        if self.settings.value("student_data_sheet", "") != self.line_edits["student_data_sheet"].text():
            clear_student_cache()
        if self.settings.value("master_template", "") != self.line_edits["master_template"].text():
            clear_template_cache()

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

        # Save Export Settings
        export_settings = QSettings("OptiMark Pro", "ExportSettings")
        export_settings.setValue("type", self.export_type_combo.currentText())
        export_settings.setValue("url", self.export_url_edit.text())
        export_settings.setValue("mysql_host", self.mysql_host_edit.text())
        export_settings.setValue("mysql_user", self.mysql_user_edit.text())
        export_settings.setValue("mysql_pass", self.mysql_pass_edit.text())
        export_settings.setValue("mysql_db", self.mysql_db_edit.text())
        export_settings.setValue("mysql_table", self.mysql_table_edit.text())

        # Save Headers Table
        headers = {}
        for row in range(self.headers_table.rowCount()):
            key_item = self.headers_table.item(row, 0)
            val_item = self.headers_table.item(row, 1)
            if key_item and val_item:
                key = key_item.text().strip()
                val = val_item.text().strip()
                if key:
                    headers[key] = val
        export_settings.setValue("headers", headers)

        self.settings_saved.emit()
        self._set_clean()

    def accept(self):
        self.save_settings()

    def _on_clear_cache_clicked(self):
        from cache_manager import clear_student_cache, clear_template_cache, CACHE_PATH
        try:
            clear_student_cache()
            clear_template_cache()
            QMessageBox.information(self, "Cache Cleared", f"Application cache cleared successfully from {CACHE_PATH}")
        except Exception as e:
            QMessageBox.critical(self, "Cache Clear Error", f"An error occurred while clearing cache: {str(e)}")
