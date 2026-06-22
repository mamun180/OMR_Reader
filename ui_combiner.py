import os
import pandas as pd
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
                             QFileDialog, QListWidget, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QLabel, QComboBox, QMessageBox, QScrollArea,
                             QFrame, QCheckBox, QGroupBox, QInputDialog, QSplitter,
                             QListWidgetItem, QStackedWidget)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QColor
from theme import apply_stylesheet_and_floatation

class FileConfigWidget(QWidget):
    """A polished widget to configure an individual file's merge settings."""
    changed = pyqtSignal()

    def __init__(self, file_path, columns, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.columns = columns
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # File Info Header
        info_label = QLabel(f"<b>File:</b> {os.path.basename(self.file_path)}")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 1. Subject Configuration
        subj_group = QGroupBox("1. Identify Metadata (for Header)")
        subj_layout = QVBoxLayout(subj_group)
        
        # Subject
        self.subject_combo = QComboBox()
        self.subject_combo.addItems(["Auto (Filename)"] + self.columns)
        self.subject_combo.currentIndexChanged.connect(lambda: self.changed.emit())
        subj_layout.addWidget(QLabel("Subject Column:"))
        subj_layout.addWidget(self.subject_combo)
        
        # Class
        self.class_combo = QComboBox()
        self.class_combo.addItems(["None"] + self.columns)
        self.class_combo.currentIndexChanged.connect(lambda: self.changed.emit())
        subj_layout.addWidget(QLabel("Class Column:"))
        subj_layout.addWidget(self.class_combo)
        
        # Section
        self.section_combo = QComboBox()
        self.section_combo.addItems(["None"] + self.columns)
        self.section_combo.currentIndexChanged.connect(lambda: self.changed.emit())
        subj_layout.addWidget(QLabel("Section Column:"))
        subj_layout.addWidget(self.section_combo)
        
        layout.addWidget(subj_group)

        # 2. Primary Keys
        pk_group = QGroupBox("2. Primary Keys (How to match students)")
        pk_layout = QVBoxLayout(pk_group)
        self.pk_list = QListWidget()
        self.pk_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.pk_list.addItems(self.columns)
        self.pk_list.setFixedHeight(120)
        self.pk_list.itemSelectionChanged.connect(lambda: self.changed.emit())
        pk_layout.addWidget(self.pk_list)
        layout.addWidget(pk_group)

        # 3. Combine Columns
        val_group = QGroupBox("3. Columns to Extract")
        val_layout = QVBoxLayout(val_group)
        self.combine_list = QListWidget()
        self.combine_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.combine_list.addItems(self.columns)
        self.combine_list.setFixedHeight(120)
        self.combine_list.itemSelectionChanged.connect(lambda: self.changed.emit())
        val_layout.addWidget(self.combine_list)
        layout.addWidget(val_group)

    def auto_detect(self):
        """Intelligently pre-selects IDs, Scores, Class, and Section."""
        # Detect Metadata
        for i in range(self.pk_list.count()):
            text = self.pk_list.item(i).text().lower()
            if 'class' in text: self.class_combo.setCurrentText(self.pk_list.item(i).text())
            if 'section' in text or 'sec' == text: self.section_combo.setCurrentText(self.pk_list.item(i).text())
            if 'subject' in text: self.subject_combo.setCurrentText(self.pk_list.item(i).text())

        # Detect PKs
        pk_keywords = ['roll', 'id', 'student', 'uid', 'index', 'primary']
        for i in range(self.pk_list.count()):
            text = self.pk_list.item(i).text().lower()
            if any(k in text for k in pk_keywords):
                self.pk_list.item(i).setSelected(True)

        # Detect Combine Columns
        val_keywords = ['score', 'total', 'correct', 'mark', 'percentage', 'grade']
        for i in range(self.combine_list.count()):
            text = self.combine_list.item(i).text().lower()
            if any(k in text for k in val_keywords) and not any(k in text for k in pk_keywords):
                self.combine_list.item(i).setSelected(True)

    def smart_preselect(self, source_config):
        """Pre-selects columns in THIS widget based on selections in the first file."""
        if not source_config: return
        
        target_pks = set(source_config.get('pks', []))
        target_combines = set(source_config.get('combines', []))
        
        # Match PKs
        for i in range(self.pk_list.count()):
            if self.pk_list.item(i).text() in target_pks:
                self.pk_list.item(i).setSelected(True)
                
        # Match Combine Columns
        for i in range(self.combine_list.count()):
            if self.combine_list.item(i).text() in target_combines:
                self.combine_list.item(i).setSelected(True)
                
        # Match Metadata combos
        if source_config.get('subject_col') in self.columns:
            self.subject_combo.setCurrentText(source_config['subject_col'])
        if source_config.get('class_col') in self.columns:
            self.class_combo.setCurrentText(source_config['class_col'])
        if source_config.get('section_col') in self.columns:
            self.section_combo.setCurrentText(source_config['section_col'])

    def get_config(self):
        return {
            'file_path': self.file_path,
            'subject_col': None if self.subject_combo.currentText() == "Auto (Filename)" else self.subject_combo.currentText(),
            'class_col': None if self.class_combo.currentText() == "None" else self.class_combo.currentText(),
            'section_col': None if self.section_combo.currentText() == "None" else self.section_combo.currentText(),
            'pks': [item.text() for item in self.pk_list.selectedItems()],
            'combines': [item.text() for item in self.combine_list.selectedItems()]
        }

class ResultCombiner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_data_map = {} # path -> config_widget
        self.merged_df = None
        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        
        # Splitter: Left (Files & Config) | Right (Preview)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- LEFT PANEL: File List & Configuration ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0,0,5,0)

        # File List Group
        file_group = QGroupBox("Files to Combine")
        file_list_layout = QVBoxLayout(file_group)
        
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton(" Add Files")
        self.btn_add.setObjectName("nav-button-active")
        self.btn_add.clicked.connect(self.add_files)
        
        self.btn_sync = QPushButton(" Sync Settings")
        self.btn_sync.setObjectName("nav-button")
        self.btn_sync.setToolTip("Apply current Primary Key/Combine selections to all other files with matching column names.")
        self.btn_sync.clicked.connect(self.sync_all_files)
        
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_sync)
        file_list_layout.addLayout(btn_layout)

        self.file_list_widget = QListWidget()
        self.file_list_widget.currentRowChanged.connect(self.switch_config)
        file_list_layout.addWidget(self.file_list_widget)
        
        left_layout.addWidget(file_group)

        # Config Stack (Switches when file in list is clicked)
        self.config_stack = QStackedWidget()
        self.empty_label = QLabel("Add result files to start configuring...")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.config_stack.addWidget(self.empty_label)
        
        left_layout.addWidget(self.config_stack)
        
        # Combine Trigger
        self.btn_combine = QPushButton("Generate Combined Preview")
        self.btn_combine.setObjectName("nav-button-active")
        self.btn_combine.setFixedHeight(40)
        self.btn_combine.clicked.connect(self.combine_results)
        left_layout.addWidget(self.btn_combine)

        # --- RIGHT PANEL: Result Preview ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # --- NEW: Report Header Configuration ---
        header_config_group = QGroupBox("Report Header Settings (for Excel Export)")
        header_config_layout = QVBoxLayout(header_config_group)
        
        row1_layout = QHBoxLayout()
        row1_layout.addWidget(QLabel("Institution Name:"))
        self.edit_header_title = QLineEdit("Chattogram Cantonment Public College")
        row1_layout.addWidget(self.edit_header_title)
        header_config_layout.addLayout(row1_layout)
        
        row2_layout = QHBoxLayout()
        row2_layout.addWidget(QLabel("Address:"))
        self.edit_header_address = QLineEdit("Chattogram Cantonment, Chattogram")
        row2_layout.addWidget(self.edit_header_address)
        header_config_layout.addLayout(row2_layout)
        
        row3_layout = QHBoxLayout()
        row3_layout.addWidget(QLabel("Class/Section/Info:"))
        self.edit_header_info = QLineEdit("Class: X, Section: A")
        row3_layout.addWidget(self.edit_header_info)
        header_config_layout.addLayout(row3_layout)
        
        right_layout.addWidget(header_config_group)
        
        preview_header = QHBoxLayout()
        preview_header.addWidget(QLabel("<b>Data Preview</b> (Rename columns by double-clicking headers)"))
        preview_header.addStretch()
        
        self.btn_save_excel = QPushButton(" Save Final Results")
        self.btn_save_excel.setObjectName("nav-button-active")
        self.btn_save_excel.setEnabled(False)
        self.btn_save_excel.clicked.connect(self.save_results)
        preview_header.addWidget(self.btn_save_excel)
        right_layout.addLayout(preview_header)

        self.preview_table = QTableWidget()
        self.preview_table.horizontalHeader().sectionDoubleClicked.connect(self.rename_column)
        right_layout.addWidget(self.preview_table)

        # Assemble Splitter
        self.main_splitter.addWidget(left_panel)
        self.main_splitter.addWidget(right_panel)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 2)
        
        self.main_layout.addWidget(self.main_splitter)

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Result Files", "", "Excel/CSV (*.xlsx *.csv)")
        if not files: return

        # Get the config of the first-ever file added to use as a template for others
        first_config = None
        if self.file_list_widget.count() > 0:
            first_path = list(self.file_data_map.keys())[0]
            first_config = self.file_data_map[first_path].get_config()

        for f in files:
            if f in self.file_data_map: continue
            
            try:
                df = pd.read_csv(f, nrows=0) if f.endswith('.csv') else pd.read_excel(f, nrows=0)
                columns = df.columns.tolist()
                
                # Create Config Widget
                config_widget = FileConfigWidget(f, columns)
                
                # --- APPLY SMART PRESELECTION ---
                # If we already have a 'first file' in the list, sync this new one to it
                if first_config:
                    config_widget.smart_preselect(first_config)
                # If the list is empty (this is the first file), we do NOTHING (no preselection)
                # as per user requirement.

                # Add to List UI
                item = QListWidgetItem(os.path.basename(f))
                self.file_list_widget.addItem(item)
                
                # Add Config Widget to Stack
                self.config_stack.addWidget(config_widget)
                self.file_data_map[f] = config_widget
                
                self.file_list_widget.setCurrentRow(self.file_list_widget.count()-1)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not load {f}: {e}")

    def switch_config(self, index):
        if index < 0:
            self.config_stack.setCurrentIndex(0)
            return
        # Index + 1 because 0 is the empty label
        self.config_stack.setCurrentIndex(index + 1)

    def sync_all_files(self):
        """Smart Sync: Applies the current file's PK/Combine logic to all other files."""
        current_idx = self.file_list_widget.currentRow()
        if current_idx < 0: return
        
        source_config = self.config_stack.currentWidget().get_config()
        source_pks = set(source_config['pks'])
        source_combines = set(source_config['combines'])

        count = 0
        for path, widget in self.file_data_map.items():
            if widget == self.config_stack.currentWidget(): continue
            
            # Match PKs
            for i in range(widget.pk_list.count()):
                if widget.pk_list.item(i).text() in source_pks:
                    widget.pk_list.item(i).setSelected(True)
            
            # Match Combine Columns
            for i in range(widget.combine_list.count()):
                if widget.combine_list.item(i).text() in source_combines:
                    widget.combine_list.item(i).setSelected(True)
            count += 1
            
        QMessageBox.information(self, "Sync Complete", f"Synchronized settings to {count} other files.")

    def clear_all(self):
        self.file_list_widget.clear()
        self.file_data_map = {}
        while self.config_stack.count() > 1:
            widget = self.config_stack.widget(1)
            self.config_stack.removeWidget(widget)
            widget.deleteLater()
        self.preview_table.setRowCount(0)
        self.preview_table.setColumnCount(0)
        self.merged_df = None
        self.btn_save_excel.setEnabled(False)

    def combine_results(self):
        if not self.file_data_map: return

        configs = [w.get_config() for w in self.file_data_map.values()]
        
        try:
            merged_df = None
            first_file_pks = configs[0]['pks']
            
            all_classes, all_sections, all_subjects = set(), set(), []
            
            for i, cfg in enumerate(configs):
                # Load the full dataframe
                df = pd.read_csv(cfg['file_path']) if cfg['file_path'].endswith('.csv') else pd.read_excel(cfg['file_path'])
                
                # 1. Determine Metadata for Header
                prefix = ""
                if cfg['subject_col'] and cfg['subject_col'] in df.columns:
                    subj_val = df[cfg['subject_col']].dropna()
                    full_subj = str(subj_val.iloc[0]).strip() if not subj_val.empty else "Unknown"
                    if full_subj not in all_subjects: all_subjects.append(full_subj)
                else:
                    full_subj = os.path.splitext(os.path.basename(cfg['file_path']))[0]
                    if full_subj not in all_subjects: all_subjects.append(full_subj)

                if cfg['class_col'] and cfg['class_col'] in df.columns:
                    c_val = df[cfg['class_col']].dropna()
                    if not c_val.empty: all_classes.add(str(c_val.iloc[0]).strip())

                if cfg['section_col'] and cfg['section_col'] in df.columns:
                    s_val = df[cfg['section_col']].dropna()
                    if not s_val.empty: all_sections.add(str(s_val.iloc[0]).strip())

                # Smart Prefix Logic for Columns
                words = full_subj.split()
                if len(words) > 1: prefix = "".join([w[0].upper() for w in words if w])
                else: prefix = full_subj[:3].capitalize()

                # 2. Filter: Keep only PKs and the columns chosen to be combined
                current_pks = cfg['pks']
                combine_cols = cfg['combines']
                df = df[current_pks + combine_cols]

                # 3. Rename combine columns with the Prefix
                rename_map = {c: f"{prefix}_{c}" for c in combine_cols}
                
                # 4. Handle Primary Key alignment
                if i > 0:
                    if len(current_pks) != len(first_file_pks):
                        raise ValueError(f"File '{os.path.basename(cfg['file_path'])}' has {len(current_pks)} PKs, but the first file has {len(first_file_pks)}.")
                    for j in range(len(current_pks)):
                        rename_map[current_pks[j]] = first_file_pks[j]
                
                df = df.rename(columns=rename_map)

                # 5. Merge
                if merged_df is None: merged_df = df
                else: merged_df = pd.merge(merged_df, df, on=first_file_pks, how='outer')

            # Update Header UI automatically
            class_str = ", ".join(sorted(list(all_classes)))
            sec_str = ", ".join(sorted(list(all_sections)))
            subj_str = ", ".join(all_subjects)
            
            header_info = ""
            if class_str: header_info += f"Class: {class_str}"
            if sec_str: header_info += f"{', ' if header_info else ''}Section: {sec_str}"
            if subj_str: header_info += f"{', ' if header_info else ''}Subjects: {subj_str}"
            
            self.edit_header_info.setText(header_info)

            self.merged_df = merged_df
            self.refresh_preview()
            self.btn_save_excel.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, "Merge Error", f"An error occurred during combining:\n{str(e)}")

    def refresh_preview(self):
        if self.merged_df is None: return
        self.preview_table.setRowCount(len(self.merged_df))
        self.preview_table.setColumnCount(len(self.merged_df.columns))
        self.preview_table.setHorizontalHeaderLabels(self.merged_df.columns)
        
        for i in range(len(self.merged_df)):
            for j in range(len(self.merged_df.columns)):
                val = self.merged_df.iloc[i, j]
                self.preview_table.setItem(i, j, QTableWidgetItem(str(val) if pd.notnull(val) else ""))
        self.preview_table.resizeColumnsToContents()

    def rename_column(self, index):
        old_name = self.merged_df.columns[index]
        new_name, ok = QInputDialog.getText(self, "Rename Column", "New Column Name:", text=old_name)
        if ok and new_name:
            cols = list(self.merged_df.columns)
            cols[index] = new_name
            self.merged_df.columns = cols
            self.preview_table.setHorizontalHeaderLabels(cols)

    def save_results(self):
        if self.merged_df is None: return
        path, _ = QFileDialog.getSaveFileName(self, "Save Combined Result", "Combined_OMR_Results.xlsx", "Excel (*.xlsx);;CSV (*.csv)")
        if not path: return

        try:
            if path.endswith('.csv'):
                # CSV doesn't support easy multi-row headers like Excel, so we save normally
                self.merged_df.to_csv(path, index=False)
            else:
                # Excel Export with custom headers
                institution = self.edit_header_title.text().strip()
                address = self.edit_header_address.text().strip()
                info = self.edit_header_info.text().strip()

                # We use ExcelWriter to insert rows at the top
                with pd.ExcelWriter(path, engine='openpyxl') as writer:
                    # Write the main data starting from row 4 (index 3)
                    self.merged_df.to_excel(writer, index=False, startrow=3, sheet_name='Sheet1')
                    
                    # Access the worksheet to write headers
                    workbook = writer.book
                    worksheet = writer.sheets['Sheet1']
                    
                    # Write Header Rows
                    worksheet.cell(row=1, column=1, value=institution)
                    worksheet.cell(row=2, column=1, value=address)
                    worksheet.cell(row=3, column=1, value=info)

            QMessageBox.information(self, "Success", f"Results saved to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save file: {e}")

    def apply_theme(self):
        apply_stylesheet_and_floatation(self)
