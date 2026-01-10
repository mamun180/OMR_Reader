from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
                             QGraphicsView, QGraphicsScene, QFileDialog, QMessageBox, QGraphicsPixmapItem, QInputDialog,
                             QSplitter, QScrollArea, QCheckBox, QButtonGroup, QLineEdit, QGroupBox, QSlider, QToolButton, QGraphicsItem,
                             QGridLayout, QRadioButton, QComboBox, QApplication, QTextEdit, QFrame, QDialog, QListWidget, QDialogButtonBox, QListWidgetItem,
                             QFormLayout, QGraphicsOpacityEffect, QTabWidget)
from PyQt6.QtGui import QImage, QPixmap, QColor, QBrush, QPen, QPolygonF, QPalette
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
from theme import apply_stylesheet_and_floatation
from directory_manager import get_answer_key_dir, get_results_dir

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
        self.option_group = QButtonGroup(self); self.option_group.setExclusive(multi_ans_strategy == "wrong")
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
            name_label.setStyleSheet("color: black;")
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
            q_num_label.setStyleSheet("color: black;")
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

class CheckerWindow(QWidget):
    log_updated = pyqtSignal()
    image_selection_updated = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("CheckerWindow") 
        
        self.identifier_input_timer = QTimer(self)
        self.identifier_input_timer.setSingleShot(True)
        self.identifier_input_timer.setInterval(400) # Debounce timer for live re-scan
        self.identifier_input_timer.timeout.connect(self._live_rescan_from_identifiers)

        self.apply_theme()

        self.panel_text_color = QColor("black") # will be updated by theme

        self.engine = OMREngine()
        self.template_data, self.current_image, self.warped_image, self.scan_results = None, None, None, None
        self.image_paths = []
        self.roi_items, self.manual_corner_items, self.corner_handles = [], [], []
        self.is_manual_corner_mode = False
        self.is_scan_stopped = False
        self.manual_corners, self.corner_polygon = [], None
        self.identifier_group_box = None
        self.identifier_layout = None
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
        self.active_renamer_pattern = None
        self.active_output_pattern = None
        self.student_data = None
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
        # Result Preview Label
        self.result_preview_label = QLabel("Excel Output:")
        self.main_layout.addWidget(self.result_preview_label)

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

        # Inspector Panel
        self.inspector_pixel_label = QLabel("Pixel Count: N/A")
        self.inspector_contour_label = QLabel("Contour Area: N/A")
        self.inspector_fill_label = QLabel("Fill %: N/A")
        bottom_layout.addWidget(self.inspector_pixel_label)
        bottom_layout.addWidget(self.inspector_contour_label)
        bottom_layout.addWidget(self.inspector_fill_label)

        self.main_layout.addWidget(self.bottom_panel_widget)
        self.btn_refresh_ans_keys.clicked.connect(self.populate_answer_key_combobox)
        self.multi_ans_group.buttonClicked.connect(self.rescan_with_new_parameters)
        self.scan_mode_group.buttonClicked.connect(self.rescan_with_new_parameters)

        self.populate_answer_key_combobox()

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
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Answer Key(s)", get_answer_key_dir(), "JSON Files (*.json)")
        if paths:
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
            return

        self.log(f"Loaded {len(self.answer_key_data)} answer key(s).")
        self.template_data = self.answer_key_data[0]['template']
        if self.answer_key_data[0].get('image_settings'):
            self._set_params_on_ui(self.answer_key_data[0]['image_settings'])
            self.log(f"Image settings loaded from: {os.path.basename(self.answer_key_data[0]['path'])}")
        
        self._create_right_panel_widgets()
        self._populate_identifier_checkboxes()
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
            self._populate_identifier_checkboxes()
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

        # 1. Try to load from cache
        if os.path.exists(cache_file):
            try:
                self.student_data = pd.read_excel(cache_file)
                self.log("Student data loaded from cache.")
                return
            except Exception as e:
                self.log(f"Could not load student data from cache: {e}. Rebuilding cache.")

        # 2. If cache fails or doesn't exist, load from original source
        settings = QSettings("OptiMark Pro", "Defaults")
        path = settings.value("student_data_sheet", "")
        if path and os.path.exists(path):
            try:
                self.student_data = pd.read_excel(path)
                self.log(f"Student data loaded from {os.path.basename(path)}.")
                # 3. Save to cache for future use
                shutil.copy(path, cache_file)
                self.log("Student data cached successfully.")
            except Exception as e:
                self.student_data = None
                self.log(f"Error loading student data from {path}: {e}")
                QMessageBox.critical(self, "Student Data Load Error", f"Failed to load student data from '{path}'.\nError: {e}")
        else:
            self.student_data = None
        
    def apply_theme(self):
        apply_stylesheet_and_floatation(self)

    def show_toast(self, message, level='info', duration=2500):
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
            if hasattr(self, 'new_excel_filename_edit'):
                self.new_excel_filename_edit.setPlaceholderText("e.g., my_results.xlsx")
                self.new_excel_filename_edit.setReadOnly(False)
            return

        output_settings = QSettings("OptiMark Pro", "OutputPatterns")
        if pattern_name not in output_settings.childGroups():
            self.output_pattern_label.setText(f"Pattern '{pattern_name}': Not Found!")
            self.active_output_pattern = None
            return

        output_settings.beginGroup(pattern_name)
        excel_filename_components = output_settings.value("excel_filename_components", [], type=list)
        rename_components = output_settings.value("rename_components", [], type=list)
        selected_columns = output_settings.value("selected_columns", [], type=list)
        lookup_roi = output_settings.value("lookup_roi", "")
        lookup_column = output_settings.value("lookup_column", "")
        output_settings.endGroup()

        if not excel_filename_components or not selected_columns:
            self.output_pattern_label.setText(f"Pattern '{pattern_name}': [INVALID - Excel config missing]")
            self.active_output_pattern = None
            return

        # Update label and check validity of rename components
        self.output_pattern_label.setText(f"Active Pattern: {pattern_name}")
        if rename_components:
            template_rois = [roi['name'] for roi in self.template_data.get('rois', [])] if self.template_data else []
            invalid_rois = [c for c in rename_components if c not in template_rois and c not in ['year', 'date']]
            if invalid_rois:
                self.output_pattern_label.setText(f"Active Pattern: {pattern_name}\n[Rename part INVALID: Missing {', '.join(invalid_rois)}]")

        self.active_output_pattern = {
            'name': pattern_name, 
            'excel_filename_components': excel_filename_components, 
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
        
        self.btn_add_images = QPushButton("Add Images")
        self.btn_add_images.clicked.connect(self._show_image_selection_dialog)
        source_selection_layout.addWidget(self.btn_add_images)

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

        self.checkbox_append_excel = QCheckBox("Save to specific static Excel file")
        output_options_layout.addWidget(self.checkbox_append_excel)

        # Container for the file path widgets, to be shown/hidden
        self.append_widgets_container = QWidget()
        append_layout = QHBoxLayout(self.append_widgets_container)
        append_layout.setContentsMargins(0,0,0,0)
        append_layout.addWidget(QLabel("File Path:"))
        self.output_excel_path_edit = QLineEdit()
        self.output_excel_path_edit.setReadOnly(True)
        append_layout.addWidget(self.output_excel_path_edit)
        self.btn_select_output_excel = QPushButton("Browse...")
        append_layout.addWidget(self.btn_select_output_excel)
        output_options_layout.addWidget(self.append_widgets_container)

        self.output_pattern_label = QLabel("Active Pattern: <None>")
        self.output_pattern_label.setWordWrap(True)
        output_options_layout.addWidget(self.output_pattern_label)

        self.btn_select_output_excel.clicked.connect(self._select_output_excel_file)
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
        self.control_buttons_layout = QVBoxLayout(control_buttons_frame)
        self.btn_start_scan = QPushButton("Start Scan"); self.btn_start_scan.clicked.connect(self._start_scan_process)
        self.btn_skip_image = QPushButton("Skip Image"); self.btn_skip_image.clicked.connect(self._skip_current_image)
        self.btn_next_image = QPushButton("Next Image"); self.btn_next_image.clicked.connect(self._process_next_image)
        self.btn_rewrap_image = QPushButton("Re-Wrap"); self.btn_rewrap_image.clicked.connect(self._rewrap_image)
        self.btn_accept_manual_ids = QPushButton("Accept & Continue"); self.btn_accept_manual_ids.clicked.connect(self._accept_manual_ids_and_continue)
        self.btn_stop_scan = QPushButton("Stop"); self.btn_stop_scan.setObjectName("btn_stop_scan"); self.btn_stop_scan.clicked.connect(self._stop_scan_process)
        for btn in [self.btn_start_scan, self.btn_skip_image, self.btn_next_image, self.btn_rewrap_image, self.btn_accept_manual_ids, self.btn_stop_scan]:
            self.control_buttons_layout.addWidget(btn)
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
        checkbox_layout = QHBoxLayout()
        self.skip_errors_checkbox = QCheckBox()
        skip_label = QLabel("<b>Skip images with identifier errors</b>")
        skip_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        checkbox_layout.addWidget(self.skip_errors_checkbox)
        checkbox_layout.addWidget(skip_label)
        checkbox_layout.addStretch()
        self.left_panel_layout.addLayout(checkbox_layout)

        self.identifier_group_box = QGroupBox("Identifiers to Match")
        self.identifier_group_box.setMinimumHeight(130)
        self.identifier_layout = QGridLayout()
        self.identifier_group_box.setLayout(self.identifier_layout)
        self.identifier_checkboxes = []
        self.identifier_layout.setContentsMargins(0,0,0,0)
        self.left_panel_layout.addWidget(self.identifier_group_box)
        
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
        self.show_wrapped_image_checkbox.setChecked(True)
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
        if path is None: path, _ = QFileDialog.getOpenFileName(self, "Load Template", "", "JSON Files (*.json)")
        if not path: return
        try:
            with open(path, 'r') as f: self.template_data = json.load(f)
            self._create_right_panel_widgets()
            self._populate_identifier_checkboxes()
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
            if self.skip_errors_checkbox.isChecked():
                self.log(f"{message} Skipping image.")
                self.show_toast(f"{message} Skipping.", level='warning', duration=3000)
                self._move_image_to_error_folder(self.current_image_index)
                self._skip_current_image()
            else:
                self.show_toast("Corner detection failed. Please click the 4 corners of the sheet.", level='warning', duration=4000)
                self.enter_manual_corner_mode() # Sets self.is_manual_corner_mode = True
                self.btn_skip_image.setVisible(True)
                self.btn_accept_manual_ids.setVisible(True) # Make Accept button visible here
            return False

    def _rewrap_image(self):
        self.log("Re-wrapping image. Entering manual corner selection mode.")
        self.enter_manual_corner_mode()
    
    def enter_manual_corner_mode(self):
        self.is_manual_corner_mode = True; self.manual_corners = []
        for handle in self.corner_handles: 
            if handle.scene(): self.scene.removeItem(handle)
        self.corner_handles.clear()
        if self.current_image is not None: self.display_image(self.current_image)
        self.show_toast("Click the 4 corners of the OMR sheet.", level='info')

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
            page_corners = corners if corners is not None else np.array([(h.pos().x(), h.pos().y()) for h in self.corner_handles], dtype="float32")
            template_corners = np.array(self.template_data.get('template_corners'), dtype="float32")
            box_points_relative = self.template_data.get('box_points_relative', [])
            if len(box_points_relative) != 4: raise ValueError("Template is missing 'box_points_relative'. Cannot warp content box.")
            tl_corner_template = template_corners[0]
            template_box_points_abs = np.array([[p['x'] + tl_corner_template[0], p['y'] + tl_corner_template[1]] for p in box_points_relative], dtype="float32")
            H, _ = cv2.findHomography(template_corners, page_corners)
            if H is None: raise ValueError("Could not compute homography from page corners.")
            self.homography_matrix = H
            new_box_points = cv2.perspectiveTransform(template_box_points_abs.reshape(-1, 1, 2), H)
            warped_image, warp_matrix = self.engine.four_point_transform(self.current_image, new_box_points.reshape(4, 2))
            if warped_image is None: raise ValueError("Failed to warp the content box.")
            self.warped_image, self.warp_matrix = warped_image, warp_matrix
            self.rescan_with_new_parameters()
            return True
        except Exception as e: 
            message = f"An error occurred during scanning:\n{e}"
            self.log(f"Processing Error: {e}")
            if self.radio_scan_auto.isChecked():
                if self.skip_errors_checkbox.isChecked():
                    self.show_toast(f"{message}\nSkipping image.", level='error', duration=4000)
                    self._skip_current_image()
                else:
                    self._pause_scan_for_manual_intervention(message + "\nPlease skip or re-wrap.", show_accept_button=False)
            else:
                QMessageBox.critical(self, "Processing Error", message)
            return False

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
            if self.image_pixmap_item and self.image_pixmap_item.scene(): self.image_pixmap_item.setPixmap(QPixmap.fromImage(qt_image))
            else: self.image_pixmap_item = self.scene.addPixmap(QPixmap.fromImage(qt_image))
            self._draw_template_on_scene(preview_image, draw_rois=True)
            self._scan_scene_grid(preview_image, params, scan_type='identifiers', clear_existing_bubbles=True)
            matching_key = self._find_matching_answer_key()
            if matching_key:
                self.correct_answers_map = matching_key['answers']
                self.current_matched_key_path = matching_key['path']
                self.log(f"Applied matching answer key: {os.path.basename(matching_key['path'])}")
            else:
                self.log("ERROR: No matching answer key found. Cannot determine bubble colors or score.")
                self.correct_answers_map = {}
                self.current_matched_key_path = "Not Found"

            self._scan_scene_grid(preview_image, params, scan_type='answers', clear_existing_bubbles=False)
            self._update_widgets_from_scan()
        except Exception as e: 
            self.log(f"Re-Scan Error: {e}")
            QMessageBox.critical(self, "Re-Scan Error", f"An error occurred during re-scan:\n{e}")
    
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
        if self.homography_matrix is None or self.warp_matrix is None: return
        combined_matrix = self.warp_matrix @ self.homography_matrix
        for i, roi_data in enumerate(self._get_target_rois()):
            roi_corners = np.array([[roi_data['x'], roi_data['y']], [roi_data['x'] + roi_data['width'], roi_data['y']], [roi_data['x'] + roi_data['width'], roi_data['y'] + roi_data['height']], [roi_data['x'], roi_data['y'] + roi_data['height']]], dtype=np.float32)
            final_roi_in_warp = cv2.perspectiveTransform(roi_corners.reshape(-1, 1, 2), combined_matrix)
            x, y, w, h = cv2.boundingRect(final_roi_in_warp)
            rect = QRectF(x, y, w, h)
            rect_item = self.scene.addRect(rect, QPen(QColor("cyan"), 2))
            text_item = self.scene.addText(roi_data['name']); text_item.setPos(rect.topLeft() - QPointF(0, 10)); text_item.setDefaultTextColor(QColor("cyan"))
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
                for r_idx in range(rows):
                    q_num_str = str(start_q + r_idx)
                    detected_options, correct_options = [], self.correct_answers_map.get(q_num_str, [])
                    for c_idx, is_filled in enumerate(matrix[r_idx]):
                        if not is_filled: continue
                        option_char = options_map[c_idx]
                        detected_options.append(option_char)
                        if (coord_index := r_idx * cols + c_idx) < len(all_coords):
                            bubble = all_coords[coord_index]
                            bubble_coords = (bubble[0] + rect.x(), bubble[1] + rect.y(), bubble[2] + rect.x(), bubble[3] + rect.y())
                            all_filled_bubbles_info.append({'coords': bubble_coords, 'status': 'correct' if option_char in correct_options else 'incorrect', 'roi_type': 'Answer'})
                    self.scan_results['answers'][q_num_str] = detected_options
                    if len(detected_options) > 1 and params.get('multi_ans_strategy', 'wrong') == "wrong": self.scan_results['errors'][f'Q{q_num_str}'] = "Multiple answers"
                    if not detected_options: self.scan_results['errors'][f'Q{q_num_str}'] = "No answer detected"

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
                            char_val = "MULTI"
                        value += char_val
                if value: 
                    self.scan_results['identifiers'][roi_name] = value
                    if "ERR" in value or "MULTI" in value: self.scan_results['errors'][roi_name] = f"Scan error ({value})"
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

    def _calculate_and_update_score(self):
        if not self.template_data or not self.scan_results:
            self.score_label.setText("Score: N/A; Correct: N/A; Unanswered: N/A")
            return
        correct_count, score, total_expected, answered = 0, 0, sum(1 for q in self.question_widgets if self.correct_answers_map.get(q)), 0
        for q_num, detected in self.scan_results.get('answers', {}).items():
            if detected:
                answered += 1
                if set(detected).issubset(set(self.correct_answers_map.get(q_num, []))): correct_count += 1; score += 1
        unanswered = max(0, total_expected - answered)
        self.score_label.setText(f"Score: {score}; Correct: {correct_count}; Unanswered: {unanswered}/{total_expected}")

    def _update_output_preview(self):
        if not self.scan_results or not self.template_data:
            self.result_preview_label.setText("")
            return

        if not self.active_output_pattern:
            self.result_preview_label.setText("No output pattern selected.")
            return

        current_ids = {name: (widget.combo_box.currentText() if isinstance(widget, IdentifierDropdownWidget) else widget.value_edit.text()) for name, widget in self.identifier_widgets.items()}
        student_info = self._get_student_info(current_ids)
        
        correct_count, score, total_expected, answered = 0, 0, 0, 0
        current_answers = {q: [b.text() for b in w.option_group.buttons() if b.isChecked()] for q, w in self.question_widgets.items()}
        for q_num in self.question_widgets:
            if self.correct_answers_map.get(q_num): total_expected += 1
        for q_num, detected in current_answers.items():
            if detected:
                answered += 1
                if set(detected).issubset(set(self.correct_answers_map.get(q_num, []))): correct_count += 1; score += 1
        
        now = datetime.datetime.now()
        scan_data = {
            'Timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
            'Image_Path': '...',
            **current_ids,
            'Score': score, 'Correct': correct_count, 'Unanswered': max(0, total_expected - answered), 'Total_Questions': total_expected
        }
        
        all_data = {**student_info, **scan_data}

        for q_num in sorted(current_answers.keys(), key=int):
            detected_opts = current_answers.get(q_num, [])
            is_correct = set(detected_opts).issubset(set(self.correct_answers_map.get(q_num,[]))) if detected_opts else False
            all_data[f'Q{q_num}'] = ", ".join(detected_opts) if detected_opts else "Unanswered"
            all_data[f'Q{q_num}_Correct'] = 'Yes' if is_correct else 'No'

        selected_columns = self.active_output_pattern.get('selected_columns', [])
        
        preview_parts = []
        for col_name in selected_columns:
            if col_name == "Student Answers (per question)":
                for q_num in sorted(current_answers.keys(), key=int):
                    value = all_data.get(f"Q{q_num}", "")
                    preview_parts.append(f"<b>Q{q_num}</b>: {value}")
            elif col_name == "Correctness Status (per question)":
                for q_num in sorted(current_answers.keys(), key=int):
                    value = all_data.get(f"Q{q_num}_Correct", "")
                    preview_parts.append(f"<b>Q{q_num}_Correct</b>: {value}")
            elif col_name in all_data:
                value = str(all_data.get(col_name, ''))
                preview_parts.append(f"<b>{col_name}</b>: {value}")
        
        preview_text = "; ".join(preview_parts)
        self.result_preview_label.setText(f"Output Preview: {preview_text}")

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
            widget.setStyleSheet("background-color: #d4edda;")
            self.identifier_input_timer.start() # Debounce the live rescan

    def _update_identifier_from_dropdown(self, text):
        sender = self.sender()
        if sender and (widget := sender.parent()) and isinstance(widget, IdentifierDropdownWidget):
            if self.scan_results:
                self.scan_results['identifiers'][widget.roi_name] = text
            widget.setStyleSheet("background-color: #d4edda;")
            self._live_rescan_from_identifiers()

    def _update_answer(self, button):
        parent = button.parent()
        if self.scan_results:
            self.scan_results['answers'][parent.q_num] = [btn.text() for btn in parent.option_group.buttons() if btn.isChecked()]

    def zoom_to_fit_height(self):
        if not self.image_pixmap_item:
            return
        view = self.view
        image_rect = self.image_pixmap_item.boundingRect()
        if image_rect.isEmpty() or view.viewport().height() == 0:
            view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
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

    def _save_scan_result(self):
        if not self.scan_results or not self.template_data:
            self.show_toast("Scanned data or template is missing. Cannot save.", level='warning')
            return

        current_ids = {name: self._format_identifier(widget.combo_box.currentText() if isinstance(widget, IdentifierDropdownWidget) else widget.value_edit.text()) for name, widget in self.identifier_widgets.items()}
        ids = current_ids
        student_info = self._get_student_info(ids)
        
        # --- Image Renaming ---
        original_path = self.image_paths[self.current_image_index]
        image_path_to_save = original_path

        if self.active_output_pattern and self.active_output_pattern.get('rename_components'):
            try:
                now = datetime.datetime.now()
                filename_parts = []
                for component in self.active_output_pattern['rename_components']:
                    part = ""
                    if component == 'year': part = now.strftime('%Y')
                    elif component == 'date': part = now.strftime('%d_%b_%y')
                    elif component.startswith("Data: "):
                        col_name = component.replace("Data: ", "", 1)
                        part = str(student_info.get(col_name, 'NA')).replace(" ", "_")
                    else: # It's an ROI name
                        part = ids.get(component, 'NA').replace(" ", "_")
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

        # --- Path and Data Generation ---
        output_path = ""
        now = datetime.datetime.now() # Get timestamp for excel naming
        if self.checkbox_append_excel.isChecked():
            output_path = self.output_excel_path_edit.text()
            if not output_path:
                self.show_toast("Please select an Excel file to append to.", level='warning')
                return
        else: # checkbox is unchecked, meaning use pattern
            filename = ""
            output_dir = get_results_dir()
            
            if self.active_output_pattern:
                filename_parts = []
                for component in self.active_output_pattern['excel_filename_components']:
                    part = ""
                    if component == 'year': part = now.strftime('%Y')
                    elif component == 'date': part = now.strftime('%d_%b_%y')
                    elif component.startswith("Data: "):
                        col_name = component.replace("Data: ", "", 1)
                        part = str(student_info.get(col_name, 'NA')).replace(" ", "_")
                    else: # It's an ROI name
                        part = ids.get(component, 'NA').replace(" ", "_")
                    filename_parts.append(part)
                filename = f"{'_'.join(filter(None, filename_parts))}.xlsx"
            else: # Fallback if no pattern
                filename = f"scan_results_{now.strftime('%d_%b_%Y')}.xlsx"
            
            if not filename.lower().endswith('.xlsx'): filename += '.xlsx'
            if not os.path.exists(output_dir):
                try: os.makedirs(output_dir)
                except Exception as e: QMessageBox.critical(self, "Error", f"Could not create output directory:\n{e}"); return
            output_path = os.path.join(output_dir, filename)

        # --- Data Calculation ---
        correct_count, score, total_expected, answered = 0, 0, 0, 0
        current_answers = {q: [b.text() for b in w.option_group.buttons() if b.isChecked()] for q, w in self.question_widgets.items()}
        for q_num in self.question_widgets:
            if self.correct_answers_map.get(q_num): total_expected += 1
        for q_num, detected in current_answers.items():
            if detected:
                answered += 1
                if set(detected).issubset(set(self.correct_answers_map.get(q_num, []))): correct_count += 1; score += 1
        
        # --- Column Selection & Data Structuring ---
        row_data = {}
        ordered_columns = []
        use_pattern = bool(self.active_output_pattern)
        selected_cols = self.active_output_pattern['selected_columns'] if use_pattern else []

        scan_data = {
            'Timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
            'Image_Path': image_path_to_save,
            **ids,
            'Score': score, 'Correct': correct_count, 'Unanswered': max(0, total_expected - answered), 'Total_Questions': total_expected
        }
        
        all_data = {**student_info, **scan_data}

        for q_num in sorted(current_answers.keys(), key=int):
            detected_opts = current_answers.get(q_num, [])
            is_correct = set(detected_opts).issubset(set(self.correct_answers_map.get(q_num,[]))) if detected_opts else False
            all_data[f'Q{q_num}'] = ", ".join(detected_opts) if detected_opts else "Unanswered"
            all_data[f'Q{q_num}_Correct'] = 'Yes' if is_correct else 'No'

        if use_pattern:
            for col_name in selected_cols:
                if col_name == "Student Answers (per question)":
                    for q_num in sorted(current_answers.keys(), key=int): ordered_columns.append(f'Q{q_num}')
                elif col_name == "Correctness Status (per question)":
                    for q_num in sorted(current_answers.keys(), key=int): ordered_columns.append(f'Q{q_num}_Correct')
                elif col_name in all_data:
                    ordered_columns.append(col_name)
            row_data = {col: all_data.get(col) for col in ordered_columns}
        else:
            row_data = all_data
            ordered_columns = list(row_data.keys())

        df = pd.DataFrame([row_data], columns=ordered_columns) # Revert to original df creation

        try:
            if os.path.exists(output_path):
                with pd.ExcelFile(output_path) as xls:
                    existing_df = pd.read_excel(xls, sheet_name='Result')
                # Concat will create a superset of columns, filling missing values with NaN
                combined_df = pd.concat([existing_df, df], ignore_index=True)
            else:
                # For a new file, we use the columns explicitly determined by the pattern or present in row_data.
                # 'df' is already created with the correct 'ordered_columns' from the logic above.
                combined_df = df # This is the main change: use 'df' directly.

            combined_df.to_excel(output_path, sheet_name='Result', index=False)
            self.show_toast(f"Result saved to {os.path.basename(output_path)}", level='info')
            self._update_image_status(image_path_to_save, "Done")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save scan result to Excel.\nError: {e}")
            self.log(f"Error saving scan result to Excel: {e}")
            self._update_image_status(original_path, "Error")

    def _load_output_settings(self):
        settings = QSettings("OptiMark Pro", "Defaults")
        # Load the append/create checkbox state
        is_append = settings.value("output_mode_is_append", "false", type=str).lower() == 'true'
        self.checkbox_append_excel.setChecked(is_append)
            
        # Load the append file path
        append_path = settings.value("output_append_path", "")
        if append_path:
            self.output_excel_path_edit.setText(append_path)

        # Update the UI to reflect the loaded state
        self._update_output_options_state()

    def _update_output_options_state(self):
        is_append_checked = self.checkbox_append_excel.isChecked()
        
        self.append_widgets_container.setVisible(is_append_checked)
        self.output_pattern_label.setVisible(not is_append_checked)

        # Save the state whenever it changes
        settings = QSettings("OptiMark Pro", "Defaults")
        settings.setValue("output_mode_is_append", str(is_append_checked))

    def _get_student_info(self, scanned_ids):
        student_info = {}
        if self.student_data is None or self.student_data.empty:
            # self.log("Student data is not loaded or is empty. Cannot perform lookup.")
            return student_info

        if self.active_output_pattern and self.active_output_pattern.get('lookup_roi') and self.active_output_pattern.get('lookup_column'):
            lookup_roi = self.active_output_pattern['lookup_roi']
            lookup_column = self.active_output_pattern['lookup_column']

            scanned_value_for_lookup = scanned_ids.get(lookup_roi)

            if scanned_value_for_lookup:
                # Ensure the column in student_data is of the same type as the scanned value for comparison
                # This handles cases where Excel might store numbers as int/float and scanned_ids are strings
                try:
                    # Convert lookup column in student_data to string for robust comparison, then apply formatting
                    self.student_data[lookup_column] = self.student_data[lookup_column].astype(str).apply(self._format_identifier)
                    scanned_value_for_lookup = self._format_identifier(str(scanned_value_for_lookup)) # Ensure scanned value is also string and formatted
                    matched_row = self.student_data[self.student_data[lookup_column] == scanned_value_for_lookup]
                except KeyError:
                    self.log(f"Lookup column '{lookup_column}' not found in student data.")
                    return student_info
                except Exception as e:
                    self.log(f"Error during student data lookup type conversion: {e}")
                    return student_info

                if not matched_row.empty:
                    student_info = matched_row.iloc[0].to_dict()
                    # self.log(f"Student info found for {lookup_roi}: {scanned_value_for_lookup}")
                # else:
                    # self.log(f"No student info found for {lookup_roi}: {scanned_value_for_lookup}")
            # else:
                # self.log(f"No scanned value available for lookup ROI: {lookup_roi}")
        # else:
            # self.log("No active output pattern with student data lookup configured.")
        return student_info

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


    def _select_output_excel_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Excel File to Append to", "", "Excel Files (*.xlsx)")
        if path: 
            self.output_excel_path_edit.setText(path)
            # Save the path when it's selected
            settings = QSettings("OptiMark Pro", "Defaults")
            settings.setValue("output_append_path", path)
    
    def _format_identifier(self, value):
        if isinstance(value, str) and value.isdigit():
            return str(int(value))
        return value

    def _set_params_on_ui(self, params):
        self.current_image_processing_params.update(params)
        self.log("Internal image processing parameters updated.")

    def _populate_identifier_checkboxes(self):
        states = {cb.text(): cb.isChecked() for cb in self.identifier_checkboxes} if hasattr(self, 'identifier_checkboxes') else {}
        if self.identifier_layout is None: self.log("ERROR: identifier_layout is missing."); return
        while self.identifier_layout.count():
            item = self.identifier_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.identifier_checkboxes.clear()
        if not self.template_data:
            self.identifier_layout.addWidget(QLabel("<i>Load an answer key to see identifiers.</i>"), 0, 0, 1, 2)
            return
        identifier_rois = [roi for roi in self.template_data.get('rois', []) if roi.get('type') == 'Identifier']
        self.identifier_layout.addWidget(QLabel("<b>Select Identifiers to Match:</b>"), 0, 0, 1, 2)
        row, col = 1, 0
        for roi in identifier_rois:
            cb = QCheckBox(roi['name']); cb.setChecked(states.get(roi['name'], True))
            self.identifier_layout.addWidget(cb, row, col); self.identifier_checkboxes.append(cb)
            col = 1 - col
            if col == 0: row += 1
        self.identifier_layout.setRowStretch(row + 1, 1)

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
        selected_paths, _ = QFileDialog.getOpenFileNames(self, "Select Multiple Images", "", "Image Files (*.png *.jpg *.bmp)")
        if selected_paths:
            self._load_image_paths(sorted(selected_paths))

    def _select_image_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Image Folder")
        if folder_path:
            image_paths_to_load = []
            for root, _, files in os.walk(folder_path):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.bmp')):
                        image_paths_to_load.append(os.path.join(root, file))
            if image_paths_to_load:
                self._load_image_paths(sorted(image_paths_to_load))
            else:
                self.show_toast("No images found in the selected folder and its subfolders.", level='warning')

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
                detected_val = self._format_identifier(str(detected_ids.get(name, "")))
                key_val = self._format_identifier(str(key_ids.get(name, "")))
                if detected_val != key_val:
                    is_match = False
                    break # Mismatch found, move to the next key
            
            if is_match:
                self.log(f"Found matching answer key: {os.path.basename(key_data['path'])}")
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
        self.log("Scan process stopped by user.")
        self.show_toast("Scan stopped.", "warning")
        self.is_scan_stopped = True
        self._end_scan_session()

    def _pause_scan_for_manual_intervention(self, message, show_accept_button=True):
        if 0 <= self.current_image_index < len(self.image_paths):
            current_path = self.image_paths[self.current_image_index]
            self._update_image_status(current_path, "Error")
            
        self.log(f"Pausing scan for manual intervention: {message}")
        QMessageBox.warning(self, "Manual Intervention Required", message)
        self.btn_next_image.setVisible(False)
        self.btn_accept_manual_ids.setVisible(show_accept_button)
        self.btn_skip_image.setVisible(True)
        self.btn_rewrap_image.setVisible(True)

    def _validate_and_pause_if_needed(self):
        # Returns a status string: 'PASS', 'PAUSE', or 'SKIP'.

        # 1. Check for low-level scanning errors
        checked_identifiers = {cb.text() for cb in self.identifier_checkboxes if cb.isChecked()}
        if not self.scan_results: return 'PASS' # No results to validate, pass silently
        scanned_ids = self.scan_results.get('identifiers', {})
        error_messages = [f"Identifier '{n}' has a scan error or is missing. Value: '{scanned_ids.get(n, '')}'"
                          for n in checked_identifiers if not scanned_ids.get(n,'').strip() or any(e in scanned_ids.get(n,'') for e in ["ERR", "MULTI", "_"])]
        
        if error_messages:
            if self.skip_errors_checkbox.isChecked():
                self.log(f"Skipping image due to identifier scan errors: {'; '.join(error_messages)}")
                self._move_image_to_error_folder(self.current_image_index)
                return 'SKIP'
            else:
                message = "One or more required identifiers failed to scan correctly.\n\n" + "\n".join(error_messages) + "\n\nPlease correct the values, then click 'Accept & Continue' or 'Skip Image'."
                self._pause_scan_for_manual_intervention(message, show_accept_button=True)
                return 'PAUSE'

        # 2. If student data is loaded, check for a match.
        if self.student_data is not None and not self.student_data.empty:
            student_info = self._get_student_info(scanned_ids)
            if not student_info: # No match found
                lookup_roi_name = self.active_output_pattern.get('lookup_roi') if self.active_output_pattern else "configured lookup ROI"
                scanned_value = scanned_ids.get(lookup_roi_name, 'N/A') if lookup_roi_name != "configured lookup ROI" else 'N/A'
                message = f"Identifier value '{scanned_value}' for '{lookup_roi_name}' not found in student data."

                if self.skip_errors_checkbox.isChecked():
                    self.log(f"Skipping image: {message}")
                    self._move_image_to_error_folder(self.current_image_index)
                    return 'SKIP'
                else:
                    self._pause_scan_for_manual_intervention(message + "\nPlease correct the value, accept, or skip.", show_accept_button=True)
                    return 'PAUSE'
        
        # 3. All checks passed
        return 'PASS'

    def _process_current_image_manual_mode(self):
        self.btn_accept_manual_ids.setVisible(False)
        self.current_matched_key_path = None # Reset for new image

        if 0 <= self.current_image_index < len(self.image_paths):
            image_path = self.image_paths[self.current_image_index]
            if hasattr(self, 'scan_progress_label') and self.scan_progress_label:
                total_images = len(self.image_paths)
                current_num = self.current_image_index + 1
                self.scan_progress_label.setText(f"Scanning {current_num} of {total_images}")
            self._update_image_status(image_path, "Processing")
            self.log(f"Processing image {self.current_image_index + 1}/{len(self.image_paths)}: {os.path.basename(image_path)}")
            self.load_image(image_path)
            if self.run_auto_corner_detection():
                matching_key = self._find_matching_answer_key()
                if matching_key:
                    self.correct_answers_map = matching_key['answers']
                    self.current_matched_key_path = matching_key['path']
                    self.log(f"Applied matching answer key: {os.path.basename(matching_key['path'])}")
                    self._update_image_status(image_path, "Processing") # Update status with key
                else:
                    self.current_matched_key_path = "Not Found"
                    self._update_image_status(image_path, "Error") # Update status with key not found
                    self.show_toast(f"No matching answer key found for {os.path.basename(image_path)}. Skipping.", 'warning')
                    self._skip_current_image(); return
                validation_status = self._validate_and_pause_if_needed()
                if validation_status == 'PASS':
                    self.btn_next_image.setVisible(True)
                    self.btn_skip_image.setVisible(True)
                    self.btn_rewrap_image.setVisible(False)
                elif validation_status == 'SKIP':
                    self._skip_current_image()
                    return
        else:
            self.show_toast("All selected images have been processed.", 'info')
            self._end_scan_session()

    def _run_auto_batch_scan(self):
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
        if not self.run_auto_corner_detection():
            self.current_matched_key_path = "Scan Error"
            self._update_image_status(image_path, "Error")
            return
        
        matching_key = self._find_matching_answer_key()
        if not matching_key:
            message = f"No matching answer key found for {os.path.basename(image_path)}."
            self.current_matched_key_path = "Not Found"
            self._update_image_status(image_path, "Error")
            if self.skip_errors_checkbox.isChecked():
                self.log(f"ERROR: {message} Skipping image.")
                self.show_toast(f"{message} Skipping.", level='warning', duration=4000)
                self._move_image_to_error_folder(self.current_image_index)
                self._skip_current_image()
            else:
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
        
        if self.scan_results: self._save_scan_result()
        self._skip_current_image()

    def _skip_current_image(self):
        current_path = self.image_paths[self.current_image_index]
        log_msg = f"Skipping image: {os.path.basename(current_path)}"

        if current_path in self.image_list_items:
            item = self.image_list_items[current_path]
            if not item.text().startswith("[Done]"):
                self._update_image_status(current_path, "Skipped")
                self.log(log_msg)
            else:
                self.log(f"Moving to next image after: {os.path.basename(current_path)}")
        else:
            self.log(log_msg)

        self.current_image_index += 1
        if self.radio_scan_auto.isChecked():
            QApplication.processEvents()
            self._run_auto_batch_scan()
        else:
            self._process_current_image_manual_mode()

    def _accept_manual_ids_and_continue(self):
        self.log("Attempting to accept manual identifiers...")

        # The identifier values in self.scan_results are updated automatically by the UI widgets' signals.
        # We just need to re-run the validation.
        validation_status = self._validate_and_pause_if_needed()
        if validation_status != 'PASS':
            # The validation failed again (e.g., still no match), and the function has already re-paused or determined a skip.
            self.show_toast("Validation still fails. Please correct the identifier or skip.", 'warning')
            return

        # If we get here, validation passed.
        self.log("Manual identifiers accepted. Saving result and continuing scan.")
        self.btn_accept_manual_ids.setVisible(False)
        self.btn_rewrap_image.setVisible(False)
        self._save_scan_result()
        
        if self.current_image_index >= len(self.image_paths) - 1:
            self.log("Processing final image after manual correction.")
            self._end_scan_session()
        else:
            self._skip_current_image()

    def _process_next_image(self):
        self.btn_rewrap_image.setVisible(False)
        if self.scan_results:
            if any(not self.scan_results.get('identifiers', {}).get(n) for n in {cb.text() for cb in self.identifier_checkboxes if cb.isChecked()}):
                self.show_toast("A required identifier is empty. Please fill it.", 'warning'); return
            self._save_scan_result()

        if self.current_image_index >= len(self.image_paths) - 1:
            self.log("Processing final image in manual mode.")
            self._end_scan_session()
        else:
            self._skip_current_image()

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
