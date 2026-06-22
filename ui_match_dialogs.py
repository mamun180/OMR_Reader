from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QComboBox, QLineEdit, QFormLayout, QWidget, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from theme import apply_stylesheet_and_floatation # Assuming this is available

class MultipleMatchesDialog(QDialog):
    def __init__(self, potential_matches, display_columns, scanned_primary_id, primary_roi_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Multiple Matches Found")
        self.setMinimumSize(800, 600)
        self.potential_matches = potential_matches
        self.display_columns = display_columns
        self.scanned_primary_id = scanned_primary_id
        self.primary_roi_name = primary_roi_name
        self.selected_student_info = None # To store the chosen student info
        self.action_taken = None # "ACCEPTED", "MANUAL_CORRECTION", "SKIP"

        main_layout = QVBoxLayout(self)

        info_label = QLabel(f"Scanned OMR Identifier <b>'{primary_roi_name}'</b> value: <b>'{scanned_primary_id}'</b>.")
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)

        secondary_info_label = QLabel("Multiple records match secondary criteria. Please select the correct student from the table:")
        secondary_info_label.setWordWrap(True)
        main_layout.addWidget(secondary_info_label)

        self.table_widget = QTableWidget(0, len(display_columns))
        self.table_widget.setHorizontalHeaderLabels(display_columns)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_widget.itemDoubleClicked.connect(self._accept_selected)
        main_layout.addWidget(self.table_widget)

        self._populate_table()

        buttons_layout = QHBoxLayout()
        self.accept_button = QPushButton("Accept Selected Match")
        self.accept_button.clicked.connect(self._accept_selected)
        self.manually_correct_button = QPushButton("Manually Correct Primary ID")
        self.manually_correct_button.clicked.connect(self._manually_correct)
        self.skip_sheet_button = QPushButton("Skip Sheet")
        self.skip_sheet_button.clicked.connect(self._skip_sheet)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.accept_button)
        buttons_layout.addWidget(self.manually_correct_button)
        buttons_layout.addWidget(self.skip_sheet_button)
        buttons_layout.addStretch()

        main_layout.addLayout(buttons_layout)
        apply_stylesheet_and_floatation(self) # Apply theme to dialog

    def reject(self):
        if self.action_taken is None:
            self.action_taken = "CANCELED"
        super().reject()

    def _populate_table(self):
        self.table_widget.setRowCount(len(self.potential_matches))
        for row_idx, match_data in enumerate(self.potential_matches):
            for col_idx, col_name in enumerate(self.display_columns):
                item = QTableWidgetItem(str(match_data.get(col_name, "")))
                item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable) # Make non-editable
                self.table_widget.setItem(row_idx, col_idx, item)
        if self.potential_matches:
            self.table_widget.selectRow(0) # Select first row by default

    def _accept_selected(self):
        selected_rows = self.table_widget.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select a student record from the table.")
            return

        selected_row_idx = selected_rows[0].row()
        self.selected_student_info = self.potential_matches[selected_row_idx]
        self.action_taken = "ACCEPTED"
        self.accept() # QDialog.Accepted

    def _manually_correct(self):
        self.action_taken = "MANUAL_CORRECTION"
        self.reject() # QDialog.Rejected, but with special internal status

    def _skip_sheet(self):
        self.action_taken = "SKIP_SHEET"
        self.reject() # QDialog.Rejected, but with special internal status

    def get_result(self):
        """Returns a tuple of (action_taken, selected_student_info)"""
        return (self.action_taken, self.selected_student_info)


class SingleSecondaryMatchDialog(QDialog):
    def __init__(self, match_result, display_columns, scanned_primary_id, primary_roi_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Suggestion for Primary ID")
        self.setMinimumWidth(500)
        self.action_taken = None

        main_layout = QVBoxLayout(self)

        info_text = (
            f"Scanned OMR Identifier <b>'{primary_roi_name}'</b> value '<b>{scanned_primary_id}</b>' was not found."
            f"<br>However, a unique student record was identified using the following details:"
        )
        main_layout.addWidget(QLabel(info_text))

        # Create a formatted display for the student info
        student_info = match_result.get("student_info", {})
        if student_info and isinstance(student_info, dict):
            # Use display_columns if provided, otherwise show all info in the dict
            columns_to_show = display_columns if display_columns else student_info.keys()
            
            details_widget = QWidget()
            details_layout = QFormLayout(details_widget)
            details_layout.setContentsMargins(15, 10, 15, 10)
            details_layout.setSpacing(5)
            details_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            
            for col in columns_to_show:
                value_label = QLabel(str(student_info.get(col, "N/A")))
                value_label.setWordWrap(True)
                details_layout.addRow(f"<b>{col}:</b>", value_label)
            
            main_layout.addWidget(details_widget)

        suggestion_text = QLabel(
            f"The suggested Primary ID for this record is: <b>{match_result.get('suggested_primary_id', 'N/A')}</b>"
            f"<br><br>Do you want to accept this suggested ID?"
        )
        suggestion_text.setWordWrap(True)
        main_layout.addWidget(suggestion_text)

        self.remember_checkbox = QCheckBox("Remember my choice for this session")
        main_layout.addWidget(self.remember_checkbox, alignment=Qt.AlignmentFlag.AlignCenter)

        buttons_layout = QHBoxLayout()
        self.accept_button = QPushButton("Accept Suggested ID")
        self.accept_button.clicked.connect(self._accept_suggestion)
        self.manually_correct_button = QPushButton("Manually Correct Primary ID")
        self.manually_correct_button.clicked.connect(self._manually_correct)
        self.skip_sheet_button = QPushButton("Skip Sheet")
        self.skip_sheet_button.clicked.connect(self._skip_sheet)

        buttons_layout.addStretch()
        buttons_layout.addWidget(self.accept_button)
        buttons_layout.addWidget(self.manually_correct_button)
        buttons_layout.addWidget(self.skip_sheet_button)
        buttons_layout.addStretch()

        main_layout.addLayout(buttons_layout)
        apply_stylesheet_and_floatation(self) # Apply theme to dialog

    def is_remember_checked(self):
        return self.remember_checkbox.isChecked()

    def reject(self):
        if self.action_taken is None:
            self.action_taken = "CANCELED"
        super().reject()

    def _accept_suggestion(self):
        self.action_taken = "ACCEPTED"
        self.accept()

    def _manually_correct(self):
        self.action_taken = "MANUAL_CORRECTION"
        self.reject()

    def _skip_sheet(self):
        self.action_taken = "SKIP_SHEET"
        self.reject()
    
    def get_result(self):
        """Returns the action taken by the user."""
        return self.action_taken


class ManualCorrectionDialog(QDialog):
    def __init__(self, current_primary_id, primary_roi_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manually Correct Primary ID")
        self.setMinimumWidth(400)
        self.new_primary_id = current_primary_id
        self.primary_roi_name = primary_roi_name

        main_layout = QVBoxLayout(self)

        info_label = QLabel(f"Please enter the correct Primary ID for <b>'{primary_roi_name}'</b>:")
        main_layout.addWidget(info_label)

        self.id_input = QLineEdit(current_primary_id)
        main_layout.addWidget(self.id_input)

        buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self._accept_input)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        buttons_layout.addStretch()
        buttons_layout.addWidget(self.ok_button)
        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addStretch()

        main_layout.addLayout(buttons_layout)
        apply_stylesheet_and_floatation(self)

    def _accept_input(self):
        self.new_primary_id = self.id_input.text().strip()
        if not self.new_primary_id:
            QMessageBox.warning(self, "Input Error", "Primary ID cannot be empty.")
            return
        self.accept()
    
    def get_new_primary_id(self):
        return self.new_primary_id