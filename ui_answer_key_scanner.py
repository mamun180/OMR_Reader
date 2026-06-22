from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, 
                             QGraphicsView, QGraphicsScene, QFileDialog, QMessageBox, QGraphicsPixmapItem, QInputDialog,
                             QSplitter, QScrollArea, QCheckBox, QButtonGroup, QLineEdit, QGroupBox, QSlider, QToolButton, QGraphicsItem,
                             QGridLayout, QRadioButton, QComboBox, QApplication, QTextEdit, QDialog, QTabWidget, QFormLayout, QDialogButtonBox, QListWidget)
from PyQt6.QtGui import QImage, QPixmap, QColor, QBrush, QPen, QPolygonF
from PyQt6.QtCore import Qt, QRectF, QPointF, QEvent, QSettings, QDateTime
import sys
import json
import cv2
import numpy as np
import datetime
import os
from core_omr import OMREngine
from scanner_manager import ScannerManager
from theme import apply_stylesheet_and_floatation
from directory_manager import get_template_dir, get_answer_key_dir
from settings_manager import save_last_path, load_last_path
from cache_manager import apply_identifier_reference


class ManualKeyCreatorDialog(QDialog):
    def __init__(self, template_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manual Answer Key Creator")
        self.setMinimumWidth(600)
        self.template_data = template_data
        self.identifier_edits = {}
        self.question_edits = {}
        self.all_widgets = []

        # Main Layout
        self.main_layout = QVBoxLayout(self)

        # --- Identifiers ---
        id_group = QGroupBox("Answer Key Identifiers")
        id_group.setObjectName("solid_panel_groupbox")
        id_form_layout = QFormLayout(id_group)
        
        identifier_rois = [roi for roi in self.template_data.get('rois', []) if roi.get('type') == 'Identifier' and roi.get('subtype') == 'Answer Script Identifier']
        
        for roi in identifier_rois:
            name = roi.get('name')
            widget = None
            is_single_dimension = (int(roi.get('rows', 0)) == 1 or int(roi.get('cols', 0)) == 1)
            has_values = roi.get('values') and isinstance(roi.get('values'), list)

            if is_single_dimension and has_values:
                widget = QComboBox()
                widget.addItems([""] + roi['values'])
            else:
                widget = QLineEdit()
            
            self.identifier_edits[name] = widget
            self.all_widgets.append(widget)
            id_form_layout.addRow(QLabel(f"{name}:"), widget)
            
        self.main_layout.addWidget(id_group)

        # --- Answers ---
        ans_group = QGroupBox("Answer Key")
        ans_group.setObjectName("solid_panel_groupbox")
        ans_layout = QVBoxLayout(ans_group)
        
        self.ans_tabs = QTabWidget()

        # Comma Separated Tab
        comma_tab = QWidget()
        comma_layout = QVBoxLayout(comma_tab)
        comma_layout.addWidget(QLabel("Enter answers separated by commas (e.g., A,B,C,D,A)"))
        self.comma_answers_edit = QTextEdit()
        self.comma_answers_edit.setPlaceholderText("A,B,C,D,A...")
        comma_layout.addWidget(self.comma_answers_edit)
        self.all_widgets.append(self.comma_answers_edit)
        
        # By Question Tab
        by_question_tab = QWidget()
        by_question_layout = QVBoxLayout(by_question_tab)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        form_layout = QFormLayout(scroll_content)
        
        total_questions = 0
        answer_rois = [r for r in self.template_data.get('rois', []) if r.get('type') == 'Answer']
        for r in answer_rois:
            try:
                total_questions += int(r.get('rows', 0))
            except (ValueError, TypeError):
                continue
        
        question_widgets_in_order = []
        for i in range(1, total_questions + 1):
            widget = QLineEdit()
            widget.setFixedWidth(100)
            widget.setPlaceholderText("e.g., A,B")
            self.question_edits[str(i)] = widget
            question_widgets_in_order.append(widget)
            form_layout.addRow(QLabel(f"Question {i}:"), widget)

        scroll_area.setWidget(scroll_content)
        by_question_layout.addWidget(scroll_area)

        self.ans_tabs.addTab(comma_tab, "Comma Separated")
        self.ans_tabs.addTab(by_question_tab, "By Question")
        ans_layout.addWidget(self.ans_tabs)
        self.main_layout.addWidget(ans_group)

        # --- Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_key)
        self.button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(self.button_box)

        # Combine question widgets to all_widgets list depending on tab visibility
        # For now, we'll just add the "By Question" ones for simplicity
        self.all_widgets.extend(question_widgets_in_order)
        
        # Install event filter on all input widgets
        for widget in self.all_widgets:
            widget.installEventFilter(self)

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress and event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Down, Qt.Key.Key_Up]:
            if source in self.all_widgets:
                try:
                    current_index = self.all_widgets.index(source)
                    if event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Down]:
                        if current_index < len(self.all_widgets) - 1:
                            next_widget = self.all_widgets[current_index + 1]
                            next_widget.setFocus()
                            if isinstance(next_widget, QComboBox):
                                next_widget.showPopup()
                            return True
                    elif event.key() == Qt.Key.Key_Up:
                        if current_index > 0:
                            prev_widget = self.all_widgets[current_index - 1]
                            prev_widget.setFocus()
                            if isinstance(prev_widget, QComboBox):
                                prev_widget.showPopup()
                            return True
                except (ValueError, IndexError):
                    pass
        return super().eventFilter(source, event)

    def save_key(self):
        # 1. Gather Identifiers
        identifiers = {}
        for name, widget in self.identifier_edits.items():
            scanned_value = ""
            if isinstance(widget, QComboBox):
                scanned_value = widget.currentText()
            else: # QLineEdit
                scanned_value = widget.text()
            identifiers[name] = apply_identifier_reference(name, scanned_value)

        # 2. Gather Answers
        answers = {}
        current_tab_text = self.ans_tabs.tabText(self.ans_tabs.currentIndex())
        if current_tab_text == "Comma Separated":
            ans_string = self.comma_answers_edit.toPlainText().strip()
            if ans_string:
                ans_list = [ans.strip().upper() for ans in ans_string.split(',')]
                for i, ans in enumerate(ans_list, 1):
                    answers[str(i)] = [ans]
        else: # By Question
            for q_num, edit in self.question_edits.items():
                ans = edit.text().strip().upper()
                if ans:
                    answers[q_num] = [a.strip() for a in ans.split(',')]

        if not any(identifiers.values()) or not answers:
            QMessageBox.warning(self, "Missing Data", "Please fill in at least one identifier and some answers.")
            return

        # 3. Construct data object
        data_to_save = {
            'template': self.template_data,
            'image_settings': {},
            'identifiers': identifiers,
            'answers': answers
        }

        # 4. Generate filename and show save dialog
        filename = self.parent()._generate_answer_key_filename(identifiers)
        answer_key_dir = get_answer_key_dir()
        save_path = os.path.join(answer_key_dir, f"{filename}.json")

        dialog_key = "Save Manual Answer Key"
        
        # Determine the initial directory for the QFileDialog
        last_saved_path = load_last_path(dialog_key)
        if last_saved_path and os.path.isfile(last_saved_path):
            initial_dir = os.path.dirname(last_saved_path)
        else:
            initial_dir = get_answer_key_dir()

        # The suggested filename should ALWAYS be based on the current identifiers
        suggested_filename_with_ext = f"{filename}.json"
        
        # Combine the initial directory with the suggested filename
        # QFileDialog.getSaveFileName expects a full path for the initial filename suggestion
        full_initial_path_suggestion = os.path.join(initial_dir, suggested_filename_with_ext)

        path, _ = QFileDialog.getSaveFileName(self, dialog_key, full_initial_path_suggestion, "JSON Files (*.json)")

        if path:
            save_last_path(dialog_key, path)
            try:
                with open(path, 'w') as f:
                    json.dump(data_to_save, f, indent=4)
                QMessageBox.information(self, "Success", f"Answer key saved to:\n{path}")
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save answer key.\nError: {e}")


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
        layout = QHBoxLayout(self); layout.addWidget(QLabel(f"<b>{self.roi_name}</b>:"))
        self.value_edit = QLineEdit(str(current_value)); layout.addWidget(self.value_edit)

class IdentifierDropdownWidget(QWidget):
    def __init__(self, roi_name, roi_subtype, options, current_value, parent=None):
        super().__init__(parent); self.roi_name = roi_name; self.roi_subtype = roi_subtype
        layout = QHBoxLayout(self); layout.addWidget(QLabel(f"<b>{self.roi_name}</b>:"))
        self.combo_box = QComboBox(self); self.combo_box.addItems(options)
        if current_value and current_value in options: self.combo_box.setCurrentText(current_value)
        layout.addWidget(self.combo_box)

class QuestionAnswerWidget(QWidget):
    def __init__(self, q_num, options, selected_options, allow_multiple, parent=None):
        super().__init__(parent); self.q_num = q_num
        layout = QHBoxLayout(self); layout.addWidget(QLabel(f"Q{self.q_num}:"))
        self.option_group = QButtonGroup(self); self.option_group.setExclusive(not allow_multiple)
        for i, option_char in enumerate(options):
            checkbox = QCheckBox(option_char)
            if option_char in selected_options: checkbox.setChecked(True)
            self.option_group.addButton(checkbox, i); layout.addWidget(checkbox)
        layout.addStretch()

class AnswerKeyScannerWindow(QWidget):
    DEFAULT_IMAGE_SETTINGS = {
        'contrast': 1.3, 'brightness': 0, 'blur': 3, 'rotation': 0.0,
        'adaptive_c': 3, 'threshold': 0.05, 'method': 'contour',
        'grayscale': False, 'transparency': 143,
        'allow_multiple_answers': True
    }

    def __init__(self):
        super().__init__()
        self.engine = OMREngine()
        self.image_paths = [] # List to store paths of all loaded images
        self.current_image_index = -1 # Index of the image currently being processed
        main_layout = QVBoxLayout(self)
        
        toolbar_layout = QHBoxLayout()

        self.btn_load_image = QPushButton("Load Image")
        self.btn_load_image.setMinimumHeight(50)
        self.btn_load_image.clicked.connect(self.load_image)
        toolbar_layout.addWidget(self.btn_load_image)

        self.btn_prev_image = QPushButton("Previous Image")
        self.btn_prev_image.setMinimumHeight(50)
        self.btn_prev_image.clicked.connect(self._load_previous_image)
        self.btn_prev_image.setEnabled(False) # Disabled until images are loaded
        toolbar_layout.addWidget(self.btn_prev_image)

        self.btn_next_image = QPushButton("Next Image")
        self.btn_next_image.setMinimumHeight(50)
        self.btn_next_image.clicked.connect(self._load_next_image)
        self.btn_next_image.setEnabled(False) # Disabled until images are loaded
        toolbar_layout.addWidget(self.btn_next_image)

        self.btn_create_manual_key = QPushButton("Create Answer Key")
        self.btn_create_manual_key.setMinimumHeight(50)
        self.btn_create_manual_key.clicked.connect(self.open_manual_key_creator)
        toolbar_layout.addWidget(self.btn_create_manual_key)

        self.btn_save = QPushButton("Save Answer Key")
        self.btn_save.setMinimumHeight(50)
        self.btn_save.clicked.connect(self.save_answer_key)
        self.btn_save.setEnabled(False)
        toolbar_layout.addWidget(self.btn_save)

        toolbar_layout.addStretch()

        # --- Image Settings Group ---
        img_settings_group = QGroupBox("Image Settings")
        img_settings_layout = QHBoxLayout(img_settings_group)
        img_settings_layout.setContentsMargins(5, 5, 5, 5)

        self.btn_save_settings = QPushButton("Save as Default")
        self.btn_save_settings.setFixedWidth(120)
        self.btn_save_settings.clicked.connect(self.save_image_settings)
        img_settings_layout.addWidget(self.btn_save_settings)

        self.btn_load_defaults = QPushButton("Load Defaults")
        self.btn_load_defaults.setFixedWidth(120)
        self.btn_load_defaults.clicked.connect(self._load_default_settings)
        img_settings_layout.addWidget(self.btn_load_defaults)
        toolbar_layout.addWidget(img_settings_group)

        # This button appears dynamically
        self.btn_manual_warp = QPushButton("Manual Scan")
        self.btn_manual_warp.setMinimumHeight(50)
        self.btn_manual_warp.clicked.connect(self.run_scan_process)
        self.btn_manual_warp.setVisible(False)
        toolbar_layout.addWidget(self.btn_manual_warp)

        main_layout.addLayout(toolbar_layout)

        # Connections for template selection are no longer needed as it's automatic


        # Main 3-panel splitter
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- 1. Left Panel (Settings + Log + Image List) ---
        left_panel_widget = QWidget()
        left_panel_widget.setObjectName("scanner_left_panel")
        left_panel_layout = QVBoxLayout(left_panel_widget)
        left_panel_layout.setContentsMargins(0,0,0,0)

        # Image List
        self.image_list_widget = QListWidget()
        self.image_list_widget.setMinimumHeight(100)
        self.image_list_widget.currentItemChanged.connect(self._on_image_list_selection_changed)
        image_list_group = QGroupBox("Loaded Images")
        image_list_layout = QVBoxLayout(image_list_group)
        image_list_layout.addWidget(self.image_list_widget)
        left_panel_layout.addWidget(image_list_group)

        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)

        controls_group = QGroupBox("Processing Controls")
        controls_layout = QVBoxLayout(controls_group)
        
        def add_control(label_text, min_val, max_val, default_val, edit_scale=1, text_format_fn=None):
            layout = QHBoxLayout()
            layout.addWidget(QLabel(label_text))
            slider, line_edit = self._create_slider_combo(min_val, max_val, default_val, edit_scale, text_format_fn)
            layout.addWidget(slider)
            layout.addWidget(line_edit)
            controls_layout.addLayout(layout)
            return slider, line_edit

        self.contrast_slider, self.contrast_edit = add_control("Contrast:", 10, 30, 13, 10)
        self.brightness_slider, self.brightness_edit = add_control("Brightness:", -100, 100, 30)
        self.blur_slider, self.blur_edit = add_control("Blur Kernel:", 0, 10, 2, 1, lambda v: f"{v*2+1}")
        self.rotation_slider, self.rotation_edit = add_control("Rotation (°):", -50, 50, 0, 10)
        self.adaptive_c_slider, self.adaptive_c_edit = add_control("B&W Threshold (C):", 0, 15, 3)
        self.threshold_slider, self.threshold_edit = add_control("Fill Threshold (%):", 5, 100, 7)
        self.transparency_slider, self.transparency_edit = add_control("Fill Alpha:", 0, 255, 143)
        
        self.grayscale_checkbox = QCheckBox("Grayscale Preview"); controls_layout.addWidget(self.grayscale_checkbox)
        self.multi_answer_checkbox = QCheckBox("Allow Multiple Answers per Question"); controls_layout.addWidget(self.multi_answer_checkbox)
        
        controls_layout.addWidget(QLabel("Scan Mode:"))
        self.detection_group = QButtonGroup(self); self.pixel_count_radio = QRadioButton("Pixel Count"); self.pixel_count_radio.setChecked(True); self.contour_radio = QRadioButton("Contour Detection")
        self.detection_group.addButton(self.pixel_count_radio, 1); self.detection_group.addButton(self.contour_radio, 2)
        radio_layout = QHBoxLayout(); radio_layout.addWidget(self.pixel_count_radio); radio_layout.addWidget(self.contour_radio); controls_layout.addLayout(radio_layout)
        
        self.btn_rescan = QPushButton("Re-Scan"); self.btn_rescan.clicked.connect(self.rescan_with_new_parameters); self.btn_rescan.setEnabled(False); controls_layout.addWidget(self.btn_rescan)
        
        controls_scroll.setWidget(controls_group)
        left_panel_layout.addWidget(controls_scroll)
        
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        log_layout.addWidget(self.log_panel)
        left_panel_layout.addWidget(log_group)
        
        self.main_splitter.addWidget(left_panel_widget)

        # --- 2. Center Panel (Image View) ---
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0,0,0,0)
        self.scene = QGraphicsScene()
        self.view = ScannerGraphicsView(self.scene, self)
        canvas_layout.addWidget(self.view)
        self.main_splitter.addWidget(canvas_container)

        # --- 3. Right Panel (Answers) ---
        right_panel_wrapper = QWidget()
        right_panel_wrapper.setObjectName("scanner_right_panel")
        right_panel_layout = QVBoxLayout(right_panel_wrapper)
        right_panel_layout.setContentsMargins(0,0,0,0)

        self.answers_scroll_area = QScrollArea()
        self.answers_scroll_area.setWidgetResizable(True)
        # The QScrollArea itself doesn't need an objectName if its parent wrapper handles styling

        self.answers_widget = QWidget()
        self.answers_layout = QVBoxLayout(self.answers_widget)
        self.answers_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.answers_layout.setContentsMargins(0,0,0,0) # Ensure content fills transparent area
        self.answers_layout.setSpacing(0) # Reduce spacing for better look
        self.answers_scroll_area.setWidget(self.answers_widget)
        right_panel_layout.addWidget(self.answers_scroll_area)
        self.main_splitter.addWidget(right_panel_wrapper)

        main_layout.addWidget(self.main_splitter, 1)
        # Set splitter sizes after the window has been shown and sized
        self.shown = False

        self.zoom_in_button = QToolButton(self.view); self.zoom_in_button.setText('+'); self.zoom_in_button.clicked.connect(self.zoom_in)
        self.zoom_out_button = QToolButton(self.view); self.zoom_out_button.setText('-'); self.zoom_out_button.clicked.connect(self.zoom_out)
        
        inspector_layout = QHBoxLayout(); inspector_layout.setContentsMargins(4,0,4,0)
        self.inspector_pixel_label = QLabel("Pixel Count: N/A"); self.inspector_contour_label = QLabel("Contour Area: N/A"); self.inspector_fill_label = QLabel("Fill %: N/A")
        for label in [self.inspector_pixel_label, self.inspector_contour_label, self.inspector_fill_label]: inspector_layout.addWidget(label); inspector_layout.addStretch()
        main_layout.addLayout(inspector_layout)

        self.template_data, self.current_image, self.warped_image, self.scan_results = None, None, None, None
        self.roi_items, self.manual_corner_items, self.corner_handles = [], [], []
        self.is_manual_corner_mode = False
        self.manual_corners, self.corner_polygon = [], None
        self.identifier_widgets = {}
        self.question_widgets = {}
        self.image_pixmap_item = None
        self.homography_matrix = None
        self.warp_matrix = None
        
        self.transparency_slider.valueChanged.connect(self.rescan_with_new_parameters)
        self.grayscale_checkbox.stateChanged.connect(self.rescan_with_new_parameters)
        self.multi_answer_checkbox.stateChanged.connect(self.rescan_with_new_parameters)

        self._load_settings_from_qsettings()
        
        self.apply_theme()

    def load_student_data(self):
        pass

    def apply_theme(self):
        apply_stylesheet_and_floatation(self)

    def open_manual_key_creator(self):
        if not self.template_data:
            self._load_master_template()
            if not self.template_data:
                QMessageBox.warning(self, "Template Missing", "A master template must be set in the main settings page before you can create a manual key.")
                return
        
        dialog = ManualKeyCreatorDialog(self.template_data, self)
        apply_stylesheet_and_floatation(dialog)
        dialog.exec()

    def log(self, message):
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.log_panel.append(f"[{timestamp}] {message}")

    def _create_slider_combo(self, min_val, max_val, default_val, edit_scale=1, text_format_fn=None):
        slider = QSlider(Qt.Orientation.Horizontal); slider.setRange(min_val, max_val); slider.setValue(default_val)
        line_edit = QLineEdit(); line_edit.setFixedWidth(50)
        def update_text_from_slider(value):
            text = text_format_fn(value) if text_format_fn else f"{value / edit_scale:.1f}" if edit_scale != 1 else str(value)
            line_edit.setText(text)
        def update_slider_from_text():
            try: value = float(line_edit.text().replace('%', '').replace('°', '')); slider.setValue(int(value * edit_scale))
            except ValueError: slider.setValue(default_val)
        slider.valueChanged.connect(update_text_from_slider); slider.valueChanged.connect(self.rescan_with_new_parameters)
        line_edit.editingFinished.connect(update_slider_from_text); line_edit.editingFinished.connect(self.rescan_with_new_parameters)
        update_text_from_slider(default_val); return slider, line_edit

    def showEvent(self, event):
        super().showEvent(event)
        if not self.shown:
            self.shown = True
            total_width = self.main_splitter.width()
            self.main_splitter.setSizes([int(total_width * 0.20), int(total_width * 0.60), int(total_width * 0.20)])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        view_rect = self.view.viewport().rect()
        button_size_in = self.zoom_in_button.sizeHint()
        button_size_out = self.zoom_out_button.sizeHint()
        margin = 10
        self.zoom_in_button.move(view_rect.left() + margin, view_rect.bottom() - (button_size_in.height() + button_size_out.height()) - margin * 2)
        self.zoom_out_button.move(view_rect.left() + margin, view_rect.bottom() - button_size_out.height() - margin)
    
    def zoom_in(self): self.view.scale(1.2, 1.2)
    def zoom_out(self): self.view.scale(0.8, 0.8)

    def reset_state(self, full_reset=True):
        self.btn_save.setEnabled(False); self.btn_manual_warp.setVisible(False); self.btn_rescan.setEnabled(False)
        self.scan_results, self.template_data, self.warped_image, self.homography_matrix, self.warp_matrix = None, None, None, None, None
        self.is_manual_corner_mode = False; self.manual_corners = []; self.image_pixmap_item = None
        for i in reversed(range(self.answers_layout.count())):
            if (widget := self.answers_layout.itemAt(i).widget()): widget.deleteLater()
        self.identifier_widgets.clear()
        self.question_widgets.clear()

        # Clear all QGraphicsItem lists to prevent crashes from stale references
        self.roi_items.clear()
        self.manual_corner_items.clear()
        self.corner_handles.clear()
        self.corner_polygon = None
        if hasattr(self, 'bubble_items'):
            self.bubble_items.clear()

        if full_reset: 
            self.current_image = None
            self.scene.clear()

    def load_image(self):
        dialog_key = "Load Answer Key Image"
        initial_path = load_last_path(dialog_key)
        # Allow multiple files to be selected
        paths, _ = QFileDialog.getOpenFileNames(self, dialog_key, initial_path, "Image Files (*.png *.jpg *.bmp)")
        
        if paths:
            save_last_path(dialog_key, os.path.dirname(paths[0]))
            self.image_paths = sorted(paths) # Store all selected paths
            self.current_image_index = 0 # Start with the first image
            
            # Populate the image list widget
            self.image_list_widget.clear()
            for p in self.image_paths:
                self.image_list_widget.addItem(os.path.basename(p))
            
            self._load_current_image_for_processing()
            self._update_navigation_buttons_state()
            self.log(f"Loaded {len(self.image_paths)} images.")
        else:
            self.log("No images selected.")

    def _load_current_image_for_processing(self):
        if not self.image_paths or not (0 <= self.current_image_index < len(self.image_paths)):
            self.reset_state(full_reset=True)
            self.log("No image to process or invalid index.")
            return

        image_path = self.image_paths[self.current_image_index]
        self.image_list_widget.setCurrentRow(self.current_image_index) # Select in list widget

        self.reset_state(full_reset=False) # Keep template data for now
        self.current_image = cv2.imread(image_path)
        if self.current_image is None:
            QMessageBox.critical(self, "Error", f"Could not read image: {image_path}")
            self.reset_state(full_reset=True)
            return
        
        self.display_image(self.current_image)
        self.log(f"Processing image {self.current_image_index + 1}/{len(self.image_paths)}: {os.path.basename(image_path)}")
        self._load_master_template() # This will try to auto-detect corners and scan

    def _load_next_image(self):
        if self.current_image_index < len(self.image_paths) - 1:
            self.current_image_index += 1
            self._load_current_image_for_processing()
            self._update_navigation_buttons_state()
        else:
            self.log("No more images to process.")

    def _load_previous_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self._load_current_image_for_processing()
            self._update_navigation_buttons_state()
        else:
            self.log("Already at the first image.")

    def _update_navigation_buttons_state(self):
        self.btn_prev_image.setEnabled(self.current_image_index > 0)
        self.btn_next_image.setEnabled(self.current_image_index < len(self.image_paths) - 1)
        
    def _on_image_list_selection_changed(self, current, previous):
        if current:
            new_index = self.image_list_widget.row(current)
            if new_index != self.current_image_index:
                self.current_image_index = new_index
                self._load_current_image_for_processing()
                self._update_navigation_buttons_state()

    def _load_master_template(self):
        settings = QSettings("OptiMark Pro", "Defaults")
        master_template_path = settings.value("master_template", "")
        if master_template_path and os.path.exists(master_template_path):
            self.log(f"Master template found. Loading: {os.path.basename(master_template_path)}")
            try:
                with open(master_template_path, 'r') as f:
                    self.template_data = json.load(f)
                # If an image is also loaded, we can run detection on it
                if self.current_image is not None:
                     self._create_right_panel_widgets()
                     self.run_auto_corner_detection()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load or parse master template: {str(e)}")
                self.template_data = None
        else:
            self.log("Master template not set or not found.")

    def load_template(self, path=None):
        if self.current_image is None: QMessageBox.warning(self, "No Image", "Please load an image first."); return
        
        dialog_key = "Load Template"
        if path is None: 
            initial_path = load_last_path(dialog_key) or get_template_dir()
            path, _ = QFileDialog.getOpenFileName(self, dialog_key, initial_path, "JSON Files (*.json)")
        if not path: return

        save_last_path(dialog_key, path) # Save the selected path

        # Reset state for the new template, but keep the current image
        self.reset_state(full_reset=False)
        # Re-display the image to clear any drawings from the old template
        self.display_image(self.current_image)

        try:
            with open(path, 'r') as f:
                self.template_data = json.load(f)

            
            self._create_right_panel_widgets()
            self.run_auto_corner_detection()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load or parse template: {str(e)}")

    def run_auto_corner_detection(self):
        for item in self.corner_handles: self.scene.removeItem(item)
        if self.corner_polygon: self.scene.removeItem(self.corner_polygon)
        self.corner_handles, self.corner_polygon = [], None
        corners = self.engine.detector.find_corners(self.current_image, self.template_data.get('corner_properties', {}))
        if corners is not None: self.run_scan_process(corners=corners)
        else:
            QMessageBox.warning(self, "Detection Failed", "Automatic corner detection failed. Manual options are now available."); self.btn_manual_warp.setVisible(True)
            self.enter_manual_corner_mode()
    
    def enter_manual_corner_mode(self):
        self.is_manual_corner_mode = True; self.manual_corners = []
        for handle in self.corner_handles: self.scene.removeItem(handle)
        self.corner_handles.clear()
        QMessageBox.information(self, "Manual Selection", "Click the 4 corners of the OMR sheet.")

    def add_manual_corner(self, point):
        if not self.is_manual_corner_mode or len(self.corner_handles) >= 4: return
        handle = CornerHandle(point.x(), point.y(), self)
        self.scene.addItem(handle); self.corner_handles.append(handle)
        if len(self.corner_handles) == 4: self.is_manual_corner_mode = False; self.update_corner_polygon()

    def update_corner_polygon(self):
        if self.corner_polygon and self.corner_polygon.scene(): self.scene.removeItem(self.corner_polygon)
        points = [handle.pos() for handle in self.corner_handles]
        if len(points) == 4: self.corner_polygon = self.scene.addPolygon(QPolygonF(points), QPen(QColor("red"), 2))

    def run_scan_process(self, corners=None):
        if corners is None and len(self.corner_handles) < 4:
            QMessageBox.warning(self, "Error", "4 corner markers must be present.")
            return
        
        try:
            page_corners = corners if corners is not None else np.array([(h.pos().x(), h.pos().y()) for h in self.corner_handles], dtype="float32")
            
            template_corners = np.array(self.template_data.get('template_corners'), dtype="float32")
            box_points_relative = self.template_data.get('box_points_relative', [])
            if len(box_points_relative) != 4:
                raise ValueError("Template is missing 'box_points_relative'. Cannot warp content box.")
            
            tl_corner_template = template_corners[0]
            template_box_points_abs = np.array([[p['x'] + tl_corner_template[0], p['y'] + tl_corner_template[1]] for p in box_points_relative], dtype="float32")

            H, _ = cv2.findHomography(template_corners, page_corners)
            if H is None:
                raise ValueError("Could not compute homography from page corners.")
            self.homography_matrix = H

            new_box_points = cv2.perspectiveTransform(template_box_points_abs.reshape(-1, 1, 2), H)
            warped_image, warp_matrix = self.engine.four_point_transform(self.current_image, new_box_points.reshape(4, 2))

            if warped_image is None:
                raise ValueError("Failed to warp the content box.")
            
            self.warped_image = warped_image
            self.warp_matrix = warp_matrix
            self.display_image(self.warped_image)
            self.rescan_with_new_parameters()
            self.btn_save.setEnabled(True)
            self.btn_rescan.setEnabled(True)
        except Exception as e:
            self.log(f"Processing Error: {str(e)}")
            QMessageBox.critical(self, "Processing Error", f"An error occurred during scanning:\n{str(e)}")

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
            self.log("Starting re-scan with new parameters...")
            params = self.get_current_params()
            preview_image = self._get_processed_preview_image(self.warped_image, params)
            if preview_image is None: 
                self.log("Preview image generation failed.")
                return

            for item_group in self.roi_items:
                for item in item_group:
                    if item and item.scene(): self.scene.removeItem(item)
            self.roi_items.clear()
            for item in getattr(self, 'bubble_items', []):
                if item and item.scene(): self.scene.removeItem(item)
            self.bubble_items = []

            h, w, ch = preview_image.shape
            qt_image = QImage(cv2.cvtColor(preview_image, cv2.COLOR_BGR2RGB).data, w, h, ch * w, QImage.Format.Format_RGB888)
            if self.image_pixmap_item and self.image_pixmap_item.scene(): self.image_pixmap_item.setPixmap(QPixmap.fromImage(qt_image))
            else: self.image_pixmap_item = self.scene.addPixmap(QPixmap.fromImage(qt_image))

            self._draw_template_on_scene(preview_image, draw_rois=True)
            self._scan_scene_grid(preview_image, params)
            self._update_widgets_from_scan()
            self.log(f"Re-scan complete. Found {len(getattr(self, 'bubble_items', []))} filled bubbles.")
        except Exception as e: 
            self.log(f"Re-Scan Error: {e}")
            QMessageBox.critical(self, "Re-Scan Error", f"An error occurred during re-scan:\n{e}")
    
    def get_current_params(self):
        return {
            'contrast': float(self.contrast_edit.text()), 'brightness': int(self.brightness_edit.text()),
            'blur': int(self.blur_edit.text().split('x')[0]), 'rotation': float(self.rotation_edit.text()),
            'adaptive_c': int(self.adaptive_c_edit.text()), 'threshold': float(self.threshold_edit.text()) / 100.0,
            'method': 'contour' if self.contour_radio.isChecked() else 'pixel_count',
            'grayscale': self.grayscale_checkbox.isChecked(), 'transparency': self.transparency_slider.value(),
            'allow_multiple_answers': self.multi_answer_checkbox.isChecked()
        }

    def _get_target_rois(self):
        """Returns a filtered list of ROIs that should be processed and displayed."""
        if not self.template_data:
            return []
        return [
            roi for roi in self.template_data.get('rois', [])
            if roi.get('subtype') == 'Answer Script Identifier'
        ]

    def _draw_template_on_scene(self, image_to_draw_on, draw_rois=True):
        if not draw_rois or not self.template_data or image_to_draw_on is None: return
        if self.homography_matrix is None or self.warp_matrix is None:
            self.log("Cannot draw template: transformation matrices not available.")
            return

        combined_matrix = self.warp_matrix @ self.homography_matrix
        
        target_rois = self._get_target_rois()
        for roi_data in target_rois:
            roi_corners = np.array([
                [roi_data['x'], roi_data['y']],
                [roi_data['x'] + roi_data['width'], roi_data['y']],
                [roi_data['x'] + roi_data['width'], roi_data['y'] + roi_data['height']],
                [roi_data['x'], roi_data['y'] + roi_data['height']]
            ], dtype=np.float32)

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
            if 'rows' in roi_data and 'cols' in roi_data:
                rows, cols = int(roi_data['rows']), int(roi_data['cols'])
            elif 'questions' in roi_data and 'options' in roi_data:
                rows, cols = int(roi_data['questions']), int(roi_data['options'])
            else:
                rows, cols = 0, 0
            
            # self.log(f"Drawing grid for {roi_data['name']} with {rows} rows, {cols} cols.")
            if rows > 1:
                for i in range(1, rows): y_pos = rect.y() + i * (rect.height() / rows); grid_lines.append(self.scene.addLine(rect.left(), y_pos, rect.right(), y_pos, grid_pen))
            if cols > 1:
                for i in range(1, cols): x_pos = rect.x() + i * (rect.width() / cols); grid_lines.append(self.scene.addLine(x_pos, rect.top(), x_pos, rect.bottom(), grid_pen))
        except (ValueError, KeyError):
            self.log(f"Could not draw grid for {roi_data['name']}: Invalid 'rows' or 'cols' values.")
            pass
        return grid_lines

    def _scan_scene_grid(self, image_to_scan, params):
        if image_to_scan is None or not self.template_data: return
        self.scan_results = {'identifiers': {}, 'answers': {}, 'errors': {}}
        all_filled_bubbles_info = []

        target_rois = self._get_target_rois()

        for i, roi_data in enumerate(target_rois):
            if i >= len(self.roi_items): 
                self.log(f"Warning: ROI item mismatch for '{roi_data.get('name')}'. Skipping scan for this ROI.")
                continue

            rect_item = self.roi_items[i][0]; rect = rect_item.rect()
            
            if rect.width() <= 0 or rect.height() <= 0: continue

            roi_image = image_to_scan[int(rect.y()):int(rect.y()+rect.height()), int(rect.x()):int(rect.x()+rect.width())]
            roi_name = roi_data.get('name', f'roi_{i}')
            
            if roi_data.get('type') == 'qrcode': 
                self.scan_results['identifiers'][roi_name] = self.engine.read_qr(roi_image)
                continue
            
            try:
                rows, cols = 0, 0
                if 'rows' in roi_data and 'cols' in roi_data:
                    rows, cols = int(roi_data['rows']), int(roi_data['cols'])
                elif 'questions' in roi_data and 'options' in roi_data:
                    rows, cols = int(roi_data['questions']), int(roi_data['options'])
                if rows == 0 or cols == 0: continue
            except (ValueError, KeyError): 
                self.scan_results['errors'][roi_name] = "Invalid grid dimensions."
                continue
            
            metric_matrix, all_coords = self.engine._process_grid(roi_image, rows, cols, params)
            if not metric_matrix: 
                self.scan_results['errors'][roi_name] = "Failed to process grid."
                continue

            threshold = params.get('threshold', 0.3)
            matrix = [[(1 if metric > threshold else 0) for metric in row] for row in metric_matrix]

            if roi_data['type'] == 'Identifier':
                value = ""
                vals = roi_data.get('values', [])
                if roi_data.get('order') == 'Column Wise':
                    mat = np.array(matrix)
                    if cols == 1 and mat.ndim == 2: # Single-choice dropdown
                        detected_indices = np.where(mat[:, 0] == 1)[0]
                        if len(detected_indices) == 1:
                            idx = detected_indices[0]
                            value = vals[idx] if idx < len(vals) else "ERR"
                        else:
                            value = "MULTIPLE"
                    else: # Multi-digit textbox
                        if mat.ndim == 2 and mat.shape[1] == cols and all(np.sum(mat[:, c]) == 1 for c in range(cols)):
                            parts = []
                            for c in range(cols):
                                idx = np.argmax(mat[:, c])
                                parts.append(vals[idx] if idx < len(vals) else "?")
                            value = "".join(parts)
                        else:
                            value = "ERROR"
                else: # Row Wise
                    if rows == 1 and len(matrix) > 0: # Single-choice dropdown
                        detected_indices = [i for i, x in enumerate(matrix[0]) if x == 1]
                        if len(detected_indices) == 1:
                            idx = detected_indices[0]
                            value = vals[idx] if idx < len(vals) else "ERR"
                        else:
                            value = "MULTIPLE"
                    else:
                        parts = []
                        for r in matrix:
                            if sum(r) == 1:
                                idx = r.index(1)
                                parts.append(vals[idx] if idx < len(vals) else "?")
                            elif sum(r) > 1:
                                parts.append("*")
                            else:
                                parts.append("_")
                        value = "".join(parts) if not any(p == "*" for p in parts) else "MULTIPLE"
                
                for r, row_vals in enumerate(matrix):
                    for c, is_filled in enumerate(row_vals):
                        if is_filled and (coord_index := r * cols + c) < len(all_coords):
                            bubble = all_coords[coord_index]
                            bubble_coords = (bubble[0] + rect.x(), bubble[1] + rect.y(), bubble[2] + rect.x(), bubble[3] + rect.y())
                            all_filled_bubbles_info.append({'coords': bubble_coords, 'correct': True})

                self.scan_results['identifiers'][roi_name] = value
                if "ERROR" in value or "MULTIPLE" in value or "ERR" in value:
                    self.scan_results['errors'][roi_name] = f"Scan error ({value})"
                    self.log(f"Identifier scan error for '{roi_name}': {value}")

            elif roi_data['type'] == 'Answer':
                start_q, options_map = roi_data.get('start_question', 1), roi_data.get('values', [chr(ord('A') + i) for i in range(cols)])
                for r_idx in range(rows):
                    question_num_str = str(start_q + r_idx)
                    detected_options = [options_map[c] for c, val in enumerate(matrix[r_idx]) if val == 1 and c < len(options_map)]
                    self.scan_results['answers'][question_num_str] = detected_options
                    for c_idx, is_filled in enumerate(matrix[r_idx]):
                        if is_filled and (coord_index := r_idx * cols + c_idx) < len(all_coords):
                            bubble = all_coords[coord_index]
                            bubble_coords = (bubble[0] + rect.x(), bubble[1] + rect.y(), bubble[2] + rect.x(), bubble[3] + rect.y())
                            all_filled_bubbles_info.append({'coords': bubble_coords, 'correct': True})
        
        for item in getattr(self, 'bubble_items', []): 
            if item.scene(): self.scene.removeItem(item)
        self.bubble_items = []
        alpha = params.get('transparency', 143)
        green_brush = QBrush(QColor(0, 255, 0, alpha))
        pen = QPen(Qt.PenStyle.NoPen)
        for bubble_info in all_filled_bubbles_info:
            x1, y1, x2, y2 = bubble_info['coords']
            self.bubble_items.append(self.scene.addRect(x1, y1, x2-x1, y2-y1, pen, green_brush))
		
    def _create_right_panel_widgets(self):
        """Builds the identifier and answer key widgets from the template."""
        self.log("Creating right panel UI from template...")
        # Clear any existing widgets
        for i in reversed(range(self.answers_layout.count())):
            if (widget := self.answers_layout.itemAt(i).widget()): widget.deleteLater()
        self.identifier_widgets.clear()
        self.question_widgets.clear()

        target_rois = self._get_target_rois()
        
        # --- Identifiers Group ---
        id_group = QGroupBox("Identifiers"); id_layout = QVBoxLayout(id_group)
        self.answers_layout.addWidget(id_group)
        
        id_rois = [r for r in target_rois if r.get('type') in ['Identifier', 'qrcode']]
        for roi_data in id_rois:
            name = roi_data.get('name')
            is_single_choice = (int(roi_data.get('rows', 0)) == 1 or int(roi_data.get('cols', 0)) == 1)
            
            if is_single_choice and roi_data.get('values'):
                widget = IdentifierDropdownWidget(name, roi_data.get('subtype', ''), roi_data.get('values', []), "", self)
                widget.combo_box.currentTextChanged.connect(self._update_identifier_from_dropdown)
            else:
                widget = IdentifierEditWidget(name, roi_data.get('subtype', ''), "", self)
                widget.value_edit.editingFinished.connect(self._update_identifier)
            
            id_layout.addWidget(widget)
            self.identifier_widgets[name] = widget
        
        # --- Answer Key Group ---
        ans_group = QGroupBox("Answer Key"); ans_layout = QVBoxLayout(ans_group)
        self.answers_layout.addWidget(ans_group)
        
        answer_rois = [r for r in target_rois if r.get('type') == 'Answer']
        if answer_rois:
            question_to_roi_map = {}
            total_questions = 0
            for r in answer_rois:
                try:
                    start_q = int(r.get('start_question', 1))
                    num_q = int(r.get('rows', 0))
                    for i in range(num_q):
                        q_num = start_q + i
                        question_to_roi_map[q_num] = r
                        if q_num > total_questions: total_questions = q_num
                except (ValueError, TypeError):
                    self.log(f"Warning: Invalid 'start_question' or 'rows' for ROI '{r.get('name')}'. Skipping.")
                    continue
            
            for q_num in range(1, total_questions + 1):
                roi_data = question_to_roi_map.get(q_num)
                opts = []
                if roi_data:
                    try:
                        num_opts = int(roi_data.get('cols', 0))
                        opts = roi_data.get('values', [chr(ord('A') + i) for i in range(num_opts)])
                    except (ValueError, TypeError):
                        opts = [] # Default to empty if cols is invalid
                
                widget = QuestionAnswerWidget(str(q_num), opts, [], self.multi_answer_checkbox.isChecked()) # Initially empty
                widget.option_group.buttonClicked.connect(self._update_answer)
                ans_layout.addWidget(widget)
                self.question_widgets[str(q_num)] = widget

        self.log("Right panel UI created.")

    def _update_widgets_from_scan(self):
        """Populates the already-created widgets with data from scan_results."""
        if not self.scan_results: self.log("No scan results to display."); return
        self.log("Updating widgets with scan results...")

        # Update identifiers
        for name, widget in self.identifier_widgets.items():
            value = self.scan_results.get('identifiers', {}).get(name, "")
            if isinstance(widget, IdentifierDropdownWidget):
                # Ensure value exists in the combobox to avoid errors
                if value in [widget.combo_box.itemText(i) for i in range(widget.combo_box.count())]:
                    widget.combo_box.setCurrentText(value)
                else:
                    widget.combo_box.setCurrentIndex(-1) # Clear selection if value not found
            elif isinstance(widget, IdentifierEditWidget):
                widget.value_edit.setText(str(value))
            
            # Highlight errors
            if name in self.scan_results.get('errors', {}):
                widget.setStyleSheet("background-color: #f8d7da;")
                widget.setToolTip(self.scan_results['errors'][name])
            else:
                widget.setStyleSheet("")
                widget.setToolTip("")

        # Update answers
        for q_num_str, widget in self.question_widgets.items():
            detected_options = self.scan_results.get('answers', {}).get(q_num_str, [])
            for button in widget.option_group.buttons():
                button.setChecked(button.text() in detected_options)

        self.log("Widgets updated.")
		
    def _update_identifier(self):
        if (widget := self.sender().parent()) and isinstance(widget, IdentifierEditWidget): 
            self.scan_results['identifiers'][widget.roi_name] = widget.value_edit.text(); widget.setStyleSheet("background-color: #d4edda;")
    
    def _update_identifier_from_dropdown(self, text):
        if (widget := self.sender().parent()) and isinstance(widget, IdentifierDropdownWidget):
            self.scan_results['identifiers'][widget.roi_name] = text; widget.setStyleSheet("background-color: #d4edda;")

    def _update_answer(self, button):
        parent = button.parent(); q_num = parent.q_num
        self.scan_results['answers'][q_num] = [btn.text() for btn in parent.option_group.buttons() if btn.isChecked()]

    def update_inspector_panel(self, scene_pos):
        if not self.roi_items or self.warped_image is None: return
        found = False
        for i, roi_data in enumerate(self.template_data['rois']):
            if i >= len(self.roi_items): continue
            rect_item = self.roi_items[i][0]
            if rect_item.rect().contains(scene_pos):
                try: 
                    rows, cols = (int(roi_data['rows']), int(roi_data['cols'])) if roi_data['type'] == 'Identifier' else (int(roi_data.get('questions', 0)), int(roi_data.get('options', 0)))
                    if rows == 0 or cols == 0:
                        continue
                    roi_rect = rect_item.rect(); local_pos = scene_pos - roi_rect.topLeft()
                    c, r = int(local_pos.x() / (roi_rect.width()/cols)), int(local_pos.y() / (roi_rect.height()/rows))
                    if 0 <= r < rows and 0 <= c < cols:
                        cell_w, cell_h = roi_rect.width()/cols, roi_rect.height()/rows
                        bubble_img = self.warped_image[int(roi_rect.y()+r*cell_h):int(roi_rect.y()+(r+1)*cell_h), int(roi_rect.x()+c*cell_w):int(roi_rect.x()+(c+1)*cell_w)]
                        if bubble_img.size > 0:
                            count, area, fill = self.engine.get_bubble_stats(bubble_img, self.get_current_params())
                            self.inspector_pixel_label.setText(f"Pixels: {count}"); self.inspector_contour_label.setText(f"Area: {area:.0f}"); self.inspector_fill_label.setText(f"Fill: {fill:.1f}%")
                            found = True
                        break
                except (KeyError, ValueError): 
                    continue
        if not found: 
            self.inspector_pixel_label.setText("Pixels: N/A")
            self.inspector_contour_label.setText("Area: N/A")
            self.inspector_fill_label.setText("Fill: N/A")

    def display_image(self, image):
        self.scene.clear(); self.roi_items.clear(); self.image_pixmap_item = None
        h, w, ch = image.shape
        qt_image = QImage(cv2.cvtColor(image, cv2.COLOR_BGR2RGB).data, w, h, ch*w, QImage.Format.Format_RGB888)
        self.image_pixmap_item = self.scene.addPixmap(QPixmap.fromImage(qt_image))
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def save_answer_key(self):
        if not self.template_data:
            QMessageBox.warning(self, "No Template", "A template must be loaded to save an answer key.")
            return

        # Explicitly gather the final values from the UI widgets at the moment of saving
        ids = {}
        for name, widget in self.identifier_widgets.items():
            scanned_value = ""
            if isinstance(widget, IdentifierDropdownWidget):
                scanned_value = widget.combo_box.currentText()
            elif isinstance(widget, IdentifierEditWidget):
                scanned_value = widget.value_edit.text()
            ids[name] = apply_identifier_reference(name, scanned_value)

        filename = self._generate_answer_key_filename(ids)

        data_to_save = {
            'template': self.template_data,
            'image_settings': self.get_current_params(),
            'identifiers': ids,
            'answers': self.scan_results.get('answers', {}) if self.scan_results else {}
        }

        answer_key_dir = get_answer_key_dir()
        save_path = os.path.join(answer_key_dir, f"{filename}.json")

        dialog_key = "Save Answer Key"
        
        # Determine the initial directory for the QFileDialog
        last_saved_path = load_last_path(dialog_key)
        if last_saved_path and os.path.isfile(last_saved_path):
            initial_dir = os.path.dirname(last_saved_path)
        else:
            initial_dir = get_answer_key_dir()

        # The suggested filename should ALWAYS be based on the current identifiers
        suggested_filename_with_ext = f"{filename}.json"
        
        # Combine the initial directory with the suggested filename
        # QFileDialog.getSaveFileName expects a full path for the initial filename suggestion
        full_initial_path_suggestion = os.path.join(initial_dir, suggested_filename_with_ext)

        path, _ = QFileDialog.getSaveFileName(self, dialog_key, full_initial_path_suggestion, "JSON Files (*.json)")
        if path:
            save_last_path(dialog_key, path)
            try:
                with open(path, 'w') as f:
                    json.dump(data_to_save, f, indent=4)
                QMessageBox.information(self, "Success", f"Answer key data saved to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save answer key.\nError: {e}")

    def _generate_answer_key_filename(self, ids):
        now = datetime.datetime.now()
        filename_parts = []
        
        output_settings = QSettings("OptiMark Pro", "OutputPatterns")
        defaults_settings = QSettings("OptiMark Pro", "Defaults")
        active_pattern_name = defaults_settings.value("last_output_pattern", "")
        naming_pattern = []

        if active_pattern_name:
            output_settings.beginGroup(active_pattern_name)
            naming_pattern = output_settings.value("answer_key_naming_pattern", [], type=list)
            output_settings.endGroup()

        if naming_pattern:
            self.log(f"Using '{active_pattern_name}' pattern to generate filename.")
            for component in naming_pattern:
                part = ""
                if component == "YYYY": part = now.strftime('%Y')
                elif component == "MM": part = now.strftime('%m')
                elif component == "DD": part = now.strftime('%d')
                elif component == "hh": part = now.strftime('%H')
                elif component == "mm": part = now.strftime('%M')
                elif component == "ss": part = now.strftime('%S')
                elif component == 'year': part = now.strftime('%Y')
                elif component == 'date': part = now.strftime('%d_%b_%y')
                elif component.startswith('"') and component.endswith('"'):
                    part = component.strip('"')
                else: # It's an ROI name
                    value = ids.get(component, '').strip()
                    part = value.replace(" ", "_") if value else 'None'
                filename_parts.append(part)
        else:
            self.log("No answer key naming pattern found. Using fallback naming scheme.")
            key_mapping = {'exam': 'Exam', 'class': 'Class', 'subject': 'Subject_Code', 'set': 'Set_Code'}
            filename_keys_in_order = ['exam', 'class', 'subject', 'set']
            for key in filename_keys_in_order:
                template_key = key_mapping.get(key)
                value = ids.get(template_key, '').strip()
                filename_parts.append(value.upper().replace("-", "_") if value else 'None')
            
            time_str = now.strftime('%H%M')
            date_str = now.strftime('%d%m%Y')
            filename_parts.extend([time_str, date_str])

        return "_".join(filter(None, filename_parts))

    def save_image_settings(self):
        """Saves the current image settings to QSettings."""
        params = self.get_current_params()
        settings = QSettings("OptiMark Pro", "ImageSettings")
        for key, value in params.items():
            settings.setValue(key, value)
        settings.setValue('allow_multiple_answers', self.multi_answer_checkbox.isChecked())
        self.log("Current image settings saved as the new default.")
        QMessageBox.information(self, "Settings Saved", "Current image settings have been saved as your new default.")

    def _load_default_settings(self, silent=False):
        self.log("Loading default image settings.")
        self._set_params_on_ui(self.DEFAULT_IMAGE_SETTINGS)
        self.rescan_with_new_parameters()
        if not silent:
            QMessageBox.information(self, "Defaults Loaded", "Default image settings have been loaded.")

    def _load_settings_from_qsettings(self):
        """Loads image settings from QSettings or uses defaults."""
        self.log("Loading image settings...")
        settings = QSettings("OptiMark Pro", "ImageSettings")
        
        # Create a dictionary of loaded settings, falling back to defaults
        loaded_params = {}
        for key, default_value in self.DEFAULT_IMAGE_SETTINGS.items():
            # QSettings needs type conversion for some values
            if isinstance(default_value, bool):
                value = settings.value(key, default_value, type=bool)
            elif isinstance(default_value, float):
                value = settings.value(key, default_value, type=float)
            elif isinstance(default_value, int):
                 value = settings.value(key, default_value, type=int)
            else:
                value = settings.value(key, default_value)
            loaded_params[key] = value

        self._set_params_on_ui(loaded_params)

    def _set_params_on_ui(self, params):
        self.contrast_slider.setValue(int(params.get('contrast', 1.3) * 10))
        self.brightness_slider.setValue(params.get('brightness', 60))
        self.blur_slider.setValue(params.get('blur', 1))
        self.rotation_slider.setValue(int(params.get('rotation', 0) * 10))
        self.adaptive_c_slider.setValue(params.get('adaptive_c', 1))
        self.threshold_slider.setValue(int(params.get('threshold', 0.08) * 100))
        self.contour_radio.setChecked(params.get('method') == 'contour')
        self.pixel_count_radio.setChecked(params.get('method') != 'contour')
        self.grayscale_checkbox.setChecked(params.get('grayscale', False))
        self.transparency_slider.setValue(params.get('transparency', 143))
        self.multi_answer_checkbox.setChecked(params.get('allow_multiple_answers', True))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    scanner = AnswerKeyScannerWindow()
    scanner.setWindowTitle("Answer Key Scanner")
    scanner.show()
    sys.exit(app.exec())
