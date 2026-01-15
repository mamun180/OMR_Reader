import sys
import os
import json
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QGroupBox, QGridLayout, QLabel, QSlider,
    QLineEdit, QRadioButton, QCheckBox, QHBoxLayout, QPushButton, QFileDialog,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QSplitter, QDialogButtonBox,
    QApplication, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtGui import QImage, QPixmap
import cv2
import numpy as np
from settings_manager import save_last_path, load_last_path

class ImageSettingsWidget(QWidget):
    """A widget for adjusting image processing parameters."""
    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        controls_group = QGroupBox("Image Settings")
        controls_layout = QVBoxLayout(controls_group)

        grid_layout = QGridLayout()

        grid_layout.addWidget(QLabel("Contrast:"), 0, 0)
        self.contrast_slider, self.contrast_edit = self._create_slider_combo(10, 30, 13, 10)
        grid_layout.addWidget(self.contrast_slider, 0, 1)
        grid_layout.addWidget(self.contrast_edit, 0, 2)

        grid_layout.addWidget(QLabel("Brightness:"), 1, 0)
        self.brightness_slider, self.brightness_edit = self._create_slider_combo(-100, 100, 35)
        grid_layout.addWidget(self.brightness_slider, 1, 1)
        grid_layout.addWidget(self.brightness_edit, 1, 2)

        grid_layout.addWidget(QLabel("Blur Kernel:"), 2, 0)
        self.blur_slider, self.blur_edit = self._create_slider_combo(0, 10, 2, 1, lambda v: f"{v*2+1}")
        grid_layout.addWidget(self.blur_slider, 2, 1)
        grid_layout.addWidget(self.blur_edit, 2, 2)
        
        grid_layout.addWidget(QLabel("Rotation (°):"), 3, 0)
        self.rotation_slider, self.rotation_edit = self._create_slider_combo(-50, 50, 0, 10)
        grid_layout.addWidget(self.rotation_slider, 3, 1)
        grid_layout.addWidget(self.rotation_edit, 3, 2)

        grid_layout.addWidget(QLabel("B&W Threshold:"), 4, 0)
        self.adaptive_c_slider, self.adaptive_c_edit = self._create_slider_combo(1, 15, 1)
        grid_layout.addWidget(self.adaptive_c_slider, 4, 1)
        grid_layout.addWidget(self.adaptive_c_edit, 4, 2)

        grid_layout.addWidget(QLabel("Fill Threshold:"), 5, 0)
        self.threshold_slider, self.threshold_edit = self._create_slider_combo(1, 100, 8)
        grid_layout.addWidget(self.threshold_slider, 5, 1)
        grid_layout.addWidget(self.threshold_edit, 5, 2)

        grid_layout.addWidget(QLabel("Fill Alpha:"), 6, 0)
        self.transparency_slider, self.transparency_edit = self._create_slider_combo(0, 255, 143)
        grid_layout.addWidget(self.transparency_slider, 6, 1)
        grid_layout.addWidget(self.transparency_edit, 6, 2)

        controls_layout.addLayout(grid_layout)

        # Method Radio Buttons
        method_group_box = QGroupBox("Method")
        method_layout = QHBoxLayout(method_group_box)
        self.method_group = QButtonGroup()
        self.pixel_count_radio = QRadioButton("Pixel Count")
        self.contour_radio = QRadioButton("Contour")
        self.contour_radio.setChecked(True)
        self.method_group.addButton(self.pixel_count_radio, 1)
        self.method_group.addButton(self.contour_radio, 2)
        method_layout.addWidget(self.pixel_count_radio)
        method_layout.addWidget(self.contour_radio)
        controls_layout.addWidget(method_group_box)

        self.method_group.buttonClicked.connect(self.settings_changed.emit)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(controls_group)

    def _create_slider_combo(self, min_val, max_val, default_val, edit_scale=1, text_format_fn=None):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)

        line_edit = QLineEdit()
        line_edit.setFixedWidth(40)

        def update_text(v):
            if text_format_fn:
                text = text_format_fn(v)
            elif edit_scale != 1:
                text = f"{v/edit_scale:.1f}"
            else:
                text = str(v)
            line_edit.setText(text)

        def update_slider():
            try:
                value = float(line_edit.text().replace('°',''))
                slider.setValue(int(value * edit_scale))
            except ValueError:
                slider.setValue(default_val)

        slider.valueChanged.connect(update_text)
        slider.valueChanged.connect(self.settings_changed.emit)
        line_edit.editingFinished.connect(update_slider)
        line_edit.editingFinished.connect(self.settings_changed.emit)
        
        slider.setValue(default_val)
        update_text(default_val)

        return slider, line_edit

    def get_params(self):
        """Returns a dictionary of the current settings."""
        return {
            'contrast': float(self.contrast_edit.text()),
            'brightness': int(self.brightness_edit.text()),
            'blur': (int(self.blur_edit.text().split('x')[0]) - 1) // 2,
            'rotation': float(self.rotation_edit.text()),
            'adaptive_c': int(self.adaptive_c_edit.text()),
            'threshold': float(self.threshold_edit.text()) / 100.0,
            'method': 'contour' if self.contour_radio.isChecked() else 'pixel_count',
            'transparency': self.transparency_slider.value(),
        }

    def set_params(self, params):
        """Sets the sliders and edits from a dictionary of parameters."""
        self.contrast_slider.setValue(int(params.get('contrast', 1.3) * 10))
        self.brightness_slider.setValue(params.get('brightness', 35))
        self.blur_slider.setValue(params.get('blur', 5))
        self.rotation_slider.setValue(int(params.get('rotation', 0.0) * 10))
        self.adaptive_c_slider.setValue(int(params.get('adaptive_c', 1)))
        self.threshold_slider.setValue(int(params.get('threshold', 0.08) * 100))
        self.contour_radio.setChecked(params.get('method', 'contour') == 'contour')
        self.pixel_count_radio.setChecked(params.get('method', 'contour') != 'contour')
        self.transparency_slider.setValue(params.get('transparency', 143))

def get_default_image_params():
    return {
        'contrast': 1.3, 'brightness': 35, 'blur': 5, 'rotation': 0.0,
        'adaptive_c': 1, 'threshold': 0.08, 'method': 'contour', 'transparency': 143
    }

def load_image_settings_from_qsettings():
    settings = QSettings("OptiMark Pro", "ImageSettings")
    params = get_default_image_params()
    for key, default_val in params.items():
        saved_val = settings.value(key)
        if saved_val is None:
            params[key] = default_val
        else:
            try:
                if isinstance(default_val, bool): params[key] = bool(saved_val)
                elif isinstance(default_val, int): params[key] = int(float(saved_val)) # Cast to float first for safety
                elif isinstance(default_val, float): params[key] = float(saved_val)
                else: params[key] = str(saved_val)
            except (ValueError, TypeError):
                params[key] = default_val
    return params

class ImageSettingsEditor(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Settings Editor")
        
        self.original_image = None
        self.processed_image = None

        # Main Layout
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # Left Panel (Controls)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        splitter.addWidget(left_panel)

        self.settings_widget = ImageSettingsWidget()
        self.settings_widget.settings_changed.connect(self.update_preview)
        left_layout.addWidget(self.settings_widget)

        self.cb_show_processed = QCheckBox("Show Processed Image")
        self.cb_show_processed.setChecked(True)
        self.cb_show_processed.stateChanged.connect(self.update_preview)
        left_layout.addWidget(self.cb_show_processed)

        # Right Panel (Image Preview)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        splitter.addWidget(right_panel)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        right_layout.addWidget(self.view)

        splitter.setSizes([300, 700])

        # Bottom Buttons
        bottom_layout = QHBoxLayout()
        main_layout.addLayout(bottom_layout)

        btn_load_image = QPushButton("Load Sample Image")
        btn_load_image.clicked.connect(self.load_image)
        bottom_layout.addWidget(btn_load_image)

        btn_reset = QPushButton("Reset to Defaults")
        btn_reset.clicked.connect(self.reset_to_defaults)
        bottom_layout.addWidget(btn_reset)
        
        bottom_layout.addStretch()

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        bottom_layout.addWidget(button_box)

        # Load existing settings
        self.load_settings()

    def get_default_params(self):
        return get_default_image_params()

    def reset_to_defaults(self):
        defaults = self.get_default_params()
        self.settings_widget.set_params(defaults)

    def load_settings(self):
        params = load_image_settings_from_qsettings()
        self.settings_widget.set_params(params)
        print("Loaded persistent image settings.")


    def save_settings(self):
        settings = QSettings("OptiMark Pro", "ImageSettings")
        params = self.settings_widget.get_params()
        for key, value in params.items():
            settings.setValue(key, value)
        print("Saved persistent image settings.")

    def load_image(self):
        dialog_key = "Load Sample Image"
        initial_path = load_last_path(dialog_key)
        path, _ = QFileDialog.getOpenFileName(self, dialog_key, initial_path)
        if path:
            save_last_path(dialog_key, path)
            self.original_image = cv2.imread(path)
            self.update_preview()

    def update_preview(self):
        if self.original_image is None:
            return

        params = self.settings_widget.get_params()
        self.processed_image = self._get_processed_image(self.original_image, params)

        if self.cb_show_processed.isChecked():
            self.display_image(self.processed_image)
        else:
            self.display_image(self.original_image)
    
    def _get_processed_image(self, image, params):
        img_copy = image.copy()
        # Contrast / Brightness
        img_copy = cv2.addWeighted(img_copy, params.get('contrast', 1.0), np.zeros(img_copy.shape, img_copy.dtype), 0, params.get('brightness', 0))
        # Blur
        if (b := params.get('blur', 1)) > 1:
             k = b if b % 2 == 1 else b + 1
             img_copy = cv2.GaussianBlur(img_copy, (k,k), 0)
        return img_copy

    def display_image(self, image_to_show):
        if len(image_to_show.shape) == 3:
            h, w, ch = image_to_show.shape
            qt_image = QImage(cv2.cvtColor(image_to_show, cv2.COLOR_BGR2RGB).data, w, h, ch * w, QImage.Format.Format_RGB888)
        else:
            h, w = image_to_show.shape
            qt_image = QImage(image_to_show.data, w, h, w, QImage.Format.Format_Grayscale8)

        self.pixmap_item.setPixmap(QPixmap.fromImage(qt_image))
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def get_default_settings(self):
        return {'contrast':1.3,'brightness':0,'blur':1,'adaptive_c':7}

    def accept(self):
        self.save_settings()
        super().accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    editor = ImageSettingsEditor()
    editor.exec()