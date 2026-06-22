from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
                             QGraphicsView, QGraphicsScene, QFileDialog, QMessageBox, QGraphicsPixmapItem, QInputDialog,
                             QSplitter, QScrollArea, QCheckBox, QButtonGroup, QLineEdit, QGroupBox, QSlider, QToolButton, QGraphicsItem,
                             QGridLayout, QRadioButton, QComboBox, QApplication, QTextEdit, QFrame, QDialog, QListWidget, QDialogButtonBox, QListWidgetItem,
                             QFormLayout, QGraphicsOpacityEffect, QTabWidget,
                             QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtGui import QImage, QPixmap, QColor, QBrush, QPen, QPolygonF, QPalette, QShortcut, QKeySequence
from PyQt6.QtCore import Qt, QRectF, QPointF, QEvent, QSettings, QDateTime, pyqtSignal, QTimer, QPropertyAnimation, QStandardPaths
import sys
import json
import cv2
import numpy as np
import datetime
import os
import pandas as pd
from openpyxl import load_workbook
from core_omr import OMREngine
import shutil
import logging
import re
from theme import apply_stylesheet_and_floatation
from directory_manager import get_answer_key_dir, get_results_dir
from settings_manager import save_last_path, load_last_path
from cache_manager import apply_identifier_reference
from ui_match_dialogs import MultipleMatchesDialog, SingleSecondaryMatchDialog, ManualCorrectionDialog
from scanner_manager import ScannerManager
from export_manager import ExportManager
from license_manager import record_omr_scans, load_license_key

logging.basicConfig(filename='app.log', filemode='w', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')




class Toast(QWidget):
    def __init__(self, parent, message, level='info', duration=2500):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QHBoxLayout(self)
        self.label = QLabel(message, self)
        font = self.label.font()
        font.setPointSize(11)
        self.label.setFont(font)
        layout.addWidget(self.label)

        bg_color_q = QColor(0, 0, 0, 190) # Default for info
        if level == 'warning':
            bg_color_q = QColor(255, 193, 7, 210)
        elif level == 'error':
            bg_color_q = QColor(220, 53, 69, 210)
        
        bg_rgb = (bg_color_q.red(), bg_color_q.green(), bg_color_q.blue())
        text_color_str = "white" # Fixed text color for toasts
        
        stylesheet = (f"background-color: rgba({bg_color_q.red()}, {bg_color_q.green()}, {bg_color_q.blue()}, {bg_color_q.alpha()}); "
                      f"color: {text_color_str}; "
                      "border-radius: 8px; padding: 8px 12px;")

        self.setStyleSheet(f"QWidget {{ {stylesheet} }}")
        
        self.adjustSize()

        parent_rect = parent.geometry()
        self.move(
            parent_rect.x() + (parent_rect.width() - self.width()) // 2,
            parent_rect.y() + parent_rect.height() - self.height() - 30
        )

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(300)
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fade_out)
        self.timer.start(duration)
        
        self.fade_in_animation.start()

    def fade_out(self):
        self.fade_out_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out_animation.setDuration(500)
        self.fade_out_animation.setStartValue(1.0)
        self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.finished.connect(self.close)
        self.fade_out_animation.start()


class MismatchAcceptDialog(QDialog):
    def __init__(self, mismatches, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Data Mismatch Detected")
        self.setMinimumWidth(450)
        layout = QVBoxLayout(self)

        message = "<p>A primary key match was found, but the following scanned data does not match the student record:</p>"
        
        table = "<table border='1' style='border-collapse: collapse; width:100%;' cellpadding='5'><tr><th>Field</th><th>Scanned Value</th><th>Expected Value</th></tr>"
        for item in mismatches:
            table += f"<tr><td><b>{item['roi']}</b></td><td style='color:red;'>{item['scanned']}</td><td style='color:green;'>{item['expected']}</td></tr>"
        table += "</table>"
        
        layout.addWidget(QLabel(message))
        layout.addWidget(QLabel(table))
        
        info_label = QLabel("\n<p>How would you like to proceed?</p>")
        layout.addWidget(info_label)
        
        # Define custom button roles for clarity
        self.AcceptScannedRole = QDialogButtonBox.ButtonRole.YesRole
        self.UseExpectedRole = QDialogButtonBox.ButtonRole.AcceptRole
        self.ManualEditRole = QDialogButtonBox.ButtonRole.ActionRole

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton("Accept Scanned", self.AcceptScannedRole)
        self.buttons.addButton("Use Expected Values", self.UseExpectedRole)
        self.buttons.addButton("Manual Edit", self.ManualEditRole)

        self.buttons.clicked.connect(self.button_clicked)

        self.remember_checkbox = QCheckBox("Remember my choice for this session")
        layout.addWidget(self.remember_checkbox)

        layout.addWidget(self.buttons)
        
        self.choice = QDialogButtonBox.StandardButton.Cancel

    def button_clicked(self, button):
        role = self.buttons.buttonRole(button)
        if role == self.AcceptScannedRole:
            self.choice = QDialogButtonBox.StandardButton.Yes
        elif role == self.UseExpectedRole:
            self.choice = QDialogButtonBox.StandardButton.Apply
        elif role == self.ManualEditRole:
            self.choice = QDialogButtonBox.StandardButton.Edit
        else:
            self.choice = QDialogButtonBox.StandardButton.Cancel
        self.accept()

    def exec(self):
        super().exec()
        return self.choice

    def is_remember_checked(self):
        return self.remember_checkbox.isChecked()

class CornerHandle(QGraphicsPixmapItem):
    def __init__(self, x, y, parent_window):
        pixmap = QPixmap(10, 10); pixmap.fill(QColor("red")); super().__init__(pixmap)
        self.setPos(x, y); self.setOffset(-5, -5); self.parent_window = parent_window
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable); self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemSendsGeometryChanges)
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged: self.parent_window.update_corner_polygon()
        return super().itemChange(change, value)

class ScannerGraphicsView(QGraphicsView):
    def __init__(self, scene, parent_window):
        super().__init__(scene, parent_window)
        self.parent_window = parent_window
        self.setMouseTracking(True)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.grabGesture(Qt.GestureType.PinchGesture)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            zoom_factor = 1.15
            if event.angleDelta().y() < 0: self.scale(1 / zoom_factor, 1 / zoom_factor)
            else: self.scale(zoom_factor, zoom_factor)
        else: super().wheelEvent(event)
    
    def viewportEvent(self, event):
        if event.type() == QEvent.Type.Gesture:
            gesture = event.gesture(Qt.GestureType.PinchGesture)
            if gesture and gesture.state() == Qt.GestureState.Updated:
                self.scale(gesture.scaleFactor(), gesture.scaleFactor()); return True
        return super().viewportEvent(event)
        
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton: super().mousePressEvent(event); return
        scene_pos = self.mapToScene(event.pos())
        if self.parent_window.is_manual_corner_mode: self.parent_window.add_manual_corner(scene_pos)
        else: super().mousePressEvent(event)
    def mouseMoveEvent(self, event):
        scene_pos = self.mapToScene(event.pos()); self.parent_window.update_inspector_panel(scene_pos)
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)

class IdentifierEditWidget(QWidget):
    def __init__(self, roi_name, roi_subtype, current_value, parent=None):
        super().__init__(parent); self.roi_name = roi_name; self.roi_subtype = roi_subtype
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(QLabel(f"<b>{self.roi_name}</b>:"))
        self.value_edit = QLineEdit(str(current_value)); layout.addWidget(self.value_edit)

class IdentifierDropdownWidget(QWidget):
    def __init__(self, roi_name, roi_subtype, options, current_value, parent=None):
        super().__init__(parent); self.roi_name = roi_name; self.roi_subtype = roi_subtype
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(QLabel(f"<b>{self.roi_name}</b>:"))
        self.combo_box = QComboBox(self); self.combo_box.addItems(options)
        if current_value and current_value in options: self.combo_box.setCurrentText(current_value)
        layout.addWidget(self.combo_box)

class QuestionAnswerWidget(QWidget):
    def __init__(self, q_num, options, selected_options, panel_text_color, multi_ans_strategy, parent=None):
        super().__init__(parent); self.q_num = q_num
        layout = QHBoxLayout(self)
        q_label = QLabel(f"Q{self.q_num}:")
        q_label.setStyleSheet(f"color: {panel_text_color.name()};") # Apply theme color
        layout.addWidget(q_label)
        self.option_group = QButtonGroup(self); self.option_group.setExclusive(False)
        for i, option_char in enumerate(options):
            checkbox = QCheckBox(option_char)
            if option_char in selected_options: checkbox.setChecked(True)
            self.option_group.addButton(checkbox, i); layout.addWidget(checkbox)
        layout.addStretch()



class AnswerKeyReviewWidget(QWidget):
    def __init__(self, key_data, parent=None):
        super().__init__(parent)
        self.key_data = key_data
        self.path = key_data.get('path', '')
        
        layout = QVBoxLayout(self)
        
        # Identifiers
        id_group = QGroupBox("Identifiers")
        id_layout = QFormLayout(id_group)
        self.id_edits = {}

        template = self.key_data.get('template', {})
        identifier_rois = [roi for roi in template.get('rois', []) if roi.get('type') in ['Identifier', 'qrcode']]
        answer_key_identifiers = self.key_data.get('identifiers', {})

        for roi_data in identifier_rois:
            name = roi_data.get('name')
            if not name: continue

            value = answer_key_identifiers.get(name, "")
            widget = None

            is_single_choice = roi_data and (int(roi_data.get('rows', 0)) == 1 or int(roi_data.get('cols', 0)) == 1)

            if is_single_choice and roi_data.get('values') and isinstance(roi_data['values'], list):
                combo = QComboBox()
                # Ensure a blank option is available
                options = [""] + [opt for opt in roi_data['values'] if opt]
                combo.addItems(list(dict.fromkeys(options))) # Add unique items, preserving order

                if str(value) in options:
                    combo.setCurrentText(str(value))
                else:
                    combo.setCurrentIndex(0) # Default to blank
                widget = combo
            else:
                widget = QLineEdit(str(value))
            
            self.id_edits[name] = widget
            name_label = QLabel(name)
            id_layout.addRow(name_label, widget)
        
        id_widget = QWidget()
        id_widget.setLayout(id_layout)

        id_scroll = QScrollArea()
        id_scroll.setWidgetResizable(True)
        id_scroll.setWidget(id_widget)
        id_scroll.setMinimumHeight(100)
        layout.addWidget(id_scroll)

        # Answers
        ans_group = QGroupBox("Answers")
        ans_layout = QFormLayout()
        self.ans_edits = {}
        sorted_answers = sorted(self.key_data.get('answers', {}).items(), key=lambda item: int(item[0]))
        for q_num, ans in sorted_answers:
            ans_str = ", ".join(ans) if isinstance(ans, list) else str(ans)
            edit = QLineEdit(ans_str)
            self.ans_edits[q_num] = edit
            q_num_label = QLabel(f"Q{q_num}:")
            ans_layout.addRow(q_num_label, edit)
        
        ans_widget = QWidget()
        ans_widget.setLayout(ans_layout)
        ans_scroll = QScrollArea()
        ans_scroll.setWidgetResizable(True)
        ans_scroll.setWidget(ans_widget)
        layout.addWidget(ans_scroll)

        self.save_button = QPushButton("Save Changes to Answer Key")
        self.save_button.clicked.connect(self.save_changes)
        layout.addWidget(self.save_button)

    def save_changes(self):
        # Update identifiers
        for name, widget in self.id_edits.items():
            if isinstance(widget, QComboBox):
                self.key_data['identifiers'][name] = widget.currentText()
            elif isinstance(widget, QLineEdit):
                self.key_data['identifiers'][name] = widget.text()
        
        # Update answers
        for q_num, edit in self.ans_edits.items():
            self.key_data['answers'][q_num] = [x.strip() for x in edit.text().split(',') if x.strip()]
            
        # Save to file
        if self.path:
            try:
                with open(self.path, 'w') as f:
                    json.dump(self.key_data, f, indent=4)
                if self.parent() and hasattr(self.parent(), 'show_toast'):
                    self.parent().show_toast(f"Saved changes to {os.path.basename(self.path)}", level='info')
            except Exception as e:
                if self.parent() and hasattr(self.parent(), 'show_toast'):
                    self.parent().show_toast(f"Error saving file: {e}", level='error')
        else:
            if self.parent() and hasattr(self.parent(), 'show_toast'):
                self.parent().show_toast("Cannot save: No file path for this answer key.", level='error')

# Match status constants for clarity
MATCH_PRIMARY = "PRIMARY_MATCH"
MATCH_SINGLE_SECONDARY = "SINGLE_SECONDARY_MATCH"
MATCH_MULTIPLE_SECONDARY = "MULTIPLE_SECONDARY_MATCHES"
MATCH_NO_MATCH = "NO_MATCH"
MATCH_PRIMARY_MISMATCH_SECONDARY = "PRIMARY_MATCH_MISMATCH_SECONDARY"

class CheckerWindow(QWidget):
    log_updated = pyqtSignal()
    image_selection_updated = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("CheckerWindow") 

        self.scanner_manager = ScannerManager()
        self.scanner_manager.image_scanned.connect(self._on_hardware_image_scanned)
        self.scanner_manager.error_occurred.connect(lambda msg: QMessageBox.critical(self, "Scanner Error", msg))
        self.export_manager = ExportManager()
        
        self.identifier_input_timer = QTimer(self)
        self.identifier_input_timer.setSingleShot(True)
        self.identifier_input_timer.setInterval(200) # Debounce timer for live re-scan
        self.identifier_input_timer.timeout.connect(self._live_rescan_from_identifiers)

        self.auto_scan_preview_timer = QTimer(self)
        self.auto_scan_preview_timer.setSingleShot(True)
        self.auto_scan_preview_timer.timeout.connect(self._advance_scan_process)

        self.apply_theme()

        self.panel_text_color = QColor("black") # will be updated by theme

        self.engine = OMREngine()
        self.template_data, self.current_image, self.warped_image, self.scan_results = None, None, None, None
        self.image_paths = []
        self.roi_items, self.manual_corner_items, self.corner_handles = [], [], []
        self.is_manual_corner_mode = False
        self.is_scan_stopped = False
        self.manual_corners, self.corner_polygon = [], None
        self.identifier_override_widgets = {}
        self.identifier_widgets = {}
        self.question_widgets = {}
        self.image_pixmap_item = None
        self.homography_matrix = None
        self.warp_matrix = None
        self.correct_answers_map = {}
        self.answer_key_data = []
        self.current_matched_key_path = None
        self.image_list_items = {}
        self.current_image_processing_params = {
            'contrast': 1.3, 'brightness': 30, 'blur': 5, 'rotation': 0,
            'adaptive_c': 3, 'threshold': 0.05, 'method': 'contour',
            'grayscale': False, 'transparency': 143
        }
        self.active_output_pattern = None
        self.student_data = None
        self.remembered_mismatch_choice = None
        self.remembered_secondary_match_choice = None
        self.last_zoom_transform = None

        # --- NEW: Load Advanced Matching Rules ---
        self.advanced_matching_settings = QSettings("OptiMark Pro", "AdvancedMatchingPatterns")
        self.defaults_settings = QSettings("OptiMark Pro", "Defaults")
        self.active_matching_rule_name = self.defaults_settings.value("active_matching_pattern", "")
        self.active_matching_rule = self._load_matching_rule_by_name(self.active_matching_rule_name)
        if self.active_matching_rule:
            self.log(f"Loaded active matching rule: '{self.active_matching_rule_name}'")
        else:
            self.log("No advanced matching rule configured or found.")
        self.student_info_for_output = None # Initialize student info for output preview
        # --- END NEW ---

        self.bubble_items = {'identifier': [], 'answer': []}
        self.current_review_index = 0
        self.review_widgets = []

        self.log_has_update = False
        self.image_panel_has_update = False

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(2)

        self.main_v_splitter = QSplitter(Qt.Orientation.Vertical)

        self.top_panel = QWidget()
        self.top_panel_layout = QHBoxLayout(self.top_panel)
        self.top_panel_layout.setContentsMargins(3, 0, 0, 0)
        self.top_panel_layout.setSpacing(2)
        self.main_v_splitter.addWidget(self.top_panel)

        self.log_images_tab_widget = QTabWidget()
        self.log_updated.connect(self.handle_log_update)
        self.image_selection_updated.connect(self.handle_image_update)

        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.content_splitter.setObjectName("main_splitter")
        self.main_v_splitter.addWidget(self.content_splitter)
        
        self.main_layout.addWidget(self.main_v_splitter)

        settings = QSettings("OptiMark Pro", "Defaults")
        button_color_name = settings.value("button_color", "#FFFFFF")
        self.button_theme_color = QColor(button_color_name)
        
        self.left_panel_widget = QWidget()
        self.left_panel_widget.setObjectName("left_panel_widget")
        self.left_panel_layout = QVBoxLayout(self.left_panel_widget)
        self.left_panel_layout.setContentsMargins(5, 2, 2, 2)
        self.left_panel_layout.setSpacing(2)
        self.content_splitter.addWidget(self.left_panel_widget)
        
        self.image_list_panel = QWidget()
        self.image_list_panel.setObjectName("image_list_panel")
        self.image_list_layout = QVBoxLayout(self.image_list_panel)
        self.image_list_layout.setContentsMargins(5, 0, 0, 0)
        self.image_list_layout.setSpacing(2)
        self.image_list_widget = QListWidget()
        self.image_list_layout.addWidget(QLabel("<b>Selected Images</b>"))
        self.image_list_layout.addWidget(self.image_list_widget)
        self.log_images_tab_widget.addTab(self.image_list_panel, "Selected Images")

        self.canvas_container = QWidget()
        self.canvas_layout = QVBoxLayout(self.canvas_container)
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        self.scene = QGraphicsScene()
        self.view = ScannerGraphicsView(self.scene, self)
        self.canvas_layout.addWidget(self.view)
        self.content_splitter.addWidget(self.canvas_container)

        self.right_panel_widget = QWidget()
        self.right_panel_widget.setObjectName("right_panel_widget")
        self.right_panel_layout = QVBoxLayout(self.right_panel_widget)
        self.right_panel_layout.setContentsMargins(5, 0, 0, 0)
        self.right_panel_layout.setSpacing(2)
        self.answers_scroll_area = QScrollArea()
        self.answers_scroll_area.setObjectName("answers_scroll_area")
        self.answers_scroll_area.setWidgetResizable(True)
        self.answers_widget = QWidget()
        self.answers_widget.setObjectName("answers_widget")
        self.answers_layout = QVBoxLayout(self.answers_widget)
        self.answers_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.answers_layout.setContentsMargins(0,0,0,0)
        self.answers_layout.setSpacing(0)
        self.answers_scroll_area.setWidget(self.answers_widget)
        self.right_panel_layout.addWidget(self.answers_scroll_area)
        self.content_splitter.addWidget(self.right_panel_widget)
        
        
        self._init_top_panel()
        self._init_left_panel()
        self._init_right_panel()
        self.load_student_data() 
        self._load_output_settings() 
        self._update_output_pattern_display()        
        self.zoom_in_button = QToolButton(self.view) 
        self.zoom_in_button.setText('+')
        self.zoom_in_button.clicked.connect(self.zoom_in)
        self.zoom_out_button = QToolButton(self.view)
        self.zoom_out_button.setText('-')
        self.zoom_out_button.clicked.connect(self.zoom_out)
        self.result_preview_table = QTableWidget(1, 0)
        self.result_preview_table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.result_preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.result_preview_table.verticalHeader().setVisible(False)
        self.result_preview_table.setFixedHeight(52)
        self.result_preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.result_preview_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.main_layout.addWidget(self.result_preview_table)

        self.bottom_panel_widget = QWidget()
        bottom_layout = QHBoxLayout(self.bottom_panel_widget)
        bottom_layout.setContentsMargins(5,2,5,2)
        bottom_layout.setSpacing(10)

        # Score Label
        self.score_label = QLabel("Score: N/A; Correct: N/A; Unanswered: N/A")
        bottom_layout.addWidget(self.score_label)

        bottom_layout.addStretch()

        # Scanning Progress Panel
        self.scan_progress_label = QLabel("")
        bottom_layout.addWidget(self.scan_progress_label)

        bottom_layout.addStretch()

        self.btn_toggle_debug = QPushButton("Debug ▶")
        self.btn_toggle_debug.setCheckable(True)
        self.btn_toggle_debug.setFixedWidth(74)
        self.btn_toggle_debug.setToolTip("Show/hide pixel inspector (for advanced tuning)")
        self.btn_toggle_debug.toggled.connect(self._toggle_debug_panel)
        bottom_layout.addWidget(self.btn_toggle_debug)

        self.inspector_widget = QWidget()
        _insp_layout = QHBoxLayout(self.inspector_widget)
        _insp_layout.setContentsMargins(0, 0, 0, 0)
        _insp_layout.setSpacing(8)
        self.inspector_pixel_label = QLabel("Pixels: N/A")
        self.inspector_contour_label = QLabel("Area: N/A")
        self.inspector_fill_label = QLabel("Fill: N/A")
        _insp_layout.addWidget(self.inspector_pixel_label)
        _insp_layout.addWidget(self.inspector_contour_label)
        _insp_layout.addWidget(self.inspector_fill_label)
        self.inspector_widget.setVisible(False)
        bottom_layout.addWidget(self.inspector_widget)

        self.main_layout.addWidget(self.bottom_panel_widget)
        self.btn_refresh_ans_keys.clicked.connect(self.populate_answer_key_combobox)
        self.multi_ans_group.buttonClicked.connect(self.rescan_with_new_parameters)
        self.scan_mode_group.buttonClicked.connect(self.rescan_with_new_parameters)

        self.populate_answer_key_combobox()

        # Keyboard shortcuts
        QShortcut(QKeySequence("F5"), self).activated.connect(
            lambda: self._start_scan_process() if self.btn_start_scan.isVisible() and self.btn_start_scan.isEnabled() else None
        )
        QShortcut(QKeySequence("F6"), self).activated.connect(
            lambda: self._process_next_image() if self.btn_next_image.isVisible() and self.btn_next_image.isEnabled() else None
        )
        QShortcut(QKeySequence("F7"), self).activated.connect(
            lambda: self._skip_current_image() if self.btn_skip_image.isVisible() and self.btn_skip_image.isEnabled() else None
        )
        QShortcut(QKeySequence("Escape"), self).activated.connect(
            lambda: self._stop_scan_process() if self.btn_stop_scan.isVisible() else None
        )

        self._show_canvas_placeholder()

    def showEvent(self, event):
        super().showEvent(event)
        # Set splitter sizes when the widget is shown to ensure correct layout
        self.main_v_splitter.setSizes([140, 500])
        
        splitter_width = self.content_splitter.width()
        if splitter_width > 0:
            left_width = int(splitter_width * 0.20)
            right_width = int(splitter_width * 0.20)
            middle_width = splitter_width - (left_width + right_width)
            self.content_splitter.setSizes([left_width, middle_width, right_width])
        else:
            # Fallback if width is not yet available
            self.content_splitter.setSizes([20, 60, 20])

        self.log(f"main_v_splitter sizes on show: {self.main_v_splitter.sizes()}")
        self.log(f"content_splitter sizes on show: {self.content_splitter.sizes()}")
        if not self.image_paths:
            self._show_canvas_placeholder()

    def _show_canvas_placeholder(self):
        self.scene.clear()
        self.scene.setSceneRect(0, 0, 800, 560)
        text_item = self.scene.addText("Click 'Add Images' or 'Hardware Scan' to begin")
        text_item.setDefaultTextColor(QColor(160, 160, 160))
        font = text_item.font()
        font.setPointSize(13)
        text_item.setFont(font)
        br = text_item.boundingRect()
        text_item.setPos((800 - br.width()) / 2, (560 - br.height()) / 2)
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _toggle_debug_panel(self, checked):
        self.inspector_widget.setVisible(checked)
        self.btn_toggle_debug.setText("Debug ▼" if checked else "Debug ▶")

    def _record_scan_async(self, count=1):
        """Fire-and-forget: report scanned sheets to the license server in background."""
        license_data = load_license_key()
        if not license_data or license_data.get("license_type") != "COUNT_BASED":
            return  # Only COUNT_BASED licenses need reporting
        import threading
        def _do_record():
            success, message, remaining = record_omr_scans(count)
            if success:
                if remaining >= 0:
                    self.show_toast(f"Scan recorded. Credits remaining: {remaining}", level='info')
            else:
                self.show_toast(f"License record failed (offline?): {message}", level='warning')
        threading.Thread(target=_do_record, daemon=True).start()

    def populate_answer_key_combobox(self):
        self.ans_key_combobox.blockSignals(True)
        current_text = self.ans_key_combobox.currentText()
        self.ans_key_combobox.clear()
        self.ans_key_combobox.addItem("Select an answer key...")
        
        answer_key_dir = get_answer_key_dir()
        if answer_key_dir and os.path.isdir(answer_key_dir):
            try:
                keys = [f for f in os.listdir(answer_key_dir) if f.endswith('.json')]
                self.ans_key_combobox.addItems(sorted(keys))
            except OSError as e:
                self.log(f"Error reading answer key directory: {e}")
        
        self.ans_key_combobox.addItem("Browse for answer key(s)...")

        # Try to restore previous selection if it's still in the list
        if (index := self.ans_key_combobox.findText(current_text)) != -1:
            self.ans_key_combobox.setCurrentIndex(index)
        self.ans_key_combobox.blockSignals(False)

    def on_answer_key_selected(self, index):
        if index == -1 or self.ans_key_combobox.itemText(index) in ["", "Select an answer key..."]:
            return
        
        selection = self.ans_key_combobox.itemText(index)
        
        if "keys loaded" in selection: # Ignore this item, it's just a display text
            return

        if selection == "Browse for answer key(s)...":
            self.browse_for_answer_key()
            self.ans_key_combobox.setCurrentIndex(0) 
        else:
            key_path = os.path.join(get_answer_key_dir(), selection)
            if os.path.exists(key_path):
                self._load_answer_keys([key_path])
            else:
                QMessageBox.warning(self, "File Not Found", f"Answer key file not found at: {key_path}")
                self.populate_answer_key_combobox()

    def browse_for_answer_key(self):
        dialog_key = "Select Answer Key(s)"
        initial_path = load_last_path(dialog_key) or get_answer_key_dir()
        paths, _ = QFileDialog.getOpenFileNames(self, dialog_key, initial_path, "JSON Files (*.json)")
        if paths:
            if paths:
                save_last_path(dialog_key, os.path.dirname(paths[0]))
            self._load_answer_keys(paths)

    def _load_answer_keys(self, paths):
        self.answer_key_data = []
        for path in paths:
            try:
                with open(path, 'r') as f: data = json.load(f)
                if 'template' not in data or 'identifiers' not in data or 'answers' not in data:
                    self.log(f"Warning: Answer key '{path}' is missing required fields. Skipping.")
                    continue
                self.answer_key_data.append({'path': path, **data})
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load or parse answer key: {path}\n{e}")
        
        if not self.answer_key_data:
            self.show_toast("Could not load any valid answer keys.", 'warning')
            self.populate_answer_key_combobox() # Reset combobox
            self.btn_review_keys.setEnabled(False)
            return

        self.log(f"Loaded {len(self.answer_key_data)} answer key(s).")
        self.btn_review_keys.setEnabled(True)
        self.template_data = self.answer_key_data[0]['template']
        if self.answer_key_data[0].get('image_settings'):
            self._set_params_on_ui(self.answer_key_data[0]['image_settings'])
            self.log(f"Image settings loaded from: {os.path.basename(self.answer_key_data[0]['path'])}")
        
        self._create_right_panel_widgets()
        self._populate_identifier_overrides()
        self._update_output_pattern_display() # This now handles both Excel and Rename pattern display

        # Update combobox and status label
        self.ans_key_combobox.blockSignals(True)
        if len(paths) == 1:
            key_name = os.path.basename(paths[0])
            if (index := self.ans_key_combobox.findText(key_name)) != -1:
                self.ans_key_combobox.setCurrentIndex(index)
            self.ans_key_status_label.setText(f"Active: {key_name}")
        else:
            self.ans_key_combobox.setCurrentIndex(0) # Back to "Select..."
            self.ans_key_status_label.setText(f"Multiple keys ({len(paths)}) loaded")
        self.ans_key_combobox.blockSignals(False)

    def _review_selected_key(self):
        if not self.answer_key_data:
            self.show_toast("No answer keys are loaded to review.", 'warning')
            return

        self.current_review_index = 0
        self.review_widgets = []

        while self.answers_layout.count():
            item = self.answers_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        for key_data in self.answer_key_data:
            review_widget = AnswerKeyReviewWidget(key_data, self)
            review_widget.setVisible(False)
            self.answers_layout.addWidget(review_widget)
            self.review_widgets.append(review_widget)

        nav_layout = QHBoxLayout()
        self.prev_key_button = QPushButton("Previous")
        self.prev_key_button.clicked.connect(self.show_previous_key)
        self.next_key_button = QPushButton("Next")
        self.next_key_button.clicked.connect(self.show_next_key)
        nav_layout.addWidget(self.prev_key_button)
        nav_layout.addWidget(self.next_key_button)
        self.answers_layout.addLayout(nav_layout)

        self.show_current_review_key()

    def _select_all_answer_keys(self, checked):
        if checked:
            self.ans_key_combobox.setEnabled(False)
            answer_key_dir = get_answer_key_dir()
            if answer_key_dir and os.path.isdir(answer_key_dir):
                try:
                    paths = [os.path.join(answer_key_dir, f) for f in os.listdir(answer_key_dir) if f.endswith('.json')]
                    if paths:
                        self._load_answer_keys(paths)
                        self.ans_key_status_label.setText(f"Loaded {len(paths)} keys from directory.")
                        self.btn_review_keys.setEnabled(True) # Enable review button after loading
                    else:
                        self.show_toast("No answer keys (.json) found in the directory.", 'warning')
                        self.select_all_keys_checkbox.setChecked(False) # Uncheck if no keys were found
                        self.btn_review_keys.setEnabled(False) # Disable if no keys were found
                except OSError as e:
                    self.log(f"Error reading answer key directory: {e}")
                    self.show_toast(f"Error accessing answer key directory: {e}", 'error')
                    self.select_all_keys_checkbox.setChecked(False) # Uncheck on error
                    self.btn_review_keys.setEnabled(False) # Disable on error
            else:
                self.show_toast("Answer key directory is not set or not found.", 'error')
                self.select_all_keys_checkbox.setChecked(False) # Uncheck if dir is not there
                self.btn_review_keys.setEnabled(False) # Disable if dir is not found
        else:
            self.ans_key_combobox.setEnabled(True)
            self.btn_review_keys.setEnabled(False) # Disable when unchecked and clearing keys
            self.answer_key_data = []
            self.template_data = None
            self.populate_answer_key_combobox()
            self._create_right_panel_widgets()
            self._populate_identifier_overrides()
            self.ans_key_status_label.setText("No key loaded.")
            self.log("Cleared all loaded answer keys.")

    def show_current_review_key(self):
        if not self.review_widgets:
            return

        for i, widget in enumerate(self.review_widgets):
            widget.setVisible(i == self.current_review_index)

        self.prev_key_button.setEnabled(self.current_review_index > 0)
        self.next_key_button.setEnabled(self.current_review_index < len(self.review_widgets) - 1)
        
        key_path = self.review_widgets[self.current_review_index].path
        self.show_toast(f"Reviewing {os.path.basename(key_path)} ({self.current_review_index + 1}/{len(self.review_widgets)})", 'info')

    def show_previous_key(self):
        if self.current_review_index > 0:
            self.current_review_index -= 1
            self.show_current_review_key()

    def show_next_key(self):
        if self.current_review_index < len(self.review_widgets) - 1:
            self.current_review_index += 1
            self.show_current_review_key()
    
    def load_student_data(self):
        app_data_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        if not os.path.exists(app_data_path):
            os.makedirs(app_data_path)
        cache_file = os.path.join(app_data_path, "student_data_cache.xlsx")

        settings = QSettings("OptiMark Pro", "Defaults")
        original_excel_path = settings.value("student_data_sheet", "")

        self.student_data = None # Initialize to None

        if original_excel_path and os.path.exists(original_excel_path):
            try:
                # Always load from the original source if it exists and is valid
                self.student_data = pd.read_excel(original_excel_path)
                self.log(f"Student data loaded from original source: {os.path.basename(original_excel_path)}.")
                
                # Always update the cache with the latest data from the original source
                # This ensures the cache is fresh and ready for subsequent quick loads
                shutil.copy(original_excel_path, cache_file)
                self.log("Student data cache updated successfully.")

            except Exception as e:
                self.log(f"Error loading student data from original source '{original_excel_path}': {str(e)}")
                QMessageBox.critical(self, "Student Data Load Error", f"Failed to load student data from '{original_excel_path}'.\nError: {str(e)}")
                
                # If original source fails, try to fall back to cache if it exists and is valid
                if os.path.exists(cache_file):
                    try:
                        self.student_data = pd.read_excel(cache_file)
                        self.log("Student data successfully loaded from (fallback) cache.")
                    except Exception as cache_e:
                        self.log(f"Error loading student data from fallback cache: {cache_e}. No student data loaded.")
        else:
            self.log("No original student data sheet configured or file not found. Checking cache...")
            if os.path.exists(cache_file):
                try:
                    self.student_data = pd.read_excel(cache_file)
                    self.log("Student data loaded from cache (no original source configured).")
                except Exception as e:
                    self.log(f"Error loading student data from cache: {e}. No student data loaded.")
            else:
                self.log("No student data available (neither original source nor cache).")
        
    def apply_theme(self):
        apply_stylesheet_and_floatation(self)

    def show_toast(self, message, level='info', duration=1500):
        Toast(self, message, level, duration).show()

    def _clear_layout(self, layout):
        if layout is None: return
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
                item.layout().deleteLater()

    def _set_active_output_pattern(self, pattern_name):
        QSettings("OptiMark Pro", "Defaults").setValue("last_output_pattern", pattern_name)
        self._update_output_pattern_display()

    def _update_output_pattern_display(self):
        app_settings = QSettings("OptiMark Pro", "Defaults")
        pattern_name = app_settings.value("last_output_pattern", "")
        if not hasattr(self, 'output_pattern_label'): return

        if not pattern_name:
            self.output_pattern_label.setText("Active Pattern: <None>")
            self.active_output_pattern = None
            if hasattr(self, 'new_excel_filename_edit'): # Check if this attribute exists
                self.new_excel_filename_edit.setPlaceholderText("e.g., my_results.csv")
                self.new_excel_filename_edit.setReadOnly(False)
            return

        output_settings = QSettings("OptiMark Pro", "OutputPatterns")
        if pattern_name not in output_settings.childGroups():
            self.output_pattern_label.setText(f"Pattern '{pattern_name}': Not Found!")
            self.active_output_pattern = None
            return

        output_settings.beginGroup(pattern_name)
        csv_filename_components = output_settings.value("csv_filename_components", [], type=list)
        rename_components = output_settings.value("rename_components", [], type=list)
        selected_columns = output_settings.value("selected_columns", [], type=list)
        lookup_roi = output_settings.value("lookup_roi", "")
        lookup_column = output_settings.value("lookup_column", "")
        output_settings.endGroup()

        if not csv_filename_components or not selected_columns:
            self.output_pattern_label.setText(f"Pattern '{pattern_name}': [INVALID - CSV config missing]")
            self.active_output_pattern = None
            return

        # Update label and check validity of rename components
        self.output_pattern_label.setText(f"Active Pattern: {pattern_name}")
        if rename_components:
            template_rois_lower = [roi['name'].lower() for roi in self.template_data.get('rois', [])] if self.template_data else []
            allowed_special_lower = ['year', 'date', 'yyyy', 'yy', 'mm', 'mmm', 'dd', 'hh', 'ss']
            invalid_rois = []
            for c in rename_components:
                if c.startswith("Data: "): continue
                if c.startswith('"') and c.endswith('"'): continue
                if c.lower() in allowed_special_lower: continue
                if c.lower() in template_rois_lower: continue
                invalid_rois.append(c)
            
            if invalid_rois:
                self.output_pattern_label.setText(f"Active Pattern: {pattern_name}\n[Rename part INVALID: Missing {', '.join(invalid_rois)}]")

        self.active_output_pattern = {
            'name': pattern_name,
            'csv_filename_components': csv_filename_components,
            'rename_components': rename_components,
            'selected_columns': selected_columns,
            'lookup_roi': lookup_roi,
            'lookup_column': lookup_column
        }        
        if hasattr(self, 'new_excel_filename_edit') and not self.checkbox_append_excel.isChecked():
            self.new_excel_filename_edit.setPlaceholderText(f"Using '{pattern_name}' pattern")
            self.new_excel_filename_edit.setReadOnly(True)
            self.new_excel_filename_edit.setHidden(True)

    def _init_top_panel(self):
        source_selection_frame = QFrame(); source_selection_frame.setFrameShape(QFrame.Shape.StyledPanel)
        source_selection_layout = QVBoxLayout(source_selection_frame)
        
        source_btns_row = QHBoxLayout()
        self.btn_add_images = QPushButton("Add Images")
        self.btn_add_images.clicked.connect(self._show_image_selection_dialog)
        source_btns_row.addWidget(self.btn_add_images)
        self.btn_hardware_scan = QPushButton("Hardware Scan")
        self.btn_hardware_scan.clicked.connect(self._hardware_scan)
        source_btns_row.addWidget(self.btn_hardware_scan)
        source_selection_layout.addLayout(source_btns_row)

        ans_key_selection_layout = QHBoxLayout()
        self.ans_key_label = QLabel("Answer Key:")
        ans_key_selection_layout.addWidget(self.ans_key_label)
        self.ans_key_combobox = QComboBox()
        self.ans_key_combobox.currentIndexChanged.connect(self.on_answer_key_selected)
        self.ans_key_combobox.setMinimumWidth(200)
        ans_key_selection_layout.addWidget(self.ans_key_combobox)
        self.btn_refresh_ans_keys = QPushButton("Refresh")
        ans_key_selection_layout.addWidget(self.btn_refresh_ans_keys)
        self.btn_review_keys = QPushButton("Review Keys")
        self.btn_review_keys.clicked.connect(self._review_selected_key)
        ans_key_selection_layout.addWidget(self.btn_review_keys)
        source_selection_layout.addLayout(ans_key_selection_layout)

        self.select_all_keys_checkbox = QCheckBox("Select all answer keys")
        self.select_all_keys_checkbox.toggled.connect(self._select_all_answer_keys)
        source_selection_layout.addWidget(self.select_all_keys_checkbox)

        self.ans_key_status_label = QLabel("")
        self.ans_key_status_label.setWordWrap(True)
        source_selection_layout.addWidget(self.ans_key_status_label)
        
        output_options_group = QGroupBox("Output File")
        output_options_layout = QVBoxLayout(output_options_group)

        self.checkbox_append_excel = QCheckBox("Save to specific static CSV file")
        output_options_layout.addWidget(self.checkbox_append_excel)

        # Container for the file path widgets, to be shown/hidden
        self.append_widgets_container = QWidget()
        append_layout = QHBoxLayout(self.append_widgets_container)
        append_layout.setContentsMargins(0,0,0,0)
        append_layout.addWidget(QLabel("File Path:"))
        self.output_csv_path_edit = QLineEdit()
        self.output_csv_path_edit.setReadOnly(True)
        append_layout.addWidget(self.output_csv_path_edit)
        self.btn_select_output_csv = QPushButton("Browse...")
        append_layout.addWidget(self.btn_select_output_csv)
        output_options_layout.addWidget(self.append_widgets_container)

        self.output_pattern_label = QLabel("Active Pattern: <None>")
        self.output_pattern_label.setWordWrap(True)
        output_options_layout.addWidget(self.output_pattern_label)

        self.btn_select_output_csv.clicked.connect(self._select_output_csv_file)
        self.checkbox_append_excel.toggled.connect(self._update_output_options_state)

        scan_options_frame = QFrame(); scan_options_frame.setFrameShape(QFrame.Shape.StyledPanel)
        scan_options_layout = QVBoxLayout(scan_options_frame)
                
        # Multi-Answer buttons
        multi_ans_combined_layout = QHBoxLayout()
        multi_ans_combined_layout.addWidget(QLabel("Multi-Answer Strategy:"))
                        
        self.multi_ans_group = QButtonGroup(self)
        self.radio_multi_ans_wrong = QRadioButton("Wrong")
        self.radio_multi_ans_accept_filled = QRadioButton("Accept")
        self.radio_multi_ans_larger_area = QRadioButton("Larger fill")
        self.radio_multi_ans_wrong.setChecked(True)
        self.multi_ans_group.addButton(self.radio_multi_ans_wrong)
        self.multi_ans_group.addButton(self.radio_multi_ans_accept_filled)
        self.multi_ans_group.addButton(self.radio_multi_ans_larger_area)
                        
        multi_ans_combined_layout.addWidget(self.radio_multi_ans_wrong)
        multi_ans_combined_layout.addWidget(self.radio_multi_ans_accept_filled)
        multi_ans_combined_layout.addWidget(self.radio_multi_ans_larger_area)
        multi_ans_combined_layout.addStretch()
                
        scan_options_layout.addLayout(multi_ans_combined_layout)
                
        # Scan Mode buttons
        scan_mode_combined_layout = QHBoxLayout()
        scan_mode_combined_layout.addWidget(QLabel("Scan Mode:"))
        self.scan_mode_group = QButtonGroup(self)
        self.radio_scan_manual = QRadioButton("Manual")
        self.radio_scan_auto = QRadioButton("Auto")
        self.radio_scan_auto.setChecked(True)
        self.scan_mode_group.addButton(self.radio_scan_manual)
        self.scan_mode_group.addButton(self.radio_scan_auto)
                        
        scan_mode_combined_layout.addWidget(self.radio_scan_manual)
        scan_mode_combined_layout.addWidget(self.radio_scan_auto)
        scan_mode_combined_layout.addStretch()
                
        scan_options_layout.addLayout(scan_mode_combined_layout)
        control_buttons_frame = QFrame(); control_buttons_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.control_buttons_layout = QGridLayout(control_buttons_frame)
        self.control_buttons_layout.setSpacing(4)
        self.btn_start_scan = QPushButton("Start Scan (F5)"); self.btn_start_scan.clicked.connect(self._start_scan_process)
        self.btn_skip_image = QPushButton("Skip (F7)"); self.btn_skip_image.clicked.connect(self._skip_current_image)
        self.btn_next_image = QPushButton("Next (F6)"); self.btn_next_image.clicked.connect(self._process_next_image)
        self.btn_rewrap_image = QPushButton("Re-Wrap"); self.btn_rewrap_image.clicked.connect(self._rewrap_image)
        self.btn_accept_manual_ids = QPushButton("Accept & Continue"); self.btn_accept_manual_ids.clicked.connect(self._accept_manual_ids_and_continue)
        self.btn_stop_scan = QPushButton("Stop (Esc)"); self.btn_stop_scan.setObjectName("btn_stop_scan"); self.btn_stop_scan.clicked.connect(self._stop_scan_process)
        self.control_buttons_layout.addWidget(self.btn_start_scan, 0, 0, 1, 2)
        self.control_buttons_layout.addWidget(self.btn_next_image, 1, 0)
        self.control_buttons_layout.addWidget(self.btn_skip_image, 1, 1)
        self.control_buttons_layout.addWidget(self.btn_accept_manual_ids, 2, 0)
        self.control_buttons_layout.addWidget(self.btn_rewrap_image, 2, 1)
        self.control_buttons_layout.addWidget(self.btn_stop_scan, 3, 0, 1, 2)
        for btn in [self.btn_start_scan, self.btn_skip_image, self.btn_next_image, self.btn_rewrap_image, self.btn_accept_manual_ids, self.btn_stop_scan]:
            btn.setVisible(False)

        self.btn_start_scan.setVisible(True)

        self.top_panel_layout.addWidget(source_selection_frame)
        self.top_panel_layout.addWidget(output_options_group)
        self.top_panel_layout.addWidget(scan_options_frame)
        self.top_panel_layout.addWidget(control_buttons_frame)

        self.top_panel_layout.setStretch(0, 25) 
        self.top_panel_layout.setStretch(1, 25)
        self.top_panel_layout.setStretch(2, 30)
        self.top_panel_layout.setStretch(3, 20)

    def _init_left_panel(self):
        self.override_group_box = QGroupBox("Override Identifier Values")
        self.override_group_box.setFixedHeight(140)
        
        group_box_layout = QVBoxLayout(self.override_group_box)
        group_box_layout.setContentsMargins(2, 10, 2, 2)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("override_scroll_area")
        
        self.override_widget_container = QWidget()
        self.override_layout = QFormLayout(self.override_widget_container)
        self.override_layout.setContentsMargins(5, 5, 5, 5)
        self.override_layout.setSpacing(5)
        
        scroll_area.setWidget(self.override_widget_container)
        group_box_layout.addWidget(scroll_area)
        
        self.left_panel_layout.addWidget(self.override_group_box)
        
        log_group = QGroupBox("Log")
        log_group.setObjectName("log_group_box")
        log_layout = QVBoxLayout(log_group)
        self.log_panel = QTextEdit()
        self.log_panel.setObjectName("log_panel")
        self.log_panel.setReadOnly(True)
        log_layout.addWidget(self.log_panel)
        self.log_images_tab_widget.insertTab(0, log_group, "Log")
        self.left_panel_layout.addWidget(self.log_images_tab_widget)

        self.left_panel_layout.addStretch()

    def _init_right_panel(self):
        self.show_wrapped_image_checkbox = QCheckBox("Show Wrapped Image (with settings)")
        self.show_wrapped_image_checkbox.setChecked(False)
        self.show_wrapped_image_checkbox.stateChanged.connect(self._toggle_wrapped_image_display)
        self.right_panel_layout.addWidget(self.show_wrapped_image_checkbox)
        self.right_panel_layout.addWidget(self.answers_scroll_area)

    def _toggle_wrapped_image_display(self, state):
        self.log(f"Show Wrapped Image (with settings) toggled: {bool(state)}")
        if self.warped_image is not None:
            self.rescan_with_new_parameters()

    def log(self, message):
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        if hasattr(self, 'log_panel') and self.log_panel:
            self.log_panel.append(f"[{timestamp}] {message}")
        else:
            print(f"[{timestamp}] {message}")
        logging.info(message)
        self.log_updated.emit()
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, 'zoom_in_button'): return
        view_rect = self.view.viewport().rect()
        button_size_in = self.zoom_in_button.sizeHint()
        button_size_out = self.zoom_out_button.sizeHint()
        margin = 10
        self.zoom_in_button.move(view_rect.left() + margin, view_rect.bottom() - (button_size_in.height() + button_size_out.height()) - margin * 2)
        self.zoom_out_button.move(view_rect.left() + margin, view_rect.bottom() - button_size_out.height() - margin)
    
    def zoom_in(self): self.view.scale(1.2, 1.2)
    def zoom_out(self): self.view.scale(0.8, 0.8)

    def reset_state(self, full_reset=True):
        if hasattr(self, 'scan_progress_label') and self.scan_progress_label:
            self.scan_progress_label.setText("")
        self.is_manual_corner_mode, self.manual_corners, self.corner_polygon = False, [], None
        self.homography_matrix, self.warp_matrix, self.warped_image, self.scan_results = None, None, None, None
        self.current_image, self.image_paths, self.current_image_index = None, [], -1
        self.scene.clear()
        self.image_pixmap_item = None
        self.corner_handles.clear(); self.roi_items.clear()
        if hasattr(self, 'bubble_items') and isinstance(self.bubble_items, dict):
            self.bubble_items['identifier'].clear()
            self.bubble_items['answer'].clear()
        elif hasattr(self, 'bubble_items'): # Fallback for old list structure
             self.bubble_items.clear() 
        while self.answers_layout.count():
            item = self.answers_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.identifier_widgets.clear(); self.question_widgets.clear()
        if hasattr(self, 'identifier_checkboxes'): self.identifier_checkboxes.clear()
        if full_reset:
            self.answer_key_data = []
            self.correct_answers_map = {}
            self.template_data = None
            self.current_image_processing_params = {
                'contrast': 1.0, 'brightness': 0, 'blur': 2, 'rotation': 0,
                'adaptive_c': 7, 'threshold': 0.3, 'method': 'pixel_count',
                'grayscale': False, 'transparency': 153
            }
            
    def load_image(self, path):
        self.current_image = cv2.imread(path)
        if self.current_image is None: 
            QMessageBox.critical(self, "Error", f"Could not read image: {path}")
            self.reset_state(); return
        self.display_image(self.current_image)
        self.log(f"Image loaded: {path}")

    def load_template(self, path=None):
        if self.current_image is None: self.show_toast("Please load an image first.", level='warning'); return
        dialog_key = "Load Template"
        if path is None: 
            initial_path = load_last_path(dialog_key)
            path, _ = QFileDialog.getOpenFileName(self, dialog_key, initial_path, "JSON Files (*.json)")
        if not path: return
        save_last_path(dialog_key, path)
        try:
            with open(path, 'r') as f: self.template_data = json.load(f)
            self._create_right_panel_widgets()
            self._populate_identifier_overrides()
        except Exception as e: QMessageBox.critical(self, "Error", f"Failed to load or parse template: {e}")

    def run_auto_corner_detection(self):
        self.btn_rewrap_image.setVisible(False)
        for item in self.corner_handles:
            if item.scene(): self.scene.removeItem(item)
        if self.corner_polygon and self.corner_polygon.scene(): self.scene.removeItem(self.corner_polygon)
        self.corner_handles, self.corner_polygon = [], None
        corners = self.engine.detector.find_corners(self.current_image, self.template_data.get('corner_properties', {}))
        if corners is not None and corners.any():
            return self.run_scan_process(corners=corners)
        else:
            message = "Automatic corner detection failed."
            self.log(message)
            self._pause_scan_for_manual_intervention(
                f"{message} Please click the 4 corners of the sheet or re-wrap.",
                show_accept_button=False 
            )
            self.enter_manual_corner_mode()
            return False

    def _rewrap_image(self):
        self.log("Re-wrapping image. Entering manual content area selection mode.")
        self.enter_manual_corner_mode()
    
    def enter_manual_corner_mode(self):
        self.is_manual_corner_mode = True; self.manual_corners = []
        for handle in self.corner_handles: 
            if handle.scene(): self.scene.removeItem(handle)
        self.corner_handles.clear()
        if self.current_image is not None: self.display_image(self.current_image)
        self.show_toast("Click the 4 corners of the main content area (e.g., the box surrounding all bubbles).", level='info')

    def add_manual_corner(self, point):
        if not self.is_manual_corner_mode or len(self.corner_handles) >= 4: return
        handle = CornerHandle(point.x(), point.y(), self)
        self.scene.addItem(handle); self.corner_handles.append(handle)
        if len(self.corner_handles) == 4:
            self.is_manual_corner_mode = False
            self.update_corner_polygon()
            if self.run_scan_process():
                # After manual corner selection and successful scan,
                # hide all current control buttons except "Accept & Continue" and "Skip"
                # The user should accept the manual correction.
                self.btn_next_image.setVisible(False)
                self.btn_skip_image.setVisible(True) # User can still skip manual correction
                self.btn_accept_manual_ids.setVisible(True) # User must explicitly accept
                self.btn_rewrap_image.setVisible(True)
            # No else needed, run_scan_process handles its own failures by skipping/pausing


    def update_corner_polygon(self):
        if self.corner_polygon and self.corner_polygon.scene(): self.scene.removeItem(self.corner_polygon)
        points = [handle.pos() for handle in self.corner_handles]
        if len(points) == 4: self.corner_polygon = self.scene.addPolygon(QPolygonF(points), QPen(QColor("red"), 2))

    def run_scan_process(self, corners=None):
        if corners is None and len(self.corner_handles) < 4:
            self.log("Scan process skipped: 4 corners not available.")
            if self.radio_scan_auto.isChecked():
                self._skip_current_image()
            return False
        
        try:
            box_points_relative = self.template_data.get('box_points_relative', [])
            if len(box_points_relative) != 4: raise ValueError("Template is missing 'box_points_relative'. Cannot warp content box.")
            
            # If corners are from auto-detection, they are the PAGE corners.
            if corners is not None and corners.any():
                self.log("DEBUG: Using auto-detected page corners to calculate warp.")
                page_corners = corners
                template_corners = np.array(self.template_data.get('template_corners'), dtype="float32")
                tl_corner_template = template_corners[0]
                template_box_points_abs = np.array([[p['x'] + tl_corner_template[0], p['y'] + tl_corner_template[1]] for p in box_points_relative], dtype="float32")
                
                H, _ = cv2.findHomography(template_corners, page_corners)
                if H is None: raise ValueError("Could not compute homography from page corners.")
                self.homography_matrix = H
                
                # Project the content box from the template onto the page
                new_box_points = cv2.perspectiveTransform(template_box_points_abs.reshape(-1, 1, 2), H)
                if new_box_points is None: raise ValueError("Could not project content box onto the page.")
                new_box_points = new_box_points.reshape(4, 2)

            # Else, the user has manually selected the CONTENT BOX corners.
            else:
                self.log("DEBUG: Using manually selected content box corners to calculate warp.")
                new_box_points = np.array([(h.pos().x(), h.pos().y()) for h in self.corner_handles], dtype="float32")
                # Set homography to None to signal that we are in a direct-to-box manual mode.
                self.homography_matrix = None

            warped_image, warp_matrix = self.engine.four_point_transform(self.current_image, new_box_points)
            if warped_image is None: raise ValueError("Failed to warp the content box.")
            
            self.warped_image, self.warp_matrix = warped_image, warp_matrix
            self.scan_results = None # Ensure a fresh scan

            # If this was a manual re-wrap (signaled by no homography), we must reset the 
            # scene geometry to the new warped image before drawing ROIs on it.
            if self.homography_matrix is None:
                self.display_image(self.warped_image)

            self.rescan_with_new_parameters()
            return True
        except Exception as e: 
            message = f"An error occurred during scanning:\n{e}"
            self.log(f"Processing Error: {e}")
            self._pause_scan_for_manual_intervention(message + "\nPlease skip or re-wrap.", show_accept_button=False)
            return False

    def _pause_scan_for_manual_intervention(self, message, show_accept_button=True):
        self.is_scan_stopped = True # This will halt the auto-scan loop
        self.show_toast(message, level='error', duration=5000)

        # Update button visibility to allow for manual correction
        self.btn_stop_scan.setVisible(True) # Can always stop
        self.btn_start_scan.setVisible(False)
        self.btn_next_image.setVisible(False)

        self.btn_skip_image.setVisible(True)
        self.btn_rewrap_image.setVisible(True)
        self.btn_accept_manual_ids.setVisible(show_accept_button)

    def _get_processed_preview_image(self, image, params):
        if image is None: return None
        processed = image.copy()
        processed = cv2.addWeighted(processed, params.get('contrast', 1.0), np.zeros(processed.shape, processed.dtype), 0, params.get('brightness', 0))
        if params.get('grayscale', False):
            if len(processed.shape) == 3: processed = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
        if (b := params.get('blur', 0)) > 0: 
            if (k := b * 2 + 1) > 1: processed = cv2.GaussianBlur(processed, (k, k), 0)
        if len(processed.shape) == 2: processed = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
        if (r := params.get('rotation', 0)) != 0:
            h, w = processed.shape[:2]; M = cv2.getRotationMatrix2D((w // 2, h // 2), r, 1.0)
            processed = cv2.warpAffine(processed, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return processed

    def rescan_with_new_parameters(self, _=None):
        if self.warped_image is None or self.template_data is None: return
        try:
            params = self.get_current_params()
            preview_image = self._get_processed_preview_image(self.warped_image, params)
            if preview_image is None: self.log("Preview image generation failed."); return

            for item_group in self.roi_items:
                for item in item_group:
                    if item and item.scene(): self.scene.removeItem(item)
            self.roi_items.clear()
            display_image = preview_image if self.show_wrapped_image_checkbox.isChecked() else self.warped_image
            h, w, ch = display_image.shape
            qt_image = QImage(cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB).data, w, h, ch * w, QImage.Format.Format_RGB888)
            if self.image_pixmap_item and self.image_pixmap_item.scene():
                self.image_pixmap_item.setPixmap(QPixmap.fromImage(qt_image))
            else:
                self.image_pixmap_item = self.scene.addPixmap(QPixmap.fromImage(qt_image))
            self.image_pixmap_item.setZValue(0) # Ensure image is at the bottom
            self._draw_template_on_scene(preview_image, draw_rois=True)
            # If this is the first scan, we need to scan for identifiers first
            if self.scan_results is None:
                self._scan_scene_grid(preview_image, params, scan_type='identifiers')

            # Identifiers are NOT re-scanned, to preserve manual edits.
            # We use the existing values in self.scan_results['identifiers']
            matching_key = self._find_matching_answer_key()
            if matching_key:
                self.correct_answers_map = matching_key['answers']
                self.current_matched_key_path = matching_key['path']
                self.log(f"Applied matching answer key: {os.path.basename(matching_key['path'])}")
            else:
                self.log("ERROR: No matching answer key found. Cannot determine bubble colors or score.")
                self.correct_answers_map = {}
                self.current_matched_key_path = "Not Found"

            self._scan_scene_grid(preview_image, params, scan_type='answers', clear_existing_bubbles=True)
            self._update_widgets_from_scan()
        except Exception as e: 
            self.log(f"Re-Scan Error: {str(e)}")
            QMessageBox.critical(self, "Re-Scan Error", f"An error occurred during re-scan:\n{str(e)}")
    
    def get_current_params(self):
        multi_ans_strategy = "wrong"
        if self.radio_multi_ans_accept_filled.isChecked(): multi_ans_strategy = "accept_if_filled"
        elif self.radio_multi_ans_larger_area.isChecked(): multi_ans_strategy = "larger_area"
        params = self.current_image_processing_params.copy()
        params['multi_ans_strategy'] = multi_ans_strategy
        return params

    def _get_target_rois(self):
        if not self.template_data: return []
        return self.template_data.get('rois', [])

    def _draw_template_on_scene(self, image_to_draw_on, draw_rois=True):
        if not draw_rois or not self.template_data or image_to_draw_on is None: return

        target_rois = self._get_target_rois()

        # Manual Mode: The warped image is the content box. ROIs are drawn relative to its top-left, but scaled to fit.
        if self.homography_matrix is None:
            self.log("DEBUG: Drawing ROIs in manual (direct-to-content-box) mode.")
            try:
                # 1. Get dimensions of the destination warped image
                h_warped, w_warped = image_to_draw_on.shape[:2]
                if w_warped == 0 or h_warped == 0:
                    self.log("ERROR: Warped image has zero dimensions. Cannot draw ROIs.")
                    return

                # 2. Get dimensions of the source content box from the template
                box_points_relative = self.template_data.get('box_points_relative', [])
                if not box_points_relative:
                    self.log("ERROR: Template is missing 'box_points_relative'.")
                    return
                
                # Defensively create numpy array from list of dicts or list of lists
                template_box_pts_list = [[p['x'], p['y']] if isinstance(p, dict) else p for p in box_points_relative]
                
                # Re-order the points to be consistent: top-left, top-right, bottom-right, bottom-left
                rect = np.zeros((4, 2), dtype="float32")
                s = np.array(template_box_pts_list).sum(axis=1)
                rect[0] = template_box_pts_list[np.argmin(s)]
                rect[2] = template_box_pts_list[np.argmax(s)]
                diff = np.diff(np.array(template_box_pts_list), axis=1)
                rect[1] = template_box_pts_list[np.argmin(diff)]
                rect[3] = template_box_pts_list[np.argmax(diff)]
                (tl, tr, br, bl) = rect

                # Calculate perspective-aware width and height, matching the four_point_transform logic
                widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
                widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
                template_w = max(int(widthA), int(widthB))

                heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
                heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
                template_h = max(int(heightA), int(heightB))

                if template_w == 0 or template_h == 0:
                    self.log("ERROR: Template content box has zero area. Cannot calculate scale.")
                    return

                # 3. Calculate scaling factors
                scale_x = w_warped / template_w
                scale_y = h_warped / template_h
                self.log(f"DEBUG: Manual warp scaling factors: x={scale_x:.2f}, y={scale_y:.2f}")

                # 4. Defensively get Page and Box Origins based on user's formula
                page_origin_x, page_origin_y = 0, 0 # Keep for defensive coding, though not used in combined_origin
                template_corners = self.template_data.get('template_corners', [])
                if template_corners:
                    first_corner = template_corners[0]
                    if isinstance(first_corner, dict):
                        page_origin_x, page_origin_y = first_corner.get('x', 0), first_corner.get('y', 0)
                    elif isinstance(first_corner, (list, tuple)) and len(first_corner) >= 2:
                        page_origin_x, page_origin_y = first_corner[0], first_corner[1]

                box_origin_x, box_origin_y = 0, 0
                if box_points_relative:
                    first_box_corner = box_points_relative[0]
                    if isinstance(first_box_corner, dict):
                        box_origin_x, box_origin_y = first_box_corner.get('x', 0), first_box_corner.get('y', 0)
                    elif isinstance(first_box_corner, (list, tuple)) and len(first_box_corner) >= 2:
                        box_origin_x, box_origin_y = first_box_corner[0], first_box_corner[1]
                
                # Simplified combined_origin based on assuming box_points_relative are absolute to template origin
                combined_origin_x = page_origin_x + box_origin_x
                combined_origin_y = page_origin_y + box_origin_y
                self.log(f"DEBUG: Using combined origin offset: x={combined_origin_x}, y={combined_origin_y}")

                for roi_data in target_rois:
                    # 5. Calculate ROI position relative to the combined origins
                    relative_x = roi_data['x'] - combined_origin_x
                    relative_y = roi_data['y'] - combined_origin_y

                    # 6. Apply scaling to position and size
                    scaled_x = relative_x * scale_x
                    scaled_y = relative_y * scale_y
                    scaled_w = roi_data['width'] * scale_x
                    scaled_h = roi_data['height'] * scale_y
                    
                    rect = QRectF(scaled_x, scaled_y, scaled_w, scaled_h)
                    rect_item = self.scene.addRect(rect, QPen(QColor("cyan"), 2))
                    rect_item.setZValue(1)
                    text_item = self.scene.addText(roi_data['name']); text_item.setPos(rect.topLeft() - QPointF(0, 10)); text_item.setDefaultTextColor(QColor("cyan"))
                    text_item.setZValue(1)
                    grid_lines = self._draw_roi_grid(roi_data, rect)
                    self.roi_items.append([rect_item, text_item] + grid_lines)

            except (KeyError, IndexError, cv2.error) as e:
                self.log(f"ERROR: Could not draw ROIs in manual mode. Error: {e}")
                return
        
        # Auto Mode: Use the combined matrix to project ROIs from template space to warped image space.
        else:
            if self.warp_matrix is None: 
                self.log("DEBUG: Skipping ROI drawing in auto mode, warp_matrix is missing.")
                return
            
            self.log("DEBUG: Drawing ROIs in automatic (homography) mode.")
            combined_matrix = self.warp_matrix @ self.homography_matrix
            for i, roi_data in enumerate(target_rois):
                roi_corners = np.array([[roi_data['x'], roi_data['y']], [roi_data['x'] + roi_data['width'], roi_data['y']], [roi_data['x'] + roi_data['width'], roi_data['y'] + roi_data['height']], [roi_data['x'], roi_data['y'] + roi_data['height']]], dtype=np.float32)
                final_roi_in_warp = cv2.perspectiveTransform(roi_corners.reshape(-1, 1, 2), combined_matrix)
                if final_roi_in_warp is None:
                    self.log(f"Warning: Could not transform ROI '{roi_data.get('name')}' for drawing.")
                    continue
                x, y, w, h = cv2.boundingRect(final_roi_in_warp)
                rect = QRectF(x, y, w, h)
                rect_item = self.scene.addRect(rect, QPen(QColor("cyan"), 2))
                rect_item.setZValue(1) # ROIs below bubbles
                text_item = self.scene.addText(roi_data['name']); text_item.setPos(rect.topLeft() - QPointF(0, 10)); text_item.setDefaultTextColor(QColor("cyan"))
                text_item.setZValue(1) # ROIs below bubbles
                grid_lines = self._draw_roi_grid(roi_data, rect)
                self.roi_items.append([rect_item, text_item] + grid_lines)

    def _draw_roi_grid(self, roi_data, rect):
        grid_lines, grid_pen = [], QPen(QColor("blue"), 1, Qt.PenStyle.DotLine)
        try:
            rows, cols = (int(roi_data.get(k, 0)) for k in (['rows', 'cols'] if roi_data.get('type') == 'Identifier' else ['questions', 'options']))
            if rows > 1:
                for i in range(1, rows): y_pos = rect.y() + i * (rect.height() / rows); grid_lines.append(self.scene.addLine(rect.left(), y_pos, rect.right(), y_pos, grid_pen))
            if cols > 1:
                for i in range(1, cols): x_pos = rect.x() + i * (rect.width() / cols); grid_lines.append(self.scene.addLine(x_pos, rect.top(), x_pos, rect.bottom(), grid_pen))
        except (ValueError, KeyError): pass
        return grid_lines

    def _scan_scene_grid(self, image_to_scan, params, scan_type='all', clear_existing_bubbles=True):
        if image_to_scan is None or not self.template_data: return

        # Initialize bubble items dictionary if it's not one
        if not hasattr(self, 'bubble_items') or not isinstance(self.bubble_items, dict):
            self.bubble_items = {'identifier': [], 'answer': []}

        if scan_type in ['all', 'identifiers']: self.scan_results = {'identifiers': {}, 'answers': {}, 'errors': {}, 'warnings': {}}
        elif scan_type == 'answers':
            self.scan_results['answers'].clear(); self.scan_results['errors'] = {k:v for k,v in self.scan_results.get('errors', {}).items() if not k.startswith('Q')}
        
        all_filled_bubbles_info = []
        for i, roi_data in enumerate(self._get_target_rois()):
            if (scan_type == 'identifiers' and roi_data.get('type') not in ['Identifier', 'qrcode']) or \
               (scan_type == 'answers' and roi_data.get('type') != 'Answer'): continue
            if i >= len(self.roi_items): self.log(f"Warning: ROI item mismatch for '{roi_data.get('name')}'."); continue
            rect = self.roi_items[i][0].rect()
            if rect.width() <= 0 or rect.height() <= 0: continue
            roi_image = image_to_scan[int(rect.y()):int(rect.y()+rect.height()), int(rect.x()):int(rect.x()+rect.width())]
            roi_name = roi_data.get('name', f'roi_{i}')

            # --- NEW: Handle Identifier Overrides ---
            if roi_data.get('type') == 'Identifier' and roi_name in self.identifier_override_widgets:
                override_widget = self.identifier_override_widgets[roi_name]
                override_value = ""
                if isinstance(override_widget, QLineEdit):
                    override_value = override_widget.text().strip()
                elif isinstance(override_widget, QComboBox):
                    override_value = override_widget.currentText().strip()

                if override_value:
                    # If there's an override value, use it and skip scanning this ROI
                    self.scan_results['identifiers'][roi_name] = override_value
                    self.log(f"Used override value '{override_value}' for identifier '{roi_name}'.")
                    # Clear any bubbles that might have been drawn from a previous non-override scan
                    for item in self.bubble_items.get('identifier', []):
                        if item.scene():
                            self.scene.removeItem(item)
                    self.bubble_items['identifier'].clear()
                    continue
            # --- END NEW ---

            if roi_data.get('type') == 'qrcode': self.scan_results['identifiers'][roi_name] = self.engine.read_qr(roi_image); continue
            try:
                rows, cols = (int(roi_data.get(k,0)) for k in (['rows', 'cols'] if 'rows' in roi_data else ['questions', 'options']))
                if rows == 0 or cols == 0: continue
            except (ValueError, KeyError): self.scan_results['errors'][roi_name] = "Invalid grid dimensions."; continue
            metric_matrix, all_coords = self.engine._process_grid(roi_image, rows, cols, params)
            if not metric_matrix: self.scan_results['errors'][roi_name] = "Failed to process grid."; continue
            matrix = [[(1 if metric > params.get('threshold', 0.3) else 0) for metric in row] for row in metric_matrix]
            
            if roi_data['type'] == 'Answer':
                start_q, options_map = roi_data.get('start_question', 1), roi_data.get('values', [chr(ord('A') + i) for i in range(cols)])
                strategy = params.get('multi_ans_strategy', 'wrong')

                for r_idx in range(rows):
                    q_num_str = str(start_q + r_idx)
                    detected_options = []
                    correct_options = self.correct_answers_map.get(q_num_str, [])
                    
                    row_metrics = metric_matrix[r_idx]
                    filled_indices = [c for c, m in enumerate(row_metrics) if m > params.get('threshold', 0.3)]

                    # --- Strategy Implementation ---
                    final_indices = filled_indices
                    if strategy == "larger_area" and len(filled_indices) > 1:
                        # Pick only the one with the maximum metric
                        max_idx = filled_indices[0]
                        max_val = row_metrics[max_idx]
                        for idx in filled_indices[1:]:
                            if row_metrics[idx] > max_val:
                                max_val = row_metrics[idx]
                                max_idx = idx
                        final_indices = [max_idx]
                        self.log(f"DEBUG: Q{q_num_str} | Larger Area strategy picked bubble {options_map[max_idx]} ({max_val:.2f})")

                    for c_idx in final_indices:
                        if c_idx >= len(options_map):
                            option_char = "?"
                        else:
                            option_char = options_map[c_idx]
                        detected_options.append(option_char)
                        
                        if (coord_index := r_idx * cols + c_idx) < len(all_coords):
                            bubble = all_coords[coord_index]
                            bubble_coords = (bubble[0] + rect.x(), bubble[1] + rect.y(), bubble[2] + rect.x(), bubble[3] + rect.y())
                            all_filled_bubbles_info.append({
                                'coords': bubble_coords, 
                                'status': 'correct' if option_char in correct_options else 'incorrect', 
                                'roi_type': 'Answer'
                            })

                    self.scan_results['answers'][q_num_str] = detected_options
                    if len(detected_options) > 1 and strategy == "wrong":
                        self.scan_results['errors'][f'Q{q_num_str}'] = "Multiple answers"
                        self.log(f"WARNING: Q{q_num_str} | Multiple answers detected under 'Wrong' strategy: {detected_options}")
                    
                    if not detected_options:
                        self.scan_results['errors'][f'Q{q_num_str}'] = "No answer detected"

            elif roi_data['type'] == 'Identifier':
                for r_idx in range(rows):
                    for c_idx, is_filled in enumerate(matrix[r_idx]):
                        if not is_filled: continue
                        if (coord_index := r_idx * cols + c_idx) < len(all_coords):
                            bubble = all_coords[coord_index]
                            bubble_coords = (bubble[0] + rect.x(), bubble[1] + rect.y(), bubble[2] + rect.x(), bubble[3] + rect.y())
                            all_filled_bubbles_info.append({'coords': bubble_coords, 'status': 'identifier', 'roi_type': 'Identifier'})
                
                value = ""
                if roi_data.get('order') == 'Column Wise':
                    for c in range(cols):
                        col_metrics = [metric_matrix[r][c] for r in range(rows)]
                        filled_indices = [r for r, metric in enumerate(col_metrics) if metric > params.get('threshold', 0.3)]
                        char_val = ""
                        if len(filled_indices) == 0:
                            char_val = "_"
                            # Highlight the empty column
                            col_width = rect.width() / cols
                            col_x = rect.x() + c * col_width
                            col_rect_coords = (col_x, rect.y(), col_x + col_width, rect.y() + rect.height())
                            all_filled_bubbles_info.append({'coords': col_rect_coords, 'status': 'highlight', 'roi_type': 'Identifier'})
                        elif len(filled_indices) == 1:
                            char_val = roi_data.get('values', [])[filled_indices[0]] if filled_indices[0] < len(roi_data.get('values', [])) else "ERR"
                        else:
                            char_val = "*"
                        value += char_val
                if value: 
                    self.scan_results['identifiers'][roi_name] = value
                    if "ERR" in value or "*" in value: self.scan_results['errors'][roi_name] = f"Scan error ({value})"
                    elif "_" in value: self.scan_results['warnings'][roi_name] = "Empty/Not found"

        # --- NEW BUBBLE MANAGEMENT LOGIC ---
        lists_to_clear = []
        if scan_type == 'all': lists_to_clear.extend(['identifier', 'answer'])
        elif scan_type == 'identifiers': lists_to_clear.append('identifier')
        elif scan_type == 'answers': lists_to_clear.append('answer')

        if clear_existing_bubbles:
            for bubble_type in lists_to_clear:
                for item in self.bubble_items[bubble_type]:
                    if item.scene(): self.scene.removeItem(item)
                self.bubble_items[bubble_type].clear()

        alpha = params.get('transparency', 143)
        brushes = {
            'correct': QBrush(QColor(0, 255, 0, alpha)), 
            'incorrect': QBrush(QColor(255, 0, 0, alpha)), 
            'empty': QBrush(QColor(255, 165, 0, alpha)),
            'identifier': QBrush(QColor(0, 100, 255, alpha)),
            'highlight': QBrush(QColor(255, 165, 0, 80))
        }
        pen = QPen(Qt.PenStyle.NoPen)
        
        for info in all_filled_bubbles_info:
            x1, y1, x2, y2 = info['coords']
            # Use 'status' for brush, but default to 'incorrect' if not found
            brush = brushes.get(info.get('status'), brushes['incorrect'])
            item = self.scene.addRect(x1, y1, x2-x1, y2-y1, pen, brush)
            
            roi_type = info.get('roi_type')
            if roi_type == 'Identifier':
                self.bubble_items['identifier'].append(item)
            elif roi_type == 'Answer':
                self.bubble_items['answer'].append(item)
                      
    def _handle_mismatch_dialog(self, match_result):
        if self.remembered_mismatch_choice:
            choice = self.remembered_mismatch_choice
            self.log(f"DEBUG: Applying remembered mismatch choice: {choice}")
        else:
            dialog = MismatchAcceptDialog(match_result["mismatched_data"], self)
            apply_stylesheet_and_floatation(dialog)
            choice = dialog.exec()

            if dialog.is_remember_checked():
                # Do not remember "Manual Edit" or "Cancel"
                if choice in [QDialogButtonBox.StandardButton.Yes, QDialogButtonBox.StandardButton.Apply]:
                    self.remembered_mismatch_choice = choice
                    self.log(f"DEBUG: Mismatch choice {choice} will be remembered for this session.")

        if choice == QDialogButtonBox.StandardButton.Yes: # Accept Scanned
            self.log("DEBUG: User accepted mismatched scanned data. Continuing scan.")
            return 'PASS'
        
        elif choice == QDialogButtonBox.StandardButton.Apply: # Use Expected
            self.log("DEBUG: User chose to use expected values from database.")
            for item in match_result["mismatched_data"]:
                roi_name = item['roi']
                expected_value = item['expected']
                self.log(f"DEBUG: Updating UI for '{roi_name}' with expected value '{expected_value}'.")
                self._update_identifier_widget_value(roi_name, expected_value)
            # The values in self.scan_results have been updated.
            # Returning 'RESCAN' will trigger a re-validation.
            return 'RESCAN'
                    
        elif choice == QDialogButtonBox.StandardButton.Edit: # Manual Edit
            self.log("DEBUG: User chose to manually edit mismatched data. Pausing.")
            self._pause_scan_for_manual_intervention(
                "Primary match found, but secondary data mismatched. Please correct the values, accept, or skip.",
                show_accept_button=True
            )
            return 'PAUSE'
                                
        else: # Cancel
            self.log("DEBUG: Mismatch dialog cancelled. Skipping image.")
            self._skip_current_image()
            return 'SKIP'

    def _create_right_panel_widgets(self):
        while self.answers_layout.count():
            item = self.answers_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
                item.layout().deleteLater()
        self.identifier_widgets.clear(); self.question_widgets.clear()
        target_rois = self._get_target_rois()
        id_group = QGroupBox("Identifiers"); id_layout = QVBoxLayout(id_group)
        id_layout.setSpacing(0); id_layout.setContentsMargins(0,0,0,0)
        self.answers_layout.addWidget(id_group)
        for roi_data in [r for r in target_rois if r.get('type') in ['Identifier', 'qrcode']]:
            name, subtype = roi_data.get('name'), roi_data.get('subtype', '')
            is_single_choice = (int(roi_data.get('rows', 0)) == 1 or int(roi_data.get('cols', 0)) == 1) and roi_data.get('values')
            widget = IdentifierDropdownWidget(name, subtype, roi_data.get('values', []), "", self) if is_single_choice else IdentifierEditWidget(name, subtype, "", self)
            if isinstance(widget, IdentifierDropdownWidget): widget.combo_box.currentTextChanged.connect(self._update_identifier_from_dropdown)
            else: widget.value_edit.textChanged.connect(self._update_identifier)
            id_layout.addWidget(widget); self.identifier_widgets[name] = widget
        id_layout.addStretch()
        ans_group = QGroupBox("Answer Key"); ans_layout = QVBoxLayout(ans_group)
        ans_layout.setSpacing(0)
        self.answers_layout.addWidget(ans_group)
        answer_rois = [r for r in target_rois if r.get('type') == 'Answer']
        if answer_rois:
            question_to_roi_map, total_questions = {}, 0
            for r in answer_rois:
                try:
                    start_q, num_q = int(r.get('start_question', 1)), int(r.get('rows', 0))
                    for i in range(num_q):
                        q_num = start_q + i; question_to_roi_map[q_num] = r
                        if q_num > total_questions: total_questions = q_num
                except (ValueError, TypeError): self.log(f"Warning: Invalid 'start_question' or 'rows' for ROI '{r.get('name')}'."); continue
            for q_num in range(1, total_questions + 1):
                roi_data = question_to_roi_map.get(q_num); opts = []
                if roi_data:
                    try: opts = roi_data.get('values', [chr(ord('A') + i) for i in range(int(roi_data.get('cols', 0)))])
                    except (ValueError, TypeError): pass
                widget = QuestionAnswerWidget(str(q_num), opts, [], self.panel_text_color, self.get_current_params().get('multi_ans_strategy', 'wrong'))
                widget.option_group.buttonClicked.connect(self._update_answer)
                ans_layout.addWidget(widget); self.question_widgets[str(q_num)] = widget

    def _update_widgets_from_scan(self):
        if not self.scan_results:
            self.log("No scan results to display.")
            return

        for name, widget in self.identifier_widgets.items():
            value = self.scan_results.get('identifiers', {}).get(name, "")

            # Block signals to prevent recursive update loops
            if isinstance(widget, IdentifierDropdownWidget):
                widget.combo_box.blockSignals(True)
                if value in [widget.combo_box.itemText(i) for i in range(widget.combo_box.count())]:
                    widget.combo_box.setCurrentText(value)
                else:
                    widget.combo_box.setCurrentIndex(-1)
                widget.combo_box.blockSignals(False)
            elif isinstance(widget, IdentifierEditWidget):
                widget.value_edit.blockSignals(True)
                widget.value_edit.setText(str(value))
                widget.value_edit.blockSignals(False)

            # Set visual feedback for the identifier's status
            if name in self.scan_results.get('errors', {}):
                bg_color = QColor("#f8d7da")
                text_color_str = "black" # Use black text for light backgrounds
                widget.setStyleSheet(f"background-color: {bg_color.name()}; color: {text_color_str};")
                widget.setToolTip(self.scan_results['errors'][name])
            elif name in self.scan_results.get('warnings', {}):
                bg_color = QColor("#ffecb3")
                text_color_str = "black" # Use black text for light backgrounds
                widget.setStyleSheet(f"background-color: {bg_color.name()}; color: {text_color_str};")
                widget.setToolTip(self.scan_results['warnings'][name])
            else:
                if value:
                    bg_color = QColor("#d4edda")
                    text_color_str = "black" # Use black text for light backgrounds
                    widget.setStyleSheet(f"background-color: {bg_color.name()}; color: {text_color_str};")
                    widget.setToolTip("Scanned value")
                else:
                    widget.setStyleSheet("")
                    widget.setToolTip("")

        for q_num_str, widget in self.question_widgets.items():
            widget.option_group.blockSignals(True)
            selected_answers = self.scan_results.get('answers', {}).get(q_num_str, [])
            for button in widget.option_group.buttons():
                button.setChecked(button.text() in selected_answers)
            widget.option_group.blockSignals(False)

        self._calculate_and_update_score()
        self._update_output_preview()

    def _get_current_aggregated_data(self):
        """
        Gathers all current data from UI widgets, performs student matching,
        calculates scores, and returns a unified dictionary of all data.
        This is the single source of truth for UI previews and CSV saving.
        """
        if not self.template_data:
            return None, {}

        # 1. Gather current identifiers from UI widgets (ensures manual overrides are used)
        current_ids = {
            name: self._format_identifier(name, widget.combo_box.currentText() if isinstance(widget, IdentifierDropdownWidget) else widget.value_edit.text())
            for name, widget in self.identifier_widgets.items()
        }

        # 2. Gather current answers from UI widgets (ensures manual toggles are used)
        current_answers = {
            q: [b.text() for b in w.option_group.buttons() if b.isChecked()]
            for q, w in self.question_widgets.items()
        }

        # 3. Perform student info lookup
        match_result = self._get_student_info(current_ids)
        student_info_data = match_result.pop("student_info", {}) or {}
        # student_info_result contains matching status, reason, etc.

        # 4. Calculate score and correctness
        correct_count, score, total_expected, answered = 0, 0, 0, 0
        for q_num in self.question_widgets:
            correct_answers = self.correct_answers_map.get(q_num, [])
            if correct_answers:
                total_expected += 1
            
            detected = current_answers.get(q_num, [])
            is_correct = False
            points = 0.0

            if detected:
                answered += 1
                correct_mark, wrong_mark = self._get_marking_rules(q_num)
                # Subset rule: Any mark is correct as long as ALL marks are in the key
                if set(detected).issubset(set(correct_answers)):
                    is_correct = True
                    correct_count += 1
                    points = correct_mark
                else:
                    is_correct = False
                    points = wrong_mark
                
                score += points
                self.log(f"DEBUG (Scoring): Q{q_num} | Strat: {self.get_current_params().get('multi_ans_strategy')} | Student: {detected} | Key: {correct_answers} | Match: {'YES' if is_correct else 'NO'} | Points: {points}")
            else:
                self.log(f"DEBUG (Scoring): Q{q_num} | Strat: {self.get_current_params().get('multi_ans_strategy')} | No answer detected | Key: {correct_answers} | Points: 0.0")

        # 5. Aggregate all data
        now = datetime.datetime.now()
        scan_data = {
            'Timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
            'Image_Path': self.image_paths[self.current_image_index] if (0 <= self.current_image_index < len(self.image_paths)) else "N/A",
            **current_ids,
            'Score': score,
            'Correct': correct_count,
            'Unanswered': max(0, total_expected - answered),
            'Total_Questions': total_expected
        }
        
        # Combine student info, matching results (status/reason), and scan data
        all_data = {**match_result, **student_info_data, **scan_data}

        # 6. Add per-question data and correctness status
        for q_num in sorted(current_answers.keys(), key=int):
            detected_opts = current_answers.get(q_num, [])
            is_correct = False
            if detected_opts:
                is_correct = set(detected_opts).issubset(set(self.correct_answers_map.get(q_num, [])))
            
            all_data[f'Q{q_num}'] = ", ".join(detected_opts) if detected_opts else "Unanswered"
            all_data[f'Q{q_num}_Correct'] = 'Yes' if is_correct else 'No'

        # Special handling for advanced matching primary key
        if self.active_matching_rule:
            primary_roi_name = self.active_matching_rule["primary_match"]["roi_name"]
            primary_excel_col = self.active_matching_rule["primary_match"]["excel_column"]
            accepted_primary_value = current_ids.get(primary_roi_name)
            if accepted_primary_value:
                all_data[primary_roi_name] = accepted_primary_value
                all_data[primary_excel_col] = accepted_primary_value

        return all_data, current_answers

    def _calculate_and_update_score(self):
        all_data, _ = self._get_current_aggregated_data()
        if not all_data:
            self.score_label.setText("Score: N/A; Correct: N/A; Unanswered: N/A")
            return
        
        score = all_data.get('Score', 0)
        correct_count = all_data.get('Correct', 0)
        unanswered = all_data.get('Unanswered', 0)
        total_expected = all_data.get('Total_Questions', 0)
        
        self.score_label.setText(f"Score: {score}; Correct: {correct_count}; Unanswered: {unanswered}/{total_expected}")

    def _get_marking_rules(self, q_num):
        """Returns (correct_mark, wrong_mark) for a given question number from template data."""
        try:
            q_idx = int(q_num)
            for roi in self.template_data.get('rois', []):
                if roi.get('type') == 'Answer':
                    start_q = int(roi.get('start_question', 1))
                    num_q = int(roi.get('rows', 0))
                    if start_q <= q_idx < start_q + num_q:
                        c_mark = float(roi.get('correct_mark', 1.0))
                        w_mark = float(roi.get('wrong_mark', 0.0))
                        return c_mark, w_mark
        except (ValueError, TypeError):
            pass
        return 1.0, 0.0

    def _update_output_preview(self):
        try:
            all_data, current_answers = self._get_current_aggregated_data()
            if not all_data:
                self.result_preview_table.setColumnCount(0)
                return

            if not self.active_output_pattern:
                self.result_preview_table.setColumnCount(1)
                self.result_preview_table.setHorizontalHeaderLabels(["Status"])
                self.result_preview_table.setItem(0, 0, QTableWidgetItem("No output pattern selected."))
                return

            selected_columns = self.active_output_pattern.get('selected_columns', [])
            headers = []
            values = []

            for col_name in selected_columns:
                if col_name == "Student Answers (per question)":
                    for q_num in sorted(current_answers.keys(), key=int):
                        headers.append(f"Q{q_num}")
                        values.append(str(all_data.get(f"Q{q_num}", "")))
                elif col_name == "Correctness Status (per question)":
                    for q_num in sorted(current_answers.keys(), key=int):
                        headers.append(f"Q{q_num}✓")
                        values.append(str(all_data.get(f"Q{q_num}_Correct", "")))
                elif col_name in all_data:
                    headers.append(col_name)
                    values.append(str(all_data.get(col_name, "")))

            self.result_preview_table.setColumnCount(len(headers))
            self.result_preview_table.setHorizontalHeaderLabels(headers)
            for i, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.result_preview_table.setItem(0, i, item)

        except Exception as e:
            self.log(f"ERROR: Exception in _update_output_preview: {str(e)}")
            self.result_preview_table.setColumnCount(1)
            self.result_preview_table.setHorizontalHeaderLabels(["Error"])
            self.result_preview_table.setItem(0, 0, QTableWidgetItem(str(e)))

    def _update_identifier_widget_value(self, roi_name, new_value):
        """Updates the UI widget for the given ROI name with the new value."""
        if roi_name in self.identifier_widgets:
            widget = self.identifier_widgets[roi_name]
            if isinstance(widget, IdentifierDropdownWidget):
                widget.combo_box.blockSignals(True)
                # If the new value is not in the dropdown, add it.
                if widget.combo_box.findText(str(new_value)) == -1:
                    widget.combo_box.addItem(str(new_value))
                widget.combo_box.setCurrentText(str(new_value))
                widget.combo_box.blockSignals(False)
            elif isinstance(widget, IdentifierEditWidget):
                widget.value_edit.blockSignals(True)
                widget.value_edit.setText(str(new_value))
                widget.value_edit.blockSignals(False)
            
            # Also update the scanned_ids in self.scan_results
            if self.scan_results and 'identifiers' in self.scan_results:
                self.scan_results['identifiers'][roi_name] = new_value
            self.log(f"DEBUG: Updated UI identifier '{roi_name}' to '{new_value}'.")

    def _handle_manual_correction(self, primary_roi_name, current_primary_id):
        """Opens a dialog for manual correction of the primary ID and processes the result."""
        dialog = ManualCorrectionDialog(current_primary_id, primary_roi_name, self)
        apply_stylesheet_and_floatation(dialog)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.get_new_primary_id()
            self.log(f"DEBUG: User manually corrected '{primary_roi_name}' to '{new_id}'.")
            self._update_identifier_widget_value(primary_roi_name, new_id)
            # After manual correction, we need to re-evaluate the student info
            # This is effectively a re-scan of the identifiers, but the UI has been updated
            # The next call to _validate_and_pause_if_needed will use this new value.
            # We explicitly trigger a rescan to update the student_info_for_output
            self._live_rescan_from_identifiers() # This also updates student_info_for_output indirectly
            return 'PASS'
        else:
            self.log("DEBUG: Manual correction dialog cancelled, pausing scan.")
            self._pause_scan_for_manual_intervention("Manual correction cancelled. Please correct the value, accept, or skip.", show_accept_button=True)
            return 'PAUSE'

    def _live_rescan_from_identifiers(self):
        """
        Triggered on identifier change. Finds the matching key, rescans answers, and updates the UI.
        """
        if self.warped_image is None or not self.scan_results:
            return

        self.log("Identifier changed, attempting live re-evaluation...")
        matching_key = self._find_matching_answer_key()

        if not matching_key:
            self.log("No matching answer key for current identifiers.")
            self.correct_answers_map = {}
        else:
            self.correct_answers_map = matching_key['answers']
            self.log(f"Live-applying matching answer key: {os.path.basename(matching_key['path'])}")

        params = self.get_current_params()
        preview_image = self._get_processed_preview_image(self.warped_image, params)
        if preview_image is not None:
            self._scan_scene_grid(preview_image, params, scan_type='answers', clear_existing_bubbles=True)
            self._update_widgets_from_scan()
        else:
            self.log("Could not generate preview image for answer re-scan.")

    def _update_identifier(self):
        sender = self.sender()
        if sender and (widget := sender.parent()) and isinstance(widget, IdentifierEditWidget):
            if self.scan_results:
                 self.scan_results['identifiers'][widget.roi_name] = widget.value_edit.text()
                 # Clear errors/warnings for this manually updated identifier
                 if widget.roi_name in self.scan_results.get('errors', {}):
                     del self.scan_results['errors'][widget.roi_name]
                 if widget.roi_name in self.scan_results.get('warnings', {}):
                     del self.scan_results['warnings'][widget.roi_name]
            widget.setStyleSheet("background-color: #d4edda;") # Indicate successful manual override
            self.identifier_input_timer.start() # Debounce the live rescan

    def _update_identifier_from_dropdown(self, text):
        sender = self.sender()
        if sender and (widget := sender.parent()) and isinstance(widget, IdentifierDropdownWidget):
            if self.scan_results:
                self.scan_results['identifiers'][widget.roi_name] = text
                # Clear errors/warnings for this manually updated identifier
                if widget.roi_name in self.scan_results.get('errors', {}):
                    del self.scan_results['errors'][widget.roi_name]
                if widget.roi_name in self.scan_results.get('warnings', {}):
                    del self.scan_results['warnings'][widget.roi_name]
            widget.setStyleSheet("background-color: #d4edda;")
            self._live_rescan_from_identifiers()

    def _update_answer(self, button):
        parent = button.parent()
        if self.scan_results:
            self.scan_results['answers'][parent.q_num] = [btn.text() for btn in parent.option_group.buttons() if btn.isChecked()]
            # Trigger immediate recalculation and UI refresh
            self._calculate_and_update_score()
            self._update_output_preview()

    def zoom_to_fit_height(self):
        if not self.image_pixmap_item:
            return
        view = self.view
        image_rect = self.image_pixmap_item.boundingRect()
        if image_rect.isEmpty() or view.viewport().height() == 0:
            view.fitInView(self.image_pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            return

        view_aspect = view.viewport().width() / view.viewport().height()
        target_rect = QRectF(0, 0, image_rect.height() * view_aspect, image_rect.height())
        target_rect.moveCenter(image_rect.center())

        view.fitInView(target_rect, Qt.AspectRatioMode.KeepAspectRatio)

    def update_inspector_panel(self, scene_pos):
        if not self.roi_items or self.warped_image is None: return
        for i, roi_data in enumerate(self.template_data['rois']):
            if i < len(self.roi_items) and self.roi_items[i][0].rect().contains(scene_pos):
                try: 
                    rows, cols = (int(roi_data[k]) for k in (['rows', 'cols'] if 'rows' in roi_data else ['questions', 'options']))
                    if rows == 0 or cols == 0: continue
                    roi_rect = self.roi_items[i][0].rect(); local_pos = scene_pos - roi_rect.topLeft()
                    c, r = int(local_pos.x()/(roi_rect.width()/cols)), int(local_pos.y()/(roi_rect.height()/rows))
                    if 0 <= r < rows and 0 <= c < cols:
                        cell_w, cell_h = roi_rect.width()/cols, roi_rect.height()/rows
                        bubble_img = self.warped_image[int(roi_rect.y()+r*cell_h):int(roi_rect.y()+(r+1)*cell_h), int(roi_rect.x()+c*cell_w):int(roi_rect.x()+(c+1)*cell_w)]
                        if bubble_img.size > 0:
                            count, area, fill = self.engine.get_bubble_stats(bubble_img, self.get_current_params())
                            self.inspector_pixel_label.setText(f"Pixels: {count}"); self.inspector_contour_label.setText(f"Area: {area:.0f}"); self.inspector_fill_label.setText(f"Fill: {fill:.1f}%")
                            return
                except (KeyError, ValueError): continue
        self.inspector_pixel_label.setText("Pixels: N/A"); self.inspector_contour_label.setText("Area: N/A"); self.inspector_fill_label.setText("Fill: N/A")

    def display_image(self, image):
        self.scene.clear()
        self.scene.setSceneRect(QRectF()) # Explicitly reset the scene's coordinate system
        self.roi_items.clear(); self.corner_handles.clear(); self.corner_polygon = None
        if hasattr(self, 'bubble_items') and isinstance(self.bubble_items, dict):
            self.bubble_items['identifier'].clear()
            self.bubble_items['answer'].clear()
        elif hasattr(self, 'bubble_items'): # Fallback for old list structure
             self.bubble_items.clear()
        self.image_pixmap_item = None
        h, w, ch = image.shape
        self.image_pixmap_item = self.scene.addPixmap(QPixmap.fromImage(QImage(cv2.cvtColor(image, cv2.COLOR_BGR2RGB).data, w, h, ch*w, QImage.Format.Format_RGB888)))
        self.zoom_to_fit_height()
        if self.last_zoom_transform:
            self.view.setTransform(self.last_zoom_transform)

    def _sanitize_for_filename(self, text: str) -> str:
        """Removes characters that are invalid for Windows filenames."""
        text = str(text).strip()
        # Replace one or more whitespace chars with a single underscore
        text = re.sub(r'\s+', '_', text)
        # Remove invalid filename characters
        return re.sub(r'[\\/*?:"<>|]', '', text)

    def _get_images_parent_folder_path(self) -> str:
        """
        Determines a default parent folder path for saving results,
        based on the location of the first loaded image, or a fallback.
        """
        if self.image_paths:
            # Get the directory of the first image
            first_image_dir = os.path.dirname(self.image_paths[0])
            # Get the parent of that directory
            grandparent_dir = os.path.dirname(first_image_dir)
            # Ensure the grandparent dir exists or is creatable
            if grandparent_dir and os.path.isdir(grandparent_dir):
                return grandparent_dir
            else:
                # Fallback if grandparent is weird or non-existent
                self.log(f"Warning: Grandparent directory '{grandparent_dir}' not found for image path '{self.image_paths[0]}'. Falling back to results directory.")
                return get_results_dir()
        else:
            self.log("No images loaded, falling back to results directory for default path.")
            return get_results_dir()

    def _save_scan_result(self):
        self.log("DEBUG: Attempting to save scan result...")
        all_data, current_answers = self._get_current_aggregated_data()
        
        if not all_data:
            self.show_toast("Scanned data or template is missing. Cannot save.", level='warning')
            self.log("DEBUG: Save aborted. Aggregated data is missing.")
            return

        self.log(f"DEBUG: Data aggregated for saving. Score: {all_data.get('Score')} | Strategy: {self.get_current_params().get('multi_ans_strategy', 'wrong')}")

        use_pattern = bool(self.active_output_pattern)
        now = datetime.datetime.now()

        # --- Strict Validation (User Request) ---
        if use_pattern:
            self.log("DEBUG: Performing strict validation based on pattern.")
            selected_cols = self.active_output_pattern.get('selected_columns', [])
            required_cols_from_pattern = [
                c for c in selected_cols 
                if c not in ["Student Answers (per question)", "Correctness Status (per question)"]
            ]
            self.log(f"DEBUG: Required columns from pattern: {required_cols_from_pattern}")
            
            missing_data_cols = []
            for col in required_cols_from_pattern:
                if all_data.get(col) is None or str(all_data.get(col)).strip() == '':
                    missing_data_cols.append(col)
            
            if missing_data_cols:
                error_message = f"Save aborted. Missing required data for: {', '.join(missing_data_cols)}."
                self.log(f"DEBUG: {error_message}")
                self.show_toast(error_message, level='error', duration=5000)
                self._update_image_status(self.image_paths[self.current_image_index], "Error")
                return # Abort both rename and save
            else:
                self.log("DEBUG: Strict validation passed.")

        # --- Image Renaming ---
        original_path = self.image_paths[self.current_image_index]
        image_path_to_save = original_path

        if self.active_output_pattern and self.active_output_pattern.get('rename_components'):
            try:
                filename_parts = []
                for component in self.active_output_pattern['rename_components']:
                    part = ""
                    # Handle Static Text
                    if component.startswith('"') and component.endswith('"'):
                        part = component.strip('"')
                    elif component.startswith("Data: "):
                        col_name = component.replace("Data: ", "", 1)
                        part = str(all_data.get(col_name, 'NA'))
                    else:
                        comp_lower = component.lower()
                        if component == 'YYYY': part = now.strftime('%Y')
                        elif component == 'YY': part = now.strftime('%y')
                        elif component == 'MM': part = now.strftime('%m') # Month
                        elif component == 'MMM': part = now.strftime('%b') # Month Abbr
                        elif component == 'DD': part = now.strftime('%d')
                        elif component == 'hh': part = now.strftime('%H')
                        elif component == 'mm': part = now.strftime('%M') # Minute
                        elif component == 'ss': part = now.strftime('%S')
                        elif comp_lower == 'year': part = now.strftime('%Y')
                        elif comp_lower == 'date': part = now.strftime('%d_%b_%y')
                        elif comp_lower == 'yyyy': part = now.strftime('%Y') # Fallback for lowercase
                        elif comp_lower == 'dd': part = now.strftime('%d') # Fallback for lowercase
                        else: # It's an ROI name or Identifier
                            # Case-insensitive lookup in all_data
                            val = all_data.get(component)
                            if val is None:
                                for k, v in all_data.items():
                                    if k.lower() == comp_lower:
                                        val = v
                                        break
                            part = str(val if val is not None else 'NA')
                    
                    # Sanitize part for filename
                    part = part.replace(" ", "_").replace("/", "-").replace("\\", "-").replace(":", "-").replace("*", "").replace("?", "").replace("\"", "").replace("<", "").replace(">", "").replace("|", "")
                    filename_parts.append(part)

                new_filename_base = '_'.join(filter(None, filename_parts))
                _, extension = os.path.splitext(original_path)
                new_filename = f"{new_filename_base}{extension}"
                directory = os.path.dirname(original_path)
                new_path = os.path.join(directory, new_filename)

                if os.path.abspath(original_path) != os.path.abspath(new_path):
                    if os.path.exists(new_path):
                        base, ext = os.path.splitext(new_path)
                        i = 1
                        while os.path.exists(f"{base}_{i}{ext}"): i += 1
                        new_path = f"{base}_{i}{ext}"
                    
                    try:
                        shutil.move(original_path, new_path)
                        self.log(f"Image '{os.path.basename(original_path)}' renamed to '{os.path.basename(new_path)}'")
                        image_path_to_save = new_path
                        self.image_paths[self.current_image_index] = new_path 
                        if original_path in self.image_list_items:
                            self.image_list_items[new_path] = self.image_list_items.pop(original_path)
                    except OSError as e:
                        self.log(f"Could not rename file. It may be in use. Error: {e}")
                        self.show_toast(f"Could not rename image: {os.path.basename(original_path)}", level='error')
                        image_path_to_save = original_path
            except Exception as e:
                self.log(f"Error during image renaming: {e}")
                self.show_toast(f"Error creating new image name: {e}", 'error')

        # --- NEW: Move out of "Error Image" folders ---
        try:
            current_path = image_path_to_save
            while True:
                parent_dir = os.path.dirname(current_path)
                parent_dir_name = os.path.basename(parent_dir)

                if parent_dir_name.lower() == "error image": # Case-insensitive check
                    # Move up one level
                    new_parent_dir = os.path.dirname(parent_dir)
                    new_path = os.path.join(new_parent_dir, os.path.basename(current_path))
                    
                    # Handle potential name conflicts in the destination
                    if os.path.exists(new_path):
                        base, ext = os.path.splitext(new_path)
                        i = 1
                        while os.path.exists(f"{base}_{i}{ext}"):
                            i += 1
                        new_path = f"{base}_{i}{ext}"
                    
                    shutil.move(current_path, new_path)
                    self.log(f"Moved image from '{parent_dir_name}' to parent directory: '{os.path.basename(new_path)}'")
                    current_path = new_path
                else:
                    # We are in a directory not named "Error Image", so we stop.
                    break
            
            image_path_to_save = current_path
            # Update the main image path list as well, as it's used by other functions
            self.image_paths[self.current_image_index] = image_path_to_save

        except Exception as e:
            self.log(f"Error while moving image out of 'Error Image' folder: {e}")
            self.show_toast("Could not move image from 'Error Image' folder.", level='error')

        all_data['Image_Path'] = image_path_to_save

        # --- Path and Data Generation ---
        output_path = ""
        if self.checkbox_append_excel.isChecked(): # This checkbox now implies "append to specific CSV"
            output_path = self.output_csv_path_edit.text()
            if not output_path:
                # If no specific file is selected, default to 'result.csv' in the images' parent folder
                output_path = os.path.join(self._get_images_parent_folder_path(), "result.csv")
                self.log(f"No specific output CSV selected, defaulting to: {output_path}")
            if not output_path.lower().endswith('.csv'):
                QMessageBox.warning(self, "Invalid File Type", "Selected file must be a CSV file (.csv).")
                return
        else: # checkbox is unchecked, meaning use pattern
            filename = ""
            output_dir = get_results_dir()
            
            if self.active_output_pattern:
                filename_parts = []
                for component in self.active_output_pattern['csv_filename_components']:
                    part = ""
                    comp_lower = component.lower()
                    if comp_lower == 'yyyy': part = now.strftime('%Y')
                    elif comp_lower == 'yy': part = now.strftime('%y')
                    elif comp_lower == 'mm': part = now.strftime('%m')
                    elif comp_lower == 'mmm': part = now.strftime('%b')
                    elif comp_lower == 'dd': part = now.strftime('%d')
                    elif comp_lower == 'year': part = now.strftime('%Y')
                    elif comp_lower == 'date': part = now.strftime('%d_%b_%y')
                    elif component.startswith("Data: "):
                        col_name = component.replace("Data: ", "", 1)
                        part = str(all_data.get(col_name, 'NA')).replace(" ", "_")
                    else: # It's an ROI name or Identifier
                        part = str(all_data.get(component, 'NA')).replace(" ", "_")
                    filename_parts.append(part)
                filename = f"{'_'.join(filter(None, filename_parts))}.csv" # Changed extension to .csv
            else: # Fallback if no pattern
                filename = f"scan_results_{now.strftime('%d_%b_%Y')}.csv" # Changed extension to .csv
            
            if not filename.lower().endswith('.csv'): filename += '.csv' # Ensure .csv extension
            if not os.path.exists(output_dir):
                try: os.makedirs(output_dir)
                except Exception as e: QMessageBox.critical(self, "Error", f"Could not create output directory:\n{e}"); return
            output_path = os.path.join(output_dir, filename)

        # --- Data Structuring with Strict Column Schema ---
        cols_to_add = []
        if use_pattern:
            selected_cols = self.active_output_pattern.get('selected_columns', [])
            for col_name in selected_cols:
                if col_name == "Student Answers (per question)":
                    cols_to_add.extend([f'Q{q_num}' for q_num in sorted(current_answers.keys(), key=int)])
                elif col_name == "Correctness Status (per question)":
                    cols_to_add.extend([f'Q{q_num}_Correct' for q_num in sorted(current_answers.keys(), key=int)])
                else:
                    cols_to_add.append(col_name)
        else:
            cols_to_add.extend(list(all_data.keys()))
            # Remove internal keys that shouldn't be in CSV if not in pattern
            cols_to_add = [c for c in cols_to_add if c not in ['status', 'reason', 'potential_matches', 'suggested_primary_id']]
        
        # FIX: Ensure all column names are unique to prevent reindexing errors.
        ordered_columns = []
        for col in cols_to_add:
            if col not in ordered_columns:
                ordered_columns.append(col)

        # Create the row by looking up each required column in the full data set.
        # all_data.get(col) will return None if a key is missing, which pandas handles correctly.
        row_data = {col: all_data.get(col) for col in ordered_columns}
        df = pd.DataFrame([row_data], columns=ordered_columns) # Explicitly set columns to guarantee order and schema

        self.log(f"Saving row data: {row_data}")
        self.log(f"Saving to CSV directory: {os.path.dirname(output_path)}")

        # --- Writing to CSV ---
        try:
            self.log(f"DEBUG: Final CSV output path: '{output_path}'") # Log final path
            if not os.path.exists(output_path):
                # Write header if file doesn't exist
                df.to_csv(output_path, mode='w', header=True, index=False)
            else:
                # Append without header if file exists
                df.to_csv(output_path, mode='a', header=False, index=False)

            self.show_toast(f"Result saved to {os.path.basename(output_path)}", level='info')
            self._update_image_status(image_path_to_save, "Done")
            self._record_scan_async(count=1)

            # --- Cloud Export ---
            success, msg = self.export_manager.export_data(row_data)
            if success:
                self.log(f"Cloud Export Success: {msg}")
            else:
                self.log(f"Cloud Export Failed: {msg}")
                self.show_toast(f"Cloud Export Failed: {msg}", level='warning')

        except Exception as e:

            QMessageBox.critical(self, "Error", f"Failed to save scan result to CSV.\nError: {e}")
            self.log(f"CRITICAL: Error saving scan result to CSV: {str(e)}") # Improved critical logging
            self.log(f"CRITICAL: Attempted to save to path: {output_path}") # Log attempted path on error
            self._update_image_status(original_path, "Error")
    
    def _load_output_settings(self):
        settings = QSettings("OptiMark Pro", "Defaults")
        # Load the append/create checkbox state
        is_append = settings.value("output_mode_is_append", "false", type=str).lower() == 'true'
        self.checkbox_append_excel.setChecked(is_append)
            
        # Load the append file path
        append_path = settings.value("output_append_path", "")
        if append_path:
            self.output_csv_path_edit.setText(append_path)

        # Update the UI to reflect the loaded state
        self._update_output_options_state()

    def _update_output_options_state(self):
        is_append_checked = self.checkbox_append_excel.isChecked()
        
        self.append_widgets_container.setVisible(is_append_checked)
        self.output_pattern_label.setVisible(not is_append_checked)

        # Save the state whenever it changes
        settings = QSettings("OptiMark Pro", "Defaults")
        settings.setValue("output_mode_is_append", str(is_append_checked))

    def _create_mapped_student_info(self, row_series):
        """
        Creates a student info dictionary with standardized keys by mapping potential
        column names from the source Excel file.
        """
        # This map defines required keys and possible source columns (in lowercase).
        COLUMN_MAP = {
            'ID': ['id', 'student id'],
            'Name': ['name', 'student name'],
            'ProgramName': ['programname', 'programme name', 'class'],
            'SectionName': ['sectionname', 'section'],
            'Roll': ['roll']
        }
        
        student_info_dict = {}
        # Create a lowercase version of the source series's index (column names)
        original_cols_lower = {str(col).lower(): col for col in row_series.index}

        for required_key, possible_keys in COLUMN_MAP.items():
            for p_key in possible_keys:
                if p_key in original_cols_lower:
                    actual_col_name = original_cols_lower[p_key]
                    student_info_dict[required_key] = row_series[actual_col_name]
                    break # Move to the next required key once found
        
        # Merge the standardized dictionary with the original one.
        # This keeps all other columns from the source file, while ensuring
        # the required keys are present and correctly named.
        final_dict = {**row_series.to_dict(), **student_info_dict}
        return final_dict

    def _apply_dependent_mappings(self, scanned_ids):
        if not self.active_matching_rule or "dependent_mappings" not in self.active_matching_rule:
            return scanned_ids

        modified_ids = scanned_ids.copy()
        rules = self.active_matching_rule["dependent_mappings"]

        for rule in rules:
            if_identifier = rule["if_identifier"]
            is_value = rule["is_value"]
            then_identifier = rule["then_identifier"]
            to_value = rule["to_value"]

            # Check if the condition is met
            if if_identifier in modified_ids and self._format_identifier(if_identifier, modified_ids[if_identifier]) == self._format_identifier(if_identifier, is_value):
                # If condition met, apply the change
                self.log(f"DEBUG (Dependency Rule): Condition met: '{if_identifier}' is '{is_value}'. Changing '{then_identifier}' to '{to_value}'.")
                modified_ids[then_identifier] = to_value

        return modified_ids

    def _get_student_info(self, scanned_ids):
        # Structured result object
        result = {
            "status": MATCH_NO_MATCH,
            "student_info": None,
            "potential_matches": [],  # List of dicts for multiple matches
            "suggested_primary_id": None, # If SINGLE_SECONDARY_MATCH, suggestion for primary ID
            "reason": ""
        }

        if self.student_data is None or self.student_data.empty:
            self.log("Student data is not loaded or is empty. Cannot perform lookup.")
            result["reason"] = "Student data not loaded."
            return result

        try: # NEW: Catch exceptions within the matching logic
            # Ensure student_data columns are formatted once for consistency in matching
            # Create a formatted version of the student data for matching
            formatted_student_df = self.student_data.copy()
            for col in formatted_student_df.columns:
                # Check if column exists before trying to format
                if col in formatted_student_df.columns:
                    formatted_student_df[col] = formatted_student_df[col].astype(str).apply(lambda x: self._format_identifier(col, x))


            # --- No Advanced Matching Rule Configured or Primary Match Fails ---
            if not self.active_matching_rule or \
            not self.active_matching_rule["primary_match"]["roi_name"] or \
            not self.active_matching_rule["primary_match"]["excel_column"]:
                self.log("DEBUG: No active advanced matching rule or primary match not fully configured. Falling back to old matching logic.")
                
                # Old matching logic fallback
                if self.active_output_pattern and self.active_output_pattern.get('lookup_roi') and self.active_output_pattern.get('lookup_column'):
                    lookup_roi = self.active_output_pattern['lookup_roi']
                    lookup_column = self.active_output_pattern['lookup_column']

                    scanned_value_for_lookup = scanned_ids.get(lookup_roi)

                    self.log(f"DEBUG (Fallback): Lookup ROI: '{lookup_roi}'")
                    self.log(f"DEBUG (Fallback): Lookup Column (in Excel): '{lookup_column}'")

                    if scanned_value_for_lookup:
                        try:
                            self.log(f"DEBUG (Fallback): Scanned value for '{lookup_roi}' (before format): '{scanned_value_for_lookup}'")
                            scanned_value_for_lookup = self._format_identifier(lookup_roi, str(scanned_value_for_lookup))
                            self.log(f"DEBUG (Fallback): Scanned value for '{lookup_roi}' (AFTER format): '{scanned_value_for_lookup}'")

                            # Use the pre-formatted DataFrame for lookup
                            if lookup_column not in formatted_student_df.columns:
                                self.log(f"ERROR (Fallback): Lookup column '{lookup_column}' not found in student data. Please check your Excel headers.")
                                result["reason"] = f"Lookup column '{lookup_column}' not found."
                                return result

                            matched_rows = self.student_data[formatted_student_df[lookup_column] == scanned_value_for_lookup]

                        except KeyError:
                            self.log(f"ERROR (Fallback): Lookup column '{lookup_column}' not found in student data. Please check your Excel headers.")
                            result["reason"] = f"Lookup column '{lookup_column}' not found."
                            return result
                        except Exception as e:
                            self.log(f"ERROR (Fallback): Exception during student data lookup: {str(e)}")
                            result["reason"] = f"Exception during fallback lookup: {str(e)}"
                            return result

                        if not matched_rows.empty:
                            result["status"] = MATCH_PRIMARY # Treat old logic as primary match
                            result["student_info"] = self._create_mapped_student_info(matched_rows.iloc[0])
                            result["reason"] = f"Primary match found for '{scanned_value_for_lookup}' (fallback)."
                            self.log(f"DEBUG (Fallback): {result['reason']}")
                        else:
                            result["reason"] = f"No match found for '{scanned_value_for_lookup}' in column '{lookup_column}' (fallback)."
                            self.log(f"DEBUG (Fallback): Match NOT FOUND for '{lookup_roi}': '{scanned_value_for_lookup}' in column '{lookup_column}'")
                            self.log(f"DEBUG (Fallback): All formatted values in column '{lookup_column}': {formatted_student_df[lookup_column].tolist()}")
                    else:
                        self.log(f"DEBUG (Fallback): No scanned value available for lookup ROI: '{lookup_roi}'")
                        result["reason"] = f"No scanned value for '{lookup_roi}' (fallback)."
                else:
                    self.log("DEBUG (Fallback): No active output pattern with student data lookup configured or lookup ROI/column missing.")
                    result["reason"] = "No fallback lookup configured."
                return result

            # --- Advanced Matching Logic ---
            matching_rule = self.active_matching_rule
            primary_roi = matching_rule["primary_match"]["roi_name"]
            primary_excel_col = matching_rule["primary_match"]["excel_column"]
            secondary_matching_enabled = matching_rule["secondary_matching_enabled"]
            secondary_identifiers = matching_rule["secondary_match_identifiers"]
            display_columns = matching_rule["display_columns"]

            scanned_primary_value = scanned_ids.get(primary_roi)
            self.log(f"DEBUG (Advanced): Primary Match ROI: '{primary_roi}' -> Excel Column: '{primary_excel_col}'")
            self.log(f"DEBUG (Advanced): Scanned Primary Value (before format): '{scanned_primary_value}'")

            if not scanned_primary_value:
                result["reason"] = f"No scanned value for primary ROI '{primary_roi}'."
                self.log(f"DEBUG (Advanced): {result['reason']}")
                return result
            
            formatted_scanned_primary_value = self._format_identifier(primary_roi, str(scanned_primary_value))
            self.log(f"DEBUG (Advanced): Scanned Primary Value (AFTER format): '{formatted_scanned_primary_value}'")

            # 1. Attempt Primary Match
            if primary_excel_col not in formatted_student_df.columns:
                self.log(f"ERROR (Advanced): Primary Excel column '{primary_excel_col}' not found in student data.")
                result["reason"] = f"Primary Excel column '{primary_excel_col}' not found."
                return result

            primary_match_df = self.student_data[formatted_student_df[primary_excel_col] == formatted_scanned_primary_value]

            if not primary_match_df.empty:
                # --- Secondary Key Validation on Primary Match ---
                matched_row_original = self.student_data.loc[primary_match_df.index[0]]
                mismatched_secondaries = []
                if secondary_matching_enabled and secondary_identifiers:
                    for sec_ident in secondary_identifiers:
                        sec_roi = sec_ident["roi_name"]
                        sec_excel_col = sec_ident["excel_column"]

                        if sec_excel_col not in formatted_student_df.columns:
                            self.log(f"WARNING: Secondary validation skipped for '{sec_roi}'. Column '{sec_excel_col}' not in student data.")
                            continue
                        
                        scanned_sec_value = scanned_ids.get(sec_roi)
                        if scanned_sec_value is None or str(scanned_sec_value).strip() == '':
                            continue

                        excel_sec_value = formatted_student_df.loc[primary_match_df.index[0]][sec_excel_col]
                        formatted_scanned_sec_value = self._format_identifier(sec_roi, str(scanned_sec_value))

                        if formatted_scanned_sec_value != excel_sec_value:
                            mismatched_secondaries.append({
                                "roi": sec_roi,
                                "scanned": str(scanned_sec_value),
                                "expected": str(matched_row_original[sec_excel_col])
                            })
                
                if mismatched_secondaries:
                    result["status"] = MATCH_PRIMARY_MISMATCH_SECONDARY
                    result["mismatched_data"] = mismatched_secondaries
                    result["student_info"] = self._create_mapped_student_info(matched_row_original)
                    result["reason"] = "Primary match found, but secondary identifiers do not match."
                    self.log(f"DEBUG (Advanced): {result['reason']} {mismatched_secondaries}")
                    return result
                
                # If we reach here, validation passed
                result["status"] = MATCH_PRIMARY
                result["student_info"] = self._create_mapped_student_info(matched_row_original)
                result["reason"] = f"Primary match found for '{formatted_scanned_primary_value}'."
                self.log(f"DEBUG (Advanced): {result['reason']}")
                return result
            else:
                self.log(f"DEBUG (Advanced): Primary match NOT FOUND for '{formatted_scanned_primary_value}'.")
                result["reason"] = f"Primary match failed for '{formatted_scanned_primary_value}'."

            # 2. Attempt Secondary Matching if Enabled and Primary Failed
            if secondary_matching_enabled and secondary_identifiers:
                self.log("DEBUG (Advanced): Primary match failed, attempting secondary matching.")
                secondary_conditions = pd.Series([True] * len(formatted_student_df), index=formatted_student_df.index)

                all_secondary_scanned_values_present = True
                for sec_ident in secondary_identifiers:
                    sec_roi = sec_ident["roi_name"]
                    sec_excel_col = sec_ident["excel_column"]

                    scanned_sec_value = scanned_ids.get(sec_roi)
                    self.log(f"DEBUG (Advanced): Secondary ROI: '{sec_roi}' -> Excel Column: '{sec_excel_col}'")
                    self.log(f"DEBUG (Advanced): Scanned Secondary Value (before format): '{scanned_sec_value}'")

                    if not scanned_sec_value:
                        self.log(f"DEBUG (Advanced): No scanned value for secondary ROI '{sec_roi}'. Cannot perform full secondary match.")
                        all_secondary_scanned_values_present = False
                        break 

                    formatted_scanned_sec_value = self._format_identifier(sec_roi, str(scanned_sec_value))
                    self.log(f"DEBUG (Advanced): Scanned Secondary Value (AFTER format): '{formatted_scanned_sec_value}'")
                    
                    if sec_excel_col not in formatted_student_df.columns:
                        self.log(f"ERROR (Advanced): Secondary Excel column '{sec_excel_col}' not found in student data. Cannot perform full secondary match.")
                        all_secondary_scanned_values_present = False
                        break 

                    secondary_conditions &= (formatted_student_df[sec_excel_col] == formatted_scanned_sec_value)
                    self.log(f"DEBUG (Advanced): Condition for '{sec_roi}' matched {secondary_conditions.sum()} rows.")
                
                if all_secondary_scanned_values_present:
                    secondary_match_df = self.student_data[secondary_conditions]

                    if not secondary_match_df.empty:
                        if len(secondary_match_df) == 1:
                            result["status"] = MATCH_SINGLE_SECONDARY
                            result["student_info"] = self._create_mapped_student_info(secondary_match_df.iloc[0])
                            result["suggested_primary_id"] = self._format_identifier(primary_excel_col, str(result["student_info"].get(primary_excel_col, ""))) # Get from matched record
                            result["reason"] = f"Single secondary match found. Suggested primary ID: '{result['suggested_primary_id']}'"
                            self.log(f"DEBUG (Advanced): {result['reason']}")
                        else:
                            result["status"] = MATCH_MULTIPLE_SECONDARY
                            result["reason"] = f"Multiple secondary matches found ({len(secondary_match_df)} rows)."
                            self.log(f"DEBUG (Advanced): {result['reason']}")
                            
                            # Prepare potential matches with display columns
                            for index, row in secondary_match_df.iterrows():
                                match_info = {}
                                for col in display_columns:
                                    match_info[col] = row.get(col, "N/A")
                                # Instead of full data, store the index to retrieve it later
                                match_info["__row_index__"] = index
                                result["potential_matches"].append(match_info)
                    else:
                        result["reason"] = "No secondary matches found."
                        self.log(f"DEBUG (Advanced): {result['reason']}")
                else:
                    result["reason"] = "Cannot perform secondary matching due to missing scanned values or excel columns."
                    self.log(f"DEBUG (Advanced): {result['reason']}")
            else:
                self.log("DEBUG (Advanced): Secondary matching not enabled or no secondary identifiers configured.")
                result["reason"] = "Primary match failed and secondary matching not used."
        except Exception as e:
            self.log(f"ERROR: Unhandled exception in _get_student_info: {str(e)}")
            result["reason"] = f"Internal error during student info lookup: {str(e)}"
        
        return result

    def _get_all_possible_columns(self):
        """Generates a comprehensive list of all possible columns for the Excel output."""
        if not self.template_data: return []
        
        columns = ['Timestamp', 'Image_Path']
        
        # Add identifier ROIs from the template
        id_roi_names = [roi['name'] for roi in self.template_data.get('rois', []) if roi.get('type') in ['Identifier', 'qrcode']]
        columns.extend(sorted(id_roi_names))

        # Add all columns from student data if available
        if self.student_data is not None:
            student_cols = [col for col in self.student_data.columns if col not in columns]
            columns.extend(student_cols)
            
        # Add core result columns
        columns.extend(['Score', 'Correct', 'Unanswered', 'Total_Questions'])
        
        # Add all possible question columns
        question_nums = sorted([int(q_num) for q_num in self.question_widgets.keys()])
        for q_num in question_nums:
            columns.append(f'Q{q_num}')
            columns.append(f'Q{q_num}_Correct')
            
        # Return a list with unique values, preserving order
        return list(dict.fromkeys(columns))

    def _load_matching_rule_by_name(self, rule_name):
        if not rule_name:
            return None

        self.advanced_matching_settings.beginGroup(rule_name)
        rule = {
            "name": rule_name,
            "primary_match": {
                "roi_name": self.advanced_matching_settings.value("primary_roi", ""),
                "excel_column": self.advanced_matching_settings.value("primary_excel_col", "")
            },
            "secondary_matching_enabled": self.advanced_matching_settings.value("enable_secondary", "false", type=str).lower() == 'true',
            "secondary_match_identifiers": [], # Will load this as a list of dicts
            "display_columns": self.advanced_matching_settings.value("display_columns", [], type=list)
        }
        
        # Load secondary match identifiers (stored as list of "roi::column" strings)
        secondary_idents_raw = self.advanced_matching_settings.value("secondary_match_identifiers", [], type=list)
        for item_str in secondary_idents_raw:
            try:
                roi, col = item_str.split("::")
                rule["secondary_match_identifiers"].append({"roi_name": roi, "excel_column": col})
            except ValueError:
                self.log(f"Warning: Malformed secondary match identifier in rule '{rule_name}': {item_str}")
                pass
        
        # Load dependent mappings
        rule["dependent_mappings"] = []
        dependent_mappings_raw = self.advanced_matching_settings.value("dependent_mappings", [], type=list)
        for item_str in dependent_mappings_raw:
            try:
                if_ident, is_value, then_ident, from_value, to_value = item_str.split("::", 4)
                rule["dependent_mappings"].append({
                    "if_identifier": if_ident,
                    "is_value": is_value,
                    "then_identifier": then_ident,
                    "from_value": from_value,
                    "to_value": to_value
                })
            except ValueError:
                self.log(f"Warning: Malformed dependent mapping in rule '{rule_name}': {item_str}")

        self.advanced_matching_settings.endGroup()
        
        # Basic validation
        if not rule["primary_match"]["roi_name"] or not rule["primary_match"]["excel_column"]:
            self.log(f"Warning: Active matching rule '{rule_name}' has incomplete primary match configuration.")
            return None
        
        return rule

    def _move_image_to_error_folder(self, image_index):
        """Moves an image file to a dedicated 'Error Image' subfolder."""
        if not (0 <= image_index < len(self.image_paths)):
            return
            
        original_path = self.image_paths[image_index]
        if not os.path.exists(original_path) or os.path.isdir(original_path):
             self.log(f"Error moving file: Source file not found or is a directory at {original_path}")
             return

        try:
            directory = os.path.dirname(original_path)
            error_folder_name = "Error Image"
            error_dir = os.path.join(directory, error_folder_name)
            
            os.makedirs(error_dir, exist_ok=True)
            
            filename = os.path.basename(original_path)
            new_path = os.path.join(error_dir, filename)

            # To avoid overwriting, find a new name if the file already exists in the error folder
            if os.path.exists(new_path):
                base, ext = os.path.splitext(filename)
                i = 1
                while os.path.exists(os.path.join(error_dir, f"{base}_{i}{ext}")):
                    i += 1
                new_path = os.path.join(error_dir, f"{base}_{i}{ext}")

            shutil.move(original_path, new_path)
            
            self.log(f"Image '{filename}' moved to '{error_folder_name}' folder due to a processing error.")
            
            # Update the image path in the application's list to prevent further errors
            self.image_paths[image_index] = new_path
            if original_path in self.image_list_items:
                self.image_list_items[new_path] = self.image_list_items.pop(original_path)
        except Exception as e:
            self.log(f"FATAL: Failed to move error image {os.path.basename(original_path)}. Error: {e}")
            self.show_toast(f"Could not move error image: {e}", "error")


    def _select_output_csv_file(self):
        dialog_key = "Select CSV File to Append to"
        initial_path = load_last_path(dialog_key)
        path, _ = QFileDialog.getSaveFileName(self, dialog_key, initial_path, "CSV Files (*.csv)")
        if path: 
            save_last_path(dialog_key, path) 
            self.output_csv_path_edit.setText(path)
            # Save the path when it's selected
            settings = QSettings("OptiMark Pro", "Defaults")
            settings.setValue("output_append_path", path)
    
    def _format_identifier(self, roi_name, value):
        # First, apply custom reference mappings if any
        mapped_value = apply_identifier_reference(roi_name, value)

        # Then, apply a more robust formatting logic
        try:
            # Convert to string, remove leading/trailing whitespace
            s_value = str(mapped_value).strip()
            # If it contains a decimal point, try to convert to float then int to drop decimals
            if '.' in s_value:
                return str(int(float(s_value)))
            # If it's all digits, convert to int to remove leading zeros, then back to string
            elif s_value.isdigit():
                return str(int(s_value))
            # Otherwise, return the stripped string as is
            else:
                return s_value
        except (ValueError, TypeError):
            # If any conversion fails, return the original stripped string
            return str(mapped_value).strip()

    def _set_params_on_ui(self, params):
        self.current_image_processing_params.update(params)
        self.log("Internal image processing parameters updated.")

    def _populate_identifier_overrides(self):
        # Clear existing widgets
        while self.override_layout.count():
            self.override_layout.takeAt(0).widget().deleteLater()
        self.identifier_override_widgets.clear()

        if not self.template_data:
            self.override_layout.addRow(QLabel("<i>Load an answer key to see identifiers.</i>"))
            return

        # Filter for the specific identifiers
        identifier_rois = [
            roi for roi in self.template_data.get('rois', []) 
            if roi.get('type') == 'Identifier' and roi.get('subtype') == 'Answer Script Identifier'
        ]

        if not identifier_rois:
            self.override_layout.addRow(QLabel("<i>No overrideable identifiers found in template.</i>"))
            return

        # Populate with new widgets
        for roi_data in identifier_rois:
            name = roi_data.get('name')
            if not name:
                continue

            # Determine if it should be a dropdown or a textbox
            is_single_choice = (int(roi_data.get('rows', 0)) == 1 or int(roi_data.get('cols', 0)) == 1) and roi_data.get('values')
            
            widget = None
            if is_single_choice:
                # Use QComboBox for single-choice ROIs
                options = [""] + roi_data.get('values', []) # Add a blank option
                widget = QComboBox()
                widget.addItems(list(dict.fromkeys(options))) # Add unique items
            else:
                # Use QLineEdit for others
                widget = QLineEdit()
            
            self.override_layout.addRow(QLabel(f"<b>{name}</b>:"), widget)
            self.identifier_override_widgets[name] = widget

    def _update_image_status(self, image_path, status):
        if image_path in self.image_list_items:
            item = self.image_list_items[image_path]
            base_name = os.path.basename(image_path)
            
            key_info = ""
            # Preserve existing key info if the new status is just 'Done' or 'Skipped'
            if "->" in item.text():
                key_info = "  " + item.text().split("  ", 1)[1]

            # Set new key info if it's available
            if self.current_matched_key_path:
                if self.current_matched_key_path in ["Not Found", "Scan Error"]:
                     key_info = f"  ->  (Key: {self.current_matched_key_path})"
                else:
                     key_info = f"  ->  (Key: {os.path.basename(self.current_matched_key_path)})"

            item.setText(f"[{status}] {base_name}{key_info}")
            
            if status == "Processing":
                item.setForeground(QColor("blue"))
            elif status == "Done":
                item.setForeground(QColor("#006400")) # Dark Green
            elif status == "Skipped":
                item.setForeground(QColor("gray"))
            elif status == "Error":
                item.setForeground(QColor("red"))
            else: # Pending
                item.setForeground(self.panel_text_color)
            self.image_list_widget.scrollToItem(item)
            self.image_selection_updated.emit()

    def _show_image_selection_dialog(self):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Select Image Source")
        dialog.setText("How would you like to add images?")
        dialog.setIcon(QMessageBox.Icon.Question)
        
        btn_files = dialog.addButton("Select File(s)", QMessageBox.ButtonRole.ActionRole)
        btn_folder = dialog.addButton("Select Folder", QMessageBox.ButtonRole.ActionRole)
        dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        
        dialog.exec()
        
        clicked_button = dialog.clickedButton()
        if clicked_button == btn_files:
            self._select_image_files()
        elif clicked_button == btn_folder:
            self._select_image_folder()

    def _select_image_files(self):
        dialog_key = "Select Multiple Images"
        initial_path = load_last_path(dialog_key)
        selected_paths, _ = QFileDialog.getOpenFileNames(self, dialog_key, initial_path, "Image Files (*.png *.jpg *.bmp)")
        if selected_paths:
            save_last_path(dialog_key, os.path.dirname(selected_paths[0]))
            self._load_image_paths(sorted(selected_paths))

    def _select_image_folder(self):
        dialog_key = "Select Image Folder"
        initial_path = load_last_path(dialog_key)
        folder_path = QFileDialog.getExistingDirectory(self, dialog_key, initial_path)
        if folder_path:
            save_last_path(dialog_key, folder_path)
            image_paths_to_load = []
            for root, _, files in os.walk(folder_path):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.bmp')):
                        image_paths_to_load.append(os.path.join(root, file))
            if image_paths_to_load:
                self._load_image_paths(sorted(image_paths_to_load))
            else:
                self.show_toast("No images found in the selected folder and its subfolders.", level='warning')

    def _hardware_scan(self):
        if not self.scanner_manager.is_available():
            QMessageBox.warning(self, "Scanner Error", "TWAIN library not found. Please install 'pytwain'.")
            return
        
        reply = QMessageBox.question(self, "Hardware Scan", "Do you want to show the scanner user interface?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        show_ui = (reply == QMessageBox.StandardButton.Yes)
        
        self.show_toast("Starting hardware scan...", level='info')
        self.scanner_manager.scan_images(show_ui=show_ui)

    def _on_hardware_image_scanned(self, image_path):
        self.log(f"New hardware image scanned: {image_path}")
        # Add to the current image list
        self.image_paths.append(image_path)
        item = QListWidgetItem(f"[Pending] {os.path.basename(image_path)}")
        self.image_list_widget.addItem(item)
        self.image_list_items[image_path] = item
        self.image_selection_updated.emit()
        self.show_toast(f"Scanned: {os.path.basename(image_path)}", level='info')

    def _load_image_paths(self, image_paths):
        if not image_paths:
            return

        self.reset_state(full_reset=False)
        
        self.image_list_widget.clear()
        self.image_list_items.clear()
        for path in image_paths:
            item = QListWidgetItem(f"[Pending] {os.path.basename(path)}")
            self.image_list_widget.addItem(item)
            self.image_list_items[path] = item
        self.image_selection_updated.emit()

        self.image_paths = image_paths
        self.current_image_index = 0
        
        self._load_current_image_for_display()
        self.log(f"Selected {len(self.image_paths)} image(s) for scanning.")
        self.btn_start_scan.setVisible(True)
        for btn in [self.btn_skip_image, self.btn_next_image, self.btn_accept_manual_ids]:
            btn.setVisible(False) 

    def _load_current_image_for_display(self):
        if 0 <= self.current_image_index < len(self.image_paths): self.load_image(self.image_paths[self.current_image_index])
        else: self.log("No image to display or invalid image index."); self.current_image = None; self.scene.clear()

    def _advance_scan_process(self):
        """
        Increments the image index and starts processing the next image,
        or ends the scan session if all images are processed.
        """
        self.current_image_index += 1

        if self.current_image_index >= len(self.image_paths):
            self._end_scan_session()
            return

        image_path = self.image_paths[self.current_image_index]
        self._update_image_status(image_path, "Processing")
        self.log(f"Processing image {self.current_image_index + 1}/{len(self.image_paths)}: {os.path.basename(image_path)}")
        self.load_image(image_path) # Load the image
        
        # If in manual mode, simply load and wait for user.
        # If in auto mode, immediately kick off the scan process for the new image.
        if self.radio_scan_auto.isChecked():
            # Run the full auto-scan logic for the next image
            self._run_auto_batch_scan()
        else:
            # Manual mode: re-enable buttons and wait for user interaction
            # (e.g., re-wrap, accept manual IDs, skip)
            self._process_current_image_manual_mode()

    def _find_matching_answer_key(self):
        if not self.scan_results or not self.answer_key_data: return None
        if len(self.answer_key_data) == 1: return self.answer_key_data[0]
        if not self.template_data or 'rois' not in self.template_data:
            self.log("Error: Template data/ROIs not loaded.")
            return None
        
        script_id_names = {r['name'] for r in self.template_data.get('rois', []) if r.get('subtype') == 'Answer Script Identifier'}
        
        if not script_id_names:
            self.log("Warning: No ROI is marked with subtype 'Answer Script Identifier'. Using first key.")
            return self.answer_key_data[0]
            
        detected_ids = self.scan_results.get('identifiers', {})
        
        for key_data in self.answer_key_data:
            key_ids = key_data.get('identifiers', {})
            
            # Get the script IDs that are actually defined in this answer key
            defined_script_ids_in_key = {
                name for name in script_id_names 
                if str(key_ids.get(name, "")).strip() and str(key_ids.get(name, "")).strip().lower() != 'none'
            }
            
            # If this key has no defined script IDs, it cannot be used for matching.
            if not defined_script_ids_in_key:
                continue

            is_match = True
            for name in defined_script_ids_in_key:
                detected_val = self._format_identifier(name, str(detected_ids.get(name, "")))
                key_val = self._format_identifier(name, str(key_ids.get(name, "")))
                if detected_val != key_val:
                    is_match = False
                    break # Mismatch found, move to the next key
            
            if is_match:
                self.log(f"Found matching answer key: {os.path.basename(key_data['path'])}")
                # FIX: Set the application's main template to the one from the matched key.
                # This ensures subsequent processing uses the correct ROI definitions.
                self.template_data = key_data['template']
                return key_data
                
        self.log(f"Could not find a matching answer key for the scanned identifiers: {detected_ids}")
        return None
    
    def _start_scan_process(self):
        # If the review panel was active, destroy it and rebuild the standard panel.
        if self.review_widgets:
            self._create_right_panel_widgets()
            self.review_widgets.clear()
            # Clear references to deleted review navigation buttons
            if hasattr(self, 'prev_key_button'): self.prev_key_button = None
            if hasattr(self, 'next_key_button'): self.next_key_button = None

        if not self.image_paths: self.show_toast("Please select image(s) to scan first.", 'warning'); return
        if not self.answer_key_data: self.show_toast("Please load an answer key first.", 'warning'); return
        if not self.template_data: 
            self.show_toast("No valid template loaded. Please re-select an answer key.", 'error')
            return

        # Re-create the right-side widgets if they were cleared by a reset
        if (not self.identifier_widgets and not self.question_widgets) and self.template_data:
            self.log("Rebuilding right-side panel widgets before scan.")
            self._create_right_panel_widgets()

        self.is_scan_stopped = False
        self.btn_start_scan.setVisible(False)
        self.btn_stop_scan.setVisible(True)
        self.btn_review_keys.setEnabled(False)
        self.ans_key_combobox.setEnabled(False)
        
        self.current_image_index = 0
        if self.radio_scan_auto.isChecked(): self.log("Starting Auto Scan..."); self._run_auto_batch_scan()
        else: self.log("Starting Manual Scan..."); self._process_current_image_manual_mode()

    def _end_scan_session(self):
        self.auto_scan_preview_timer.stop()
        if hasattr(self, 'scan_progress_label') and self.scan_progress_label:
            self.scan_progress_label.setText("")
        self.btn_start_scan.setVisible(True)
        self.btn_review_keys.setEnabled(True)
        self.ans_key_combobox.setEnabled(True)
        for btn in [self.btn_skip_image, self.btn_next_image, self.btn_accept_manual_ids, self.btn_stop_scan, self.btn_rewrap_image]: 
            btn.setVisible(False)
        self.show_toast("Scan session ended.", 'info')
        self.log("Scan session ended.")

    def _stop_scan_process(self):
        self.auto_scan_preview_timer.stop()
        self.log("DEBUG: Stop scan called.")
        if self.current_image_index >= 0 and self.scan_results:
            self.log("DEBUG: Valid scan results found. Saving before stopping.")
            self._save_scan_result()
        else:
            self.log("DEBUG: No valid results to save upon stopping.")

        self.is_scan_stopped = True
        self.btn_start_scan.setVisible(True)
        self.btn_skip_image.setVisible(False)
        self.btn_next_image.setVisible(False)
        self.btn_accept_manual_ids.setVisible(False)
        self.btn_stop_scan.setVisible(False)
        self.scan_progress_label.setText("Scan stopped.")

        # Re-enable UI elements after stopping
        if self.answer_key_data:
            self.btn_review_keys.setEnabled(True)
        self.ans_key_combobox.setEnabled(True)

    def _pause_scan_for_manual_intervention(self, message, show_accept_button=True):
        self.auto_scan_preview_timer.stop()
        if 0 <= self.current_image_index < len(self.image_paths):
            current_path = self.image_paths[self.current_image_index]
            self._update_image_status(current_path, "Error")
            
        self.log(f"Pausing scan for manual intervention: {message}")
        QMessageBox.warning(self, "Manual Intervention Required", message)
        self.btn_next_image.setVisible(False)
        self.btn_accept_manual_ids.setVisible(show_accept_button)
        self.btn_skip_image.setVisible(True)
        self.btn_rewrap_image.setVisible(True)

    def _apply_dependent_mappings(self):
        """
        Applies conditional value mappings based on the active matching rule.
        This method reads from self.scan_results and updates it directly via _update_identifier_widget_value.
        """
        if not self.active_matching_rule or "dependent_mappings" not in self.active_matching_rule or not self.scan_results:
            return

        original_ids = self.scan_results.get('identifiers', {}).copy()
        rules = self.active_matching_rule.get("dependent_mappings", [])

        for rule in rules:
            if_identifier = rule.get("if_identifier")
            is_value = rule.get("is_value")
            then_identifier = rule.get("then_identifier")
            from_value = rule.get("from_value")
            to_value = rule.get("to_value")

            # Ensure the rule has all necessary parts
            if not all([if_identifier, is_value, then_identifier, to_value]):
                continue

            # Check if the primary 'if' condition is met using original, unmodified values
            if if_identifier in original_ids and self._format_identifier(if_identifier, original_ids.get(if_identifier, '')) == self._format_identifier(if_identifier, is_value):
                
                # Check if the secondary 'and' condition is met (if from_value is specified)
                # If from_value is blank, it means we should overwrite the 'then_identifier' regardless of its current value.
                if not from_value or not from_value.strip() or (then_identifier in original_ids and self._format_identifier(then_identifier, original_ids.get(then_identifier, '')) == self._format_identifier(then_identifier, from_value)):
                    
                    # Check if a change is actually needed before updating
                    if self.scan_results['identifiers'].get(then_identifier) != to_value:
                        self.log(f"DEBUG (Dependency Rule): Condition met. Changing '{then_identifier}' to '{to_value}'.")
                        
                        # This function updates both the UI and self.scan_results['identifiers']
                        self._update_identifier_widget_value(then_identifier, to_value)

    def _validate_and_pause_if_needed(self):
        # Returns a status string: 'PASS', 'PAUSE', 'RESCAN', or 'SKIP'.

        if not self.scan_results: return 'PASS' # No results to validate, pass silently
        
        # 1. Apply any dependent/conditional value mappings. This updates UI and self.scan_results directly.
        self._apply_dependent_mappings()
        
        # 2. Get the (potentially modified) IDs from the single source of truth.
        scanned_ids = self.scan_results.get('identifiers', {})
        
        # 3. Perform Advanced Student Data Lookup with the potentially modified IDs.
        match_result = self._get_student_info(scanned_ids)
        
        primary_roi_name = 'Primary ID' # Default
        if self.active_matching_rule:
            primary_roi_name = self.active_matching_rule.get("primary_match", {}).get("roi_name", primary_roi_name)
        elif self.active_output_pattern:
            primary_roi_name = self.active_output_pattern.get('lookup_roi', primary_roi_name)

        # 2. Handle different match statuses.
        
        # A. Perfect primary match or a mismatch that the user resolves by accepting the scanned values.
        if match_result["status"] == MATCH_PRIMARY:
            self.log(f"DEBUG: Student ID matched: {match_result['student_info'].get(primary_roi_name, 'N/A')}")
            self.student_info_for_output = match_result["student_info"]
            return 'PASS'

        # B. Primary match found, but some secondary fields don't match the database.
        elif match_result["status"] == MATCH_PRIMARY_MISMATCH_SECONDARY:
            action = self._handle_mismatch_dialog(match_result)
            # This can return 'PASS', 'RESCAN', 'PAUSE', or 'SKIP' based on user's choice.
            if action == 'RESCAN':
                # Re-run validation after UI has been updated to confirm the new state.
                return self._validate_and_pause_if_needed()
            return action

        # C. No primary match, but a single, unique match found on secondary keys.
        elif match_result["status"] == MATCH_SINGLE_SECONDARY:
            # If a choice has been remembered for this session, use it automatically.
            if self.remembered_secondary_match_choice:
                action = self.remembered_secondary_match_choice
                self.log(f"DEBUG: Applying remembered secondary match choice: {action}")
                if action == "ACCEPTED":
                    self.log(f"DEBUG: Auto-accepting suggested primary ID: {match_result['suggested_primary_id']}")
                    self._update_identifier_widget_value(primary_roi_name, match_result["suggested_primary_id"])
                    self.student_info_for_output = match_result["student_info"]
                    return 'PASS'
                elif action == "MANUAL_CORRECTION":
                    # Even if remembered, manual correction still requires user input.
                    return self._handle_manual_correction(primary_roi_name, scanned_ids.get(primary_roi_name, ''))

            # If no choice is remembered, show the dialog.
            display_columns = self.active_matching_rule.get("display_columns", [])
            
            dialog_match_result = match_result.copy()
            full_student_info = match_result.get("student_info")
            if full_student_info is not None and display_columns:
                dialog_match_result["student_info"] = {
                    col: full_student_info.get(col, "N/A") for col in display_columns
                }

            dialog = SingleSecondaryMatchDialog(
                match_result=dialog_match_result,
                display_columns=display_columns,
                scanned_primary_id=scanned_ids.get(primary_roi_name, "N/A"),
                primary_roi_name=primary_roi_name,
                parent=self
            )
            apply_stylesheet_and_floatation(dialog)
            
            dialog_code = dialog.exec()
            action = dialog.get_result()

            # After the dialog closes, check if the user wanted to remember the choice.
            if dialog.is_remember_checked():
                if action in ["ACCEPTED", "MANUAL_CORRECTION"]:
                    self.remembered_secondary_match_choice = action
                    self.log(f"DEBUG: Secondary match choice '{action}' will be remembered for this session.")

            if dialog_code == QDialog.DialogCode.Accepted: # This is only for "ACCEPTED"
                self.log(f"DEBUG: User accepted suggested primary ID: {match_result['suggested_primary_id']}")
                self._update_identifier_widget_value(primary_roi_name, match_result["suggested_primary_id"])
                self.student_info_for_output = match_result["student_info"]
                return 'PASS'
            else: # Dialog was rejected or another action was chosen
                if action == "MANUAL_CORRECTION":
                    return self._handle_manual_correction(primary_roi_name, scanned_ids.get(primary_roi_name, ''))
                elif action == "SKIP_SHEET":
                    return 'SKIP'
                else: # Dialog rejected/closed, treat as pause
                    self._pause_scan_for_manual_intervention(match_result["reason"] + "\nPlease correct the value, accept, or skip.", show_accept_button=True)
                    return 'PAUSE'

        # D. Multiple potential matches found on secondary keys.
        elif match_result["status"] == MATCH_MULTIPLE_SECONDARY:
            dialog = MultipleMatchesDialog(
                potential_matches=match_result["potential_matches"],
                display_columns=self.active_matching_rule.get("display_columns", []),
                scanned_primary_id=scanned_ids.get(primary_roi_name, "N/A"),
                primary_roi_name=primary_roi_name,
                parent=self
            )
            apply_stylesheet_and_floatation(dialog)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_item = dialog.get_selected_student_info()
                if selected_item and "__row_index__" in selected_item:
                    row_index = selected_item["__row_index__"]
                    selected_student_info = self._create_mapped_student_info(self.student_data.loc[row_index])

                    self.log(f"DEBUG: User selected student record via index {row_index}: {selected_student_info.get(primary_roi_name, 'N/A')}")
                    
                    suggested_id = self._format_identifier(primary_roi_name, str(selected_student_info.get(primary_roi_name, "")))
                    self._update_identifier_widget_value(primary_roi_name, suggested_id)
                    self.student_info_for_output = selected_student_info
                    return 'PASS'
                else:
                    self.log("DEBUG: Multiple matches dialog accepted but no valid item was selected, pausing.")
                    self._pause_scan_for_manual_intervention(match_result["reason"] + "\nPlease select a student, correct, or skip.", show_accept_button=True)
                    return 'PAUSE'
            else: # Dialog rejected or another action chosen
                action, _ = dialog.get_result()
                if action == "MANUAL_CORRECTION":
                    return self._handle_manual_correction(primary_roi_name, scanned_ids.get(primary_roi_name, ''))
                elif action == "SKIP_SHEET":
                    return 'SKIP'
            
            # If we fall through, it means the user closed the dialog or didn't make a choice. Pause.
            self._pause_scan_for_manual_intervention(match_result["reason"] + "\nPlease select a student, correct, or skip.", show_accept_button=True)
            return 'PAUSE'

        # E. No match found at all. NOW we check for low-level scanning errors.
        elif match_result["status"] == MATCH_NO_MATCH:
            self.log("DEBUG: No student record found. Checking for low-level scanning errors as a possible cause.")
            self.student_info_for_output = None # No student info found

            # Check for low-level scanning errors (moved from the top of the function)
            checked_identifiers = self.identifier_override_widgets.keys()
            error_messages = []
            for n in checked_identifiers:
                value = scanned_ids.get(n, '')
                if not value.strip():
                    error_messages.append(f"Identifier '{n}' is empty or contains only whitespace.")
                else:
                    reasons = []
                    if "ERR" in value: reasons.append("scan error")
                    if "*" in value: reasons.append("multiple marks")
                    if "_" in value: reasons.append("empty/no mark")
                    if reasons:
                        error_messages.append(f"Identifier '{n}' has a {', '.join(reasons)} (Value: '{value}')")
            
            # If we found specific scan errors, show them. They are the most likely cause of the failed match.
            if error_messages:
                message = "No student match found. This may be due to scanning errors:\n\n" + "\n".join(error_messages) + "\n\nPlease correct the values, then click 'Accept & Continue' or 'Skip Image'."
                self._pause_scan_for_manual_intervention(message, show_accept_button=True)
            else:
                # If there are no obvious scan errors, just show the reason from the matching logic.
                message = match_result["reason"] + "\nPlease correct the value, accept, or skip."
                self._pause_scan_for_manual_intervention(message, show_accept_button=True)
            return 'PAUSE'

        # This part should theoretically not be reached if all statuses are handled
        self.log(f"WARNING: Unhandled match status: {match_result['status']}")
        self._pause_scan_for_manual_intervention(f"Unhandled matching scenario: {match_result['status']}", show_accept_button=True)
        return 'PAUSE'

    def _process_current_image_manual_mode(self):
        self.btn_accept_manual_ids.setVisible(False)
        self.current_matched_key_path = None # Reset for new image

        if not (0 <= self.current_image_index < len(self.image_paths)):
            self.show_toast("All selected images have been processed.", 'info')
            self._end_scan_session()
            return

        image_path = self.image_paths[self.current_image_index]
        if hasattr(self, 'scan_progress_label') and self.scan_progress_label:
            total_images = len(self.image_paths)
            current_num = self.current_image_index + 1
            self.scan_progress_label.setText(f"Scanning {current_num} of {total_images}")
        
        self._update_image_status(image_path, "Processing")
        self.log(f"Processing image {self.current_image_index + 1}/{len(self.image_paths)}: {os.path.basename(image_path)}")
        self.load_image(image_path)

        # --- REFACTORED SCAN LOGIC FOR MANUAL MODE ---
        initial_template = self.template_data
        if not self.run_auto_corner_detection():
            # Failure is handled inside run_auto_corner_detection by pausing
            return

        if initial_template != self.template_data:
            self.log("Template mismatch corrected. Re-running scan with the correct template for manual review.")
            if not self.run_auto_corner_detection():
                # Failure on the second try
                return

        # --- Proceed with validation and UI updates ---
        matching_key = self._find_matching_answer_key()
        if not matching_key:
            self.current_matched_key_path = "Not Found"
            self._update_image_status(image_path, "Error") # Update status with key not found
            self.show_toast(f"No matching answer key found for {os.path.basename(image_path)}. Please skip or correct identifiers.", 'warning')
            self._pause_scan_for_manual_intervention("No matching answer key found.", show_accept_button=True)
            return

        self.correct_answers_map = matching_key['answers']
        self.current_matched_key_path = matching_key['path']
        self.log(f"Applied matching answer key: {os.path.basename(matching_key['path'])}")
        self._update_image_status(image_path, "Processing") # Update status with key
        
        validation_status = self._validate_and_pause_if_needed()
        if validation_status == 'PASS':
            self.btn_next_image.setVisible(True)
            self.btn_skip_image.setVisible(True)
            self.btn_rewrap_image.setVisible(False)
        elif validation_status == 'SKIP':
            self._skip_current_image()
            return

    def _run_auto_batch_scan(self):
        try:
            if self.is_scan_stopped:
                return

            if not (0 <= self.current_image_index < len(self.image_paths)):
                self.show_toast(f"Auto scan processed {len(self.image_paths)} images.", 'info')
                self._end_scan_session(); return
            
            self.current_matched_key_path = None # Reset for new image
            i = self.current_image_index
            image_path = self.image_paths[i]
            
            if hasattr(self, 'scan_progress_label') and self.scan_progress_label:
                total_images = len(self.image_paths)
                current_num = self.current_image_index + 1
                self.scan_progress_label.setText(f"Scanning {current_num} of {total_images}")
            
            self._update_image_status(image_path, "Processing")
            self.log(f"Processing image {i + 1}/{len(self.image_paths)}: {os.path.basename(image_path)}")
            self.load_image(image_path)

            # --- REFACTORED SCAN LOGIC ---
            # 1. Run initial scan with whatever template is currently loaded
            initial_template = self.template_data
            if not self.run_auto_corner_detection():
                self.log("Initial corner detection failed. Pausing.")
                self.current_matched_key_path = "Scan Error"
                self._update_image_status(image_path, "Error")
                self._pause_scan_for_manual_intervention("Automatic corner detection failed.", show_accept_button=False)
                return

            # 2. _find_matching_answer_key() has now updated self.template_data to the correct one.
            #    Check if a mismatch was found and corrected.
            if initial_template != self.template_data:
                self.log("Template mismatch corrected. Re-running corner detection with the correct template.")
                # 3. If so, re-run the scan with the NEWLY loaded correct template to fix geometry.
                if not self.run_auto_corner_detection():
                    self.log("Corner detection failed on 2nd attempt with correct template. Pausing.")
                    self.current_matched_key_path = "Scan Error"
                    self._update_image_status(image_path, "Error")
                    self._pause_scan_for_manual_intervention("Corner detection failed after template correction.", show_accept_button=False)
                    return
            
            # 4. At this point, the scan is complete and used the correct template.
            #    Retrieve the matching key again, as it was found during the last scan.
            matching_key = self._find_matching_answer_key()
            if not matching_key:
                message = f"No matching answer key found for {os.path.basename(image_path)}."
                self.current_matched_key_path = "Not Found"
                self._update_image_status(image_path, "Error")
                self.log(f"ERROR: {message} Pausing scan.")
                self._pause_scan_for_manual_intervention(message + "\nPlease correct the identifiers, accept, or skip.", show_accept_button=True)
                return

            self.current_matched_key_path = matching_key['path']
            self._update_image_status(image_path, "Processing") # Update status to show found key

            validation_status = self._validate_and_pause_if_needed()
            if validation_status == 'PAUSE':
                self.log("Auto-scan paused for identifier correction.")
                return
            if validation_status == 'SKIP':
                self._skip_current_image()
                return
            
            # If validation passes, automatically save and proceed to the next image
            # without waiting for the user to click "Next".
            if validation_status == 'PASS':
                self.log("Auto-scan for current image complete and validated. Automatically saving and proceeding.")
                self._save_scan_result()
                self.last_zoom_transform = self.view.transform()
                self.auto_scan_preview_timer.start(200) # Short delay before advancing
            else:
                # Fallback for any other unhandled statuses, maintaining original behavior for review.
                self.log(f"Auto-scan for current image complete with status '{validation_status}'. Pausing for user review.")
                self.btn_next_image.setVisible(True)
                self.btn_skip_image.setVisible(True)
        except Exception as e:
            self.log(f"CRITICAL ERROR during auto-batch scan for image {self.current_image_index}: {e}")
            self.show_toast(f"Critical error during auto-scan: {e}", "error")
            self._update_image_status(self.image_paths[self.current_image_index], "Error")
            # Pause the scan for manual intervention
            self._pause_scan_for_manual_intervention(f"A critical error occurred: {e}\nPlease correct the issue or skip the image.", show_accept_button=False)

    def _skip_current_image(self):
        self.last_zoom_transform = self.view.transform()
        try:
            if not (0 <= self.current_image_index < len(self.image_paths)): return
            
            image_path = self.image_paths[self.current_image_index]
            self.log(f"User manually skipped image: {os.path.basename(image_path)}")

            # Move the file to the "Error Image" folder
            self._move_image_to_error_folder(self.current_image_index)
            
            # Update the UI list with the final status for the (now moved) image
            new_image_path = self.image_paths[self.current_image_index]
            self._update_image_status(new_image_path, "Skipped")
            
            # Now proceed to the next image
            self._advance_scan_process()
        except Exception as e:
            self.log(f"CRITICAL ERROR in _skip_current_image: {e}")
            self.show_toast(f"Error skipping image: {e}", "error")
            # Attempt to end the scan session gracefully to avoid further issues
            self._end_scan_session()

    def _accept_manual_ids_and_continue(self):
        self.last_zoom_transform = self.view.transform()
        self.log("Attempting to accept manual identifiers...")

        # The identifier values in self.scan_results are updated automatically by the UI widgets' signals.
        # We just need to re-run the validation.
        validation_status = self._validate_and_pause_if_needed()

        if validation_status == 'SKIP':
            self._skip_current_image()
            return
        
        if validation_status in ['PAUSE', 'RESCAN']:
            # The validation failed again or triggered a rescan, and the function has already re-paused.
            self.show_toast("Validation failed or view has been updated. Please review and accept again.", 'warning')
            return

        if validation_status == 'PASS':
            # If validation passes, it means a unique, confirmed student record was found.
            # self.student_info_for_output is now populated. Let's update the UI with it.
            if self.student_info_for_output and self.active_matching_rule:
                self.log("DEBUG: Validation passed. Updating UI with matched student info before saving.")
                
                # Build the ROI -> Excel Column mapping from the active rule
                mappings = {}
                primary_match = self.active_matching_rule.get("primary_match", {})
                if primary_match.get("roi_name") and primary_match.get("excel_column"):
                    mappings[primary_match["roi_name"]] = primary_match["excel_column"]
                
                for sec_ident in self.active_matching_rule.get("secondary_match_identifiers", []):
                    if sec_ident.get("roi_name") and sec_ident.get("excel_column"):
                        mappings[sec_ident["roi_name"]] = sec_ident["excel_column"]

                # Update all configured identifier widgets with data from the matched Excel row
                for roi_name, excel_col in mappings.items():
                    # The student_info_for_output contains original column names from Excel
                    if excel_col in self.student_info_for_output:
                        new_value = self.student_info_for_output[excel_col]
                        self._update_identifier_widget_value(roi_name, str(new_value))

            # Proceed to save and move to the next image
            self.log("Manual identifiers accepted. Saving result and continuing scan.")
            self.btn_accept_manual_ids.setVisible(False)
            self.btn_rewrap_image.setVisible(False)
            self._save_scan_result()
            
            # After saving, advance to the next image
            self._advance_scan_process()

    def _process_next_image(self):
        self.last_zoom_transform = self.view.transform()
        self.btn_rewrap_image.setVisible(False)
        if self.scan_results:
            self._save_scan_result()

        # Always advance to the next image after processing/saving the current one
        self._advance_scan_process()

    def closeEvent(self, event):
        settings = QSettings("OptiMark Pro", "Defaults")
        settings.setValue("main_v_splitter_state", self.main_v_splitter.saveState())
        super().closeEvent(event)

    def handle_log_update(self):
        self.log_has_update = True
        QTimer.singleShot(50, self.switch_tabs)

    def handle_image_update(self):
        self.image_panel_has_update = True
        QTimer.singleShot(50, self.switch_tabs)

    def switch_tabs(self):
        if not hasattr(self, 'log_images_tab_widget'): return

        image_tab_index = -1
        log_tab_index = -1

        for i in range(self.log_images_tab_widget.count()):
            widget = self.log_images_tab_widget.widget(i)
            if widget == self.image_list_panel:
                image_tab_index = i
            elif widget.objectName() == "log_group_box":
                log_tab_index = i

        if self.image_panel_has_update and image_tab_index != -1:
            if self.log_images_tab_widget.currentIndex() != image_tab_index:
                self.log_images_tab_widget.setCurrentIndex(image_tab_index)
        elif self.log_has_update and log_tab_index != -1:
            if self.log_images_tab_widget.currentIndex() != log_tab_index:
                self.log_images_tab_widget.setCurrentIndex(log_tab_index)

        self.image_panel_has_update = False
        self.log_has_update = False


if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        w = CheckerWindow()
        w.setWindowTitle("OMR Checker")
        w.showMaximized()
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        with open("error.log", "w") as f:
            f.write(str(e))
            f.write(traceback.format_exc())
