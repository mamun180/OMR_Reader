from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QFileDialog,
                             QGraphicsView, QGraphicsScene, QGraphicsRectItem, QToolButton, QComboBox, QHBoxLayout, QInputDialog,
                             QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QMessageBox, QGraphicsPixmapItem, QGroupBox, QLabel, QGraphicsItem,
                             QSplitter, QListWidget, QRadioButton, QButtonGroup, QTextEdit, QCheckBox)
from PyQt6.QtCore import Qt, QRectF, QPointF, QEvent, QDateTime, QObject, pyqtSignal, QThread, QSettings
from PyQt6.QtGui import QPixmap, QPen, QColor, QImage, QPolygonF, QPainter, QBrush
import os
import json
import cv2
import numpy as np
import copy
from corner_detector import CornerDetector
from core_omr import OMREngine
from theme import apply_stylesheet_and_floatation
from directory_manager import get_template_dir
from settings_manager import save_last_path, load_last_path



class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

class CornerHandle(QGraphicsRectItem):
    def __init__(self, x, y, template_builder, size=10):
        super().__init__(-size/2, -size/2, size, size)
        self.setPos(x, y)
        self.setBrush(QColor("red"))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.template_builder = template_builder

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.template_builder.update_corner_polygon()
        return super().itemChange(change, value)

class EditableRectItem(QGraphicsRectItem):
    handleTopLeft = 1
    handleTopMiddle = 2
    handleTopRight = 3
    handleMiddleLeft = 4
    handleMiddleRight = 5
    handleBottomLeft = 6
    handleBottomMiddle = 7
    handleBottomRight = 8

    handleCursors = {
        handleTopLeft: Qt.CursorShape.SizeFDiagCursor,
        handleTopMiddle: Qt.CursorShape.SizeVerCursor,
        handleTopRight: Qt.CursorShape.SizeBDiagCursor,
        handleMiddleLeft: Qt.CursorShape.SizeHorCursor,
        handleMiddleRight: Qt.CursorShape.SizeHorCursor,
        handleBottomLeft: Qt.CursorShape.SizeBDiagCursor,
        handleBottomMiddle: Qt.CursorShape.SizeVerCursor,
        handleBottomRight: Qt.CursorShape.SizeFDiagCursor,
    }

    def __init__(self, rect, template_builder, parent=None):
        super().__init__(rect, parent)
        self.template_builder = template_builder
        self.setPen(QPen(QColor("green"), 2))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

        self.handleSize = 8.0
        self.handleSelected = None
        self.mousePressPos = None
        self.mousePressRect = None

        self.handles = {}
        self.updateHandlesPos()

    def updateHandlesPos(self):
        """Update the positions of the resize handles."""
        size = self.handleSize
        rect = self.rect()
        self.handles = {
            self.handleTopLeft: QRectF(rect.topLeft().x() - size / 2, rect.topLeft().y() - size / 2, size, size),
            self.handleTopMiddle: QRectF(rect.center().x() - size / 2, rect.top() - size / 2, size, size),
            self.handleTopRight: QRectF(rect.topRight().x() - size / 2, rect.topRight().y() - size / 2, size, size),
            self.handleMiddleLeft: QRectF(rect.left() - size / 2, rect.center().y() - size / 2, size, size),
            self.handleMiddleRight: QRectF(rect.right() - size / 2, rect.center().y() - size / 2, size, size),
            self.handleBottomLeft: QRectF(rect.bottomLeft().x() - size / 2, rect.bottomLeft().y() - size / 2, size, size),
            self.handleBottomMiddle: QRectF(rect.center().x() - size / 2, rect.bottom() - size / 2, size, size),
            self.handleBottomRight: QRectF(rect.bottomRight().x() - size / 2, rect.bottomRight().y() - size / 2, size, size),
        }

    def paint(self, painter, option, widget=None):
        """Paint the item and its handles."""
        super().paint(painter, option, widget)

        if self.isSelected():
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QBrush(QColor(255, 0, 0, 200))) # Red handles
            painter.setPen(QPen(QColor("black"), 1))
            for handle_rect in self.handles.values():
                painter.drawRect(handle_rect)

    def handleAt(self, point):
        """Returns the resize handle below the given point."""
        for k, v in self.handles.items():
            if v.contains(point):
                return k
        return None

    def hoverMoveEvent(self, event):
        """Change cursor when hovering over a handle."""
        if self.isSelected():
            handle = self.handleAt(event.pos())
            if handle:
                self.setCursor(self.handleCursors[handle])
            else:
                self.setCursor(Qt.CursorShape.OpenHandCursor if self.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable else Qt.CursorShape.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        """Detect if a handle is pressed or the item itself."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.handleSelected = self.handleAt(event.pos())
            if self.handleSelected:
                self.mousePressPos = event.pos()
                self.mousePressRect = self.rect()
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Resize the item if a handle is selected, otherwise move it."""
        if self.handleSelected:
            self.interactiveResize(event.pos())
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Clear selected handle."""
        if self.handleSelected:
            self.handleSelected = None
            self.setCursor(Qt.CursorShape.OpenHandCursor if self.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable else Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    def interactiveResize(self, mouse_pos):
        """Resize the item based on mouse movement and selected handle."""
        offset = mouse_pos - self.mousePressPos
        rect = self.mousePressRect
        self.prepareGeometryChange()

        new_rect = QRectF(rect)

        if self.handleSelected == self.handleTopLeft:
            new_rect.setTopLeft(rect.topLeft() + offset)
        elif self.handleSelected == self.handleTopMiddle:
            new_rect.setTop(rect.top() + offset.y())
        elif self.handleSelected == self.handleTopRight:
            new_rect.setTopRight(rect.topRight() + offset)
        elif self.handleSelected == self.handleMiddleLeft:
            new_rect.setLeft(rect.left() + offset.x())
        elif self.handleSelected == self.handleMiddleRight:
            new_rect.setRight(rect.right() + offset.x())
        elif self.handleSelected == self.handleBottomLeft:
            new_rect.setBottomLeft(rect.bottomLeft() + offset)
        elif self.handleSelected == self.handleBottomMiddle:
            new_rect.setBottom(rect.bottom() + offset.y())
        elif self.handleSelected == self.handleBottomRight:
            new_rect.setBottomRight(rect.bottomRight() + offset)
        
        # Ensure minimum size
        if new_rect.width() < self.handleSize * 2:
            if self.handleSelected in [self.handleTopLeft, self.handleMiddleLeft, self.handleBottomLeft]:
                new_rect.setLeft(new_rect.right() - self.handleSize * 2)
            else:
                new_rect.setWidth(self.handleSize * 2)
        if new_rect.height() < self.handleSize * 2:
            if self.handleSelected in [self.handleTopLeft, self.handleTopMiddle, self.handleTopRight]:
                new_rect.setTop(new_rect.bottom() - self.handleSize * 2)
            else:
                new_rect.setHeight(self.handleSize * 2)

        # Move the item's position by the change in the rect's top-left
        self.moveBy(new_rect.x() - rect.x(), new_rect.y() - rect.y())
        # Set the item's rect to have a top-left of (0,0)
        self.setRect(0, 0, new_rect.width(), new_rect.height())

        self.updateHandlesPos()
        self.template_builder.on_roi_geometry_changed(self)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene():
            # This is where you can react to the item's position changing.
            # For example, you could update some data that depends on the item's position.
            pass
        return super(EditableRectItem, self).itemChange(change, value)

class DrawableGraphicsView(QGraphicsView):
    def __init__(self, scene, template_builder, parent=None):
        super().__init__(scene, parent)
        self.template_builder = template_builder
        self.start_point = None
        self.current_rect_item = None
        self.drawing_enabled = False

    def set_drawing_enabled(self, enabled):
        self.drawing_enabled = enabled

    def keyPressEvent(self, event):
        if self.scene() is None:
            super().keyPressEvent(event)
            return
            
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Plus or event.key() == Qt.Key.Key_Equal:
                self.zoom_in()
                return
            elif event.key() == Qt.Key.Key_Minus:
                self.zoom_out()
                return
            elif event.key() == Qt.Key.Key_C: # Copy
                if self.template_builder.selected_roi_index is not None:
                    self.template_builder.clipboard = copy.deepcopy(self.template_builder.rois[self.template_builder.selected_roi_index])
                    self.template_builder.log("ROI copied to clipboard.")
                return
            elif event.key() == Qt.Key.Key_X: # Cut
                if self.template_builder.selected_roi_index is not None:
                    self.template_builder.clipboard = copy.deepcopy(self.template_builder.rois[self.template_builder.selected_roi_index])
                    self.template_builder.delete_selected_roi()
                    self.template_builder.log("ROI cut to clipboard.")
                return
            elif event.key() == Qt.Key.Key_V: # Paste
                if self.template_builder.clipboard is not None:
                    new_roi_data = copy.deepcopy(self.template_builder.clipboard)
                    new_roi_data['name'] = f"{new_roi_data['name']}_copy"
                    # Paste near the original, not at a fixed offset from (0,0)
                    new_roi_data['x'] = self.mapToScene(self.viewport().rect().center()).x()
                    new_roi_data['y'] = self.mapToScene(self.viewport().rect().center()).y()
                    self.template_builder.add_roi(new_roi_data)
                    self.template_builder.log("ROI pasted from clipboard.")
                return
            elif event.key() == Qt.Key.Key_S: # Save
                if event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier): # Shift+Ctrl+S (Save As)
                    self.template_builder.save_template_as()
                elif event.modifiers() == Qt.KeyboardModifier.ControlModifier: # Ctrl+S (Save)
                    self.template_builder.save_template()
                return
            elif event.key() == Qt.Key.Key_D: # Ctrl+D (Draw tool)
                self.template_builder.draw_mode_radio.setChecked(True)
                self.template_builder.set_interaction_mode(1) # Manually trigger the mode change
                return
            elif event.key() == Qt.Key.Key_H: # Ctrl+H (Hand tool)
                self.template_builder.select_mode_radio.setChecked(True)
                self.template_builder.set_interaction_mode(0) # Manually trigger the mode change
                return
            elif event.key() == Qt.Key.Key_L: # Ctrl+L (Load Template)
                self.template_builder.load_template_action()
                return

        selected_items = self.scene().selectedItems()
        if len(selected_items) == 1 and isinstance(selected_items[0], EditableRectItem):
            item = selected_items[0]
            dx, dy = 0, 0
            if event.key() == Qt.Key.Key_Left:
                dx = -1
            elif event.key() == Qt.Key.Key_Right:
                dx = 1
            elif event.key() == Qt.Key.Key_Up:
                dy = -1
            elif event.key() == Qt.Key.Key_Down:
                dy = 1
            elif event.key() == Qt.Key.Key_Delete:
                self.template_builder.delete_selected_roi()
                return

            if dx != 0 or dy != 0:
                item.moveBy(dx, dy)
                return

        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if self.template_builder.is_defining_box:
            pos = self.mapToScene(event.pos())
            self.template_builder.add_box_point(pos)
            return

        if self.drawing_enabled and event.button() == Qt.MouseButton.LeftButton:
            self.start_point = self.mapToScene(event.pos())
            self.current_rect_item = QGraphicsRectItem(QRectF(self.start_point, self.start_point))
            self.current_rect_item.setPen(QPen(QColor("red"), 2, Qt.PenStyle.DashLine))
            self.scene().addItem(self.current_rect_item)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drawing_enabled and self.current_rect_item and self.start_point:
            end_point = self.mapToScene(event.pos())
            if end_point is not None:
                rect = QRectF(self.start_point, end_point).normalized()
                self.current_rect_item.setRect(rect)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drawing_enabled and event.button() == Qt.MouseButton.LeftButton and self.current_rect_item:
            rect = self.current_rect_item.rect().normalized()

            if self.template_builder.is_setting_corner:
                self.template_builder.learn_corner_from_roi(rect)
                self.scene().removeItem(self.current_rect_item)
                self.current_rect_item = None
                self.start_point = None
                super().mouseReleaseEvent(event)
                return

            # Create a new ROI with default data
            roi_data = {
                'type': "Identifier", # Default to Identifier
                'name': f"ROI {len(self.template_builder.rois) + 1}",
                'x': rect.x(),
                'y': rect.y(),
                'width': rect.width(),
                'height': rect.height(),
                # Default identifier properties
                'rows': '1', 
                'cols': '1', 
                'order': 'Row Wise', 
                'values': ['a', 'b', 'c', 'd'], 
                'subtype': 'Answer Script Identifier'
            }

            self.template_builder.add_roi(roi_data)

            # Remove the temporary rectangle
            self.scene().removeItem(self.current_rect_item)
            self.current_rect_item = None
            self.start_point = None
            
        super().mouseReleaseEvent(event)


    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            super().wheelEvent(event)

    def zoom_in(self):
        self.scale(1.2, 1.2)

    def zoom_out(self):
        self.scale(0.8, 0.8)

class TemplateBuilder(QWidget):
    def __init__(self):
        super().__init__()
        self.engine = OMREngine()
        self.detector = CornerDetector()
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)

        # Top toolbar
        tools_widget = QWidget()
        tools_layout = QHBoxLayout(tools_widget)
        tools_layout.setContentsMargins(0,0,0,0)
        tools_layout.setSpacing(1)
        
        self.btn_load = QPushButton("Load Image")
        self.btn_load.setMinimumHeight(50)
        self.btn_load.clicked.connect(self.load_image)

        self.template_label = QLabel("Template:")
        self.template_combobox = QComboBox()
        self.template_combobox.setMinimumWidth(200)
        self.btn_refresh_templates = QPushButton("Refresh")
        self.btn_refresh_templates.setMinimumHeight(50)
        
        self.btn_save = QPushButton("Save Template")
        self.btn_save.setMinimumHeight(50)
        self.btn_save.setToolTip("Ctrl+S")
        self.btn_save.clicked.connect(self.save_template)
        
        tools_layout.addWidget(self.btn_load)
        tools_layout.addWidget(self.template_label)
        tools_layout.addWidget(self.template_combobox)
        tools_layout.addWidget(self.btn_refresh_templates)
        tools_layout.addWidget(self.btn_save)
        tools_layout.addStretch()
        main_layout.addWidget(tools_widget)

        # Main splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side panel
        left_panel_group = QGroupBox("ROIs")
        left_panel_layout = QVBoxLayout()
        self.roi_list_widget = QListWidget()
        self.roi_list_widget.setFixedHeight(220)
        self.roi_list_widget.currentItemChanged.connect(self.select_roi_from_list)
        left_panel_layout.addWidget(self.roi_list_widget)
        self.btn_delete_roi = QPushButton("Delete ROI")
        self.btn_delete_roi.setMinimumHeight(50)
        self.btn_delete_roi.setToolTip("Del")
        self.btn_delete_roi.clicked.connect(self.delete_selected_roi)
        left_panel_layout.addWidget(self.btn_delete_roi)

        # ROI editor
        self.roi_editor_group = QGroupBox("ROI Properties")
        self.roi_editor_group.setFixedHeight(150)
        self.roi_editor_layout = QFormLayout()
        self.roi_name_edit = QLineEdit()
        self.roi_x_edit = QLineEdit()
        self.roi_y_edit = QLineEdit()
        self.roi_w_edit = QLineEdit()
        self.roi_h_edit = QLineEdit()
        self.roi_editor_layout.addRow("Name:", self.roi_name_edit)
        self.roi_type_combo = QComboBox()
        self.roi_type_combo.addItems(["Identifier", "Answer", "Qrcode", "Annotation"])
        self.roi_editor_layout.addRow("Type:", self.roi_type_combo)
        self.roi_editor_layout.addRow("X:", self.roi_x_edit)
        self.roi_editor_layout.addRow("Y:", self.roi_y_edit)
        self.roi_editor_layout.addRow("Width:", self.roi_w_edit)
        self.roi_editor_layout.addRow("Height:", self.roi_h_edit)
        self.roi_editor_group.setLayout(self.roi_editor_layout)
        left_panel_layout.addWidget(self.roi_editor_group)

        # -- Answer ROI Editor --
        self.answer_editor_group = QGroupBox("Answer Parameters")
        answer_layout = QFormLayout()
        self.ans_rows_edit = QLineEdit()
        self.ans_cols_edit = QLineEdit()
        self.roi_start_question_edit = QLineEdit()
        self.roi_end_question_edit = QLineEdit()
        self.roi_correct_mark_edit = QLineEdit()
        self.roi_wrong_mark_edit = QLineEdit()
        self.ans_values_edit = QLineEdit()
        answer_layout.addRow("Number of Questions:", self.ans_rows_edit)
        answer_layout.addRow("Number of Options:", self.ans_cols_edit)
        answer_layout.addRow("Values (',' separated):", self.ans_values_edit)
        answer_layout.addRow("Starting Question #:", self.roi_start_question_edit)
        answer_layout.addRow("Ending Question #:", self.roi_end_question_edit)
        answer_layout.addRow("Correct Mark:", self.roi_correct_mark_edit)
        answer_layout.addRow("Wrong Mark:", self.roi_wrong_mark_edit)
        self.answer_editor_group.setLayout(answer_layout)
        left_panel_layout.addWidget(self.answer_editor_group)

        # -- Identifier ROI Editor --
        self.identifier_editor_group = QGroupBox("Identifier Parameters")
        identifier_layout = QFormLayout()
        self.ident_rows_edit = QLineEdit()
        self.ident_cols_edit = QLineEdit()
        self.roi_order_combo = QComboBox()
        self.roi_order_combo.addItems(["Row Wise", "Column Wise"])
        self.roi_values_edit = QLineEdit()
        self.roi_identifier_subtype_combo = QComboBox()
        self.roi_identifier_subtype_combo.addItems(["Answer Script Identifier", "Student Identifier"])
        identifier_layout.addRow("Rows:", self.ident_rows_edit)
        identifier_layout.addRow("Columns:", self.ident_cols_edit)
        identifier_layout.addRow("Order:", self.roi_order_combo)
        identifier_layout.addRow("Values (comma-sep):", self.roi_values_edit)
        identifier_layout.addRow("Identifier Type:", self.roi_identifier_subtype_combo)
        self.identifier_editor_group.setLayout(identifier_layout)
        left_panel_layout.addWidget(self.identifier_editor_group)
        
        # -- QRCode ROI Editor --
        self.qrcode_editor_group = QGroupBox("QRCode Parameters")
        qrcode_layout = QFormLayout()
        self.roi_role_edit = QLineEdit()
        qrcode_layout.addRow("Role:", self.roi_role_edit)
        self.qrcode_editor_group.setLayout(qrcode_layout)
        left_panel_layout.addWidget(self.qrcode_editor_group)

        # -- Annotation ROI Editor --
        self.annotation_editor_group = QGroupBox("Annotation Parameters")
        annotation_layout = QFormLayout()
        self.annotation_editor_group.setLayout(annotation_layout)
        left_panel_layout.addWidget(self.annotation_editor_group)

        self.roi_editor_group.setVisible(False)
        self.answer_editor_group.setVisible(False)
        self.identifier_editor_group.setVisible(False)
        self.qrcode_editor_group.setVisible(False)
        self.annotation_editor_group.setVisible(False)
        
        left_panel_layout.addStretch() # Add stretch to push content to top
        left_panel_group.setLayout(left_panel_layout)
        main_splitter.addWidget(left_panel_group)

        # Center canvas
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0,0,0,0)
        self.scene = QGraphicsScene()
        self.view = DrawableGraphicsView(self.scene, self, self)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        canvas_layout.addWidget(self.view)
        main_splitter.addWidget(canvas_container)

        # Right side panel
        right_panel_widget = QWidget()
        right_panel_layout = QVBoxLayout(right_panel_widget)
        right_panel_layout.setContentsMargins(0,0,0,0)
        right_panel_layout.setSpacing(2)

        # Log Panel
        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setFixedHeight(120)
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()
        log_layout.addWidget(self.log_panel)
        log_group.setLayout(log_layout)
        log_group.setContentsMargins(0,5,0,0)
        right_panel_layout.addWidget(log_group)

        # Anchor Setup Group
        anchor_setup_group = QGroupBox("Template Setup")
        anchor_setup_layout = QVBoxLayout()
        self.btn_learn_corner = QPushButton("1. Learn Corner Shape")
        self.btn_learn_corner.setMinimumHeight(50)
        self.btn_learn_corner.clicked.connect(self.on_set_corner_marker)
        self.btn_define_box = QPushButton("2. Define Content Box")
        self.btn_define_box.setMinimumHeight(50)
        self.btn_define_box.clicked.connect(self.on_define_box_clicked)
        anchor_setup_layout.addWidget(self.btn_learn_corner)
        anchor_setup_layout.addWidget(self.btn_define_box)
        anchor_setup_group.setLayout(anchor_setup_layout)
        anchor_setup_group.setContentsMargins(0,5,0,0)
        right_panel_layout.addWidget(anchor_setup_group)

        # Actions Group
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setMinimumHeight(50)
        self.btn_reset.clicked.connect(self.reset_template)
        self.btn_test_template = QPushButton("Test Template")
        self.btn_test_template.setMinimumHeight(50)
        self.btn_test_template.clicked.connect(self.test_template)
        actions_layout.addWidget(self.btn_reset)
        actions_layout.addWidget(self.btn_test_template)
        actions_group.setLayout(actions_layout)
        actions_group.setContentsMargins(0,5,0,0)
        right_panel_layout.addWidget(actions_group)
        
        # Interaction Mode Group
        interaction_mode_group = QGroupBox("Interaction Mode")
        interaction_mode_layout = QHBoxLayout()
        self.select_mode_radio = QRadioButton("Hand")
        self.select_mode_radio.setToolTip("Ctrl+H")
        self.draw_mode_radio = QRadioButton("Draw")
        self.draw_mode_radio.setToolTip("Ctrl+D")
        interaction_mode_layout.addWidget(self.select_mode_radio)
        interaction_mode_layout.addWidget(self.draw_mode_radio)
        interaction_mode_group.setLayout(interaction_mode_layout)
        interaction_mode_group.setContentsMargins(0,5,0,0)
        right_panel_layout.addWidget(interaction_mode_group)

        # Keyboard Shortcuts Group
        shortcuts_group = QGroupBox("Keyboard Shortcuts")
        shortcuts_layout = QVBoxLayout()
        self.shortcuts_display = QTextEdit()
        self.shortcuts_display.setReadOnly(True)
        shortcuts_text = """
<b>Zoom:</b><br>
  Ctrl + Mouse Wheel: In/Out<br>
  Ctrl + +: Zoom In<br>
  Ctrl + -: Zoom Out<br>
<b>ROI Manipulation:</b><br>
  Del: Delete selected ROI<br>
  Ctrl + C: Copy selected ROI<br>
  Ctrl + X: Cut selected ROI<br>
  Ctrl + V: Paste ROI<br>
<b>Tools:</b><br>
  Ctrl + D: Draw Tool<br>
  Ctrl + H: Hand Tool<br>
<b>File Operations:</b><br>
  Ctrl + S: Save Template<br>
  Shift + Ctrl + S: Save Template As<br>
  Ctrl + L: Load Template<br>
"""
        self.shortcuts_display.setHtml(shortcuts_text)
        shortcuts_layout.addWidget(self.shortcuts_display)
        shortcuts_group.setLayout(shortcuts_layout)
        right_panel_layout.addWidget(shortcuts_group)
        right_panel_layout.contentsMargins().setTop(5)
        main_splitter.addWidget(right_panel_widget)
        main_splitter.setSizes([170, 660, 170])
        
        main_layout.addWidget(main_splitter, 1)

        # Connect signals
        for editor in [self.roi_name_edit, self.roi_x_edit, self.roi_y_edit, self.roi_w_edit, self.roi_h_edit,
                       self.ans_cols_edit, self.ans_values_edit, self.ident_rows_edit, self.ident_cols_edit,
                       self.roi_correct_mark_edit, self.roi_wrong_mark_edit,
                       self.roi_values_edit, self.roi_role_edit]:
            editor.editingFinished.connect(self.update_roi_from_fields)
        for editor in [self.ans_rows_edit, self.roi_start_question_edit, self.roi_end_question_edit]:
            editor.editingFinished.connect(self._update_answer_roi_numbers)
        self.roi_order_combo.currentIndexChanged.connect(self.update_roi_from_fields)
        self.roi_identifier_subtype_combo.currentIndexChanged.connect(self.update_roi_from_fields)
        self.roi_type_combo.currentTextChanged.connect(self.on_roi_type_changed)
        
        # Floating Zoom Buttons
        self.zoom_in_button = QToolButton(self.view)
        self.zoom_in_button.setText('+')
        self.zoom_in_button.clicked.connect(self.view.zoom_in)
        
        self.zoom_out_button = QToolButton(self.view)
        self.zoom_out_button.setText('-')
        self.zoom_out_button.clicked.connect(self.view.zoom_out)

        # Instance variables
        self.current_image = None
        self.rois = []
        self.roi_items = []
        self.corner_properties = {}
        self.corner_handles = []
        self.grid_visible = True
        self.is_setting_corner = False
        self.is_defining_box = False
        self.selected_roi_index = None
        self.learning_rects = []
        self.clipboard = None
        self.pixmap_item = None
        self.box_points = []
        self.box_rect_item = None
        self.corner_box_lines = []
        self.detected_corners = None
        self.interaction_mode_group = QButtonGroup(self)
        self.interaction_mode_group.addButton(self.select_mode_radio, 0)
        self.interaction_mode_group.addButton(self.draw_mode_radio, 1)
        self.select_mode_radio.setChecked(True)
        self.interaction_mode_group.idClicked.connect(self.set_interaction_mode)
        self.set_interaction_mode(0)

        # Warping variables
        self.warped_image = None
        self.warp_matrix = None
        self.original_box_points = None

        self.btn_refresh_templates.clicked.connect(self.populate_template_combobox)
        self.template_combobox.currentIndexChanged.connect(self.on_template_selected)
        
        self.template_combobox.setEnabled(False)
        self.btn_refresh_templates.setEnabled(False)

        self.apply_theme()

        self.populate_template_combobox()

    def populate_template_combobox(self):
        self.template_combobox.clear()
        self.template_combobox.addItem("Select a template...")
        template_dir = get_template_dir()
        if template_dir and os.path.isdir(template_dir):
            try:
                templates = [f for f in os.listdir(template_dir) if f.endswith('.json')]
                self.template_combobox.addItems(templates)
            except OSError as e:
                self.log(f"Error reading template directory: {e}")
        self.template_combobox.addItem("Browse for template...")

    def browse_for_template(self):
        dialog_key = "Load Template"
        initial_path = load_last_path(dialog_key) or get_template_dir()
        path, _ = QFileDialog.getOpenFileName(self, dialog_key, initial_path, "JSON Files (*.json)")
        if path:
            save_last_path(dialog_key, path)
            self.load_template_action(path=path)

    def on_template_selected(self, index):
        if index == -1 or self.template_combobox.itemText(index) in ["", "Select a template..."]:
            return
        
        selection = self.template_combobox.itemText(index)
        
        if selection == "Browse for template...":
            self.browse_for_template()
            self.template_combobox.setCurrentIndex(0) # Reset after browsing
        else:
            template_path = os.path.join(get_template_dir(), selection)
            if os.path.exists(template_path):
                self.load_template_action(path=template_path)
            else:
                QMessageBox.warning(self, "File Not Found", f"Template file not found at: {template_path}")
                self.populate_template_combobox() # Refresh list if file is missing

    def load_student_data(self):
        pass

    def apply_theme(self):
        apply_stylesheet_and_floatation(self)

    def log(self, message):
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.log_panel.append(f"[{timestamp}] {message}")

    def on_set_corner_marker(self):
        self.log("Starting corner learning. Draw a box around one of the corner markers.")
        self.is_setting_corner = True
        self.view.set_drawing_enabled(True)
        QMessageBox.information(self, "Learn Corner Shape", "Draw a tight box around one of the corner markers.")

    def learn_corner_from_roi(self, rect):
        self.is_setting_corner = False
        self.set_interaction_mode(self.interaction_mode_group.checkedId())
        
        if self.current_image is None or self.pixmap_item is None:
            self.log("Learn corner failed: No image loaded.")
            return

        image_rect = self.pixmap_item.mapFromScene(rect).boundingRect()
        x, y, w, h = int(image_rect.x()), int(image_rect.y()), int(image_rect.width()), int(image_rect.height())
        roi_img = self.current_image[y:y+h, x:x+w]

        if roi_img.size == 0:
            self.log("Error: Drawn corner ROI is empty or out of bounds.")
            return

        gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                       cv2.THRESH_BINARY_INV, 11, 2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            QMessageBox.warning(self, "Error", "Could not find a corner marker in the selected area.")
            return
            
        c = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(c)
        
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.04 * peri, True)
        num_vertices = len(approx)
        (x_b, y_b, w_b, h_b) = cv2.boundingRect(approx)
        aspect_ratio = w_b / float(h_b) if h_b != 0 else 0

        self.learning_rects.append(self.scene.addRect(rect, QPen(QColor("orange")), QBrush(QColor(255, 165, 0, 50))))

        self.corner_properties = {
            'area_min': area * 0.7, 'area_max': area * 1.3,
            'aspect_ratio_min': aspect_ratio * 0.85, 'aspect_ratio_max': aspect_ratio * 1.15,
            'num_vertices': num_vertices
        }
        
        self.log(f"Corner properties learned. Detecting corners...")
        self.run_corner_detection()

    def run_corner_detection(self):
        self.log("Running corner detection...")
        corners = self.detector.find_corners(self.current_image, self.corner_properties)
        
        for item in self.corner_handles + self.corner_box_lines:
            if item.scene():
                self.scene.removeItem(item)
        self.corner_handles.clear()
        self.corner_box_lines.clear()
        
        if corners is not None and len(corners) == 4:
            self.log(f"Found 4 corners automatically.")
            self.detected_corners = self.detector._order_points(corners)
            
            # Draw the box for visual feedback
            poly = QPolygonF([QPointF(p[0], p[1]) for p in self.detected_corners])
            pen = QPen(QColor("yellow"), 2)
            for i in range(4):
                p1 = poly.at(i)
                p2 = poly.at((i + 1) % 4)
                line = self.scene.addLine(p1.x(), p1.y(), p2.x(), p2.y(), pen)
                self.corner_box_lines.append(line)

            self.btn_define_box.setEnabled(True)
            self.log("Corner detection successful. Please define the content box.")
        else:
            self.log("Automatic corner detection failed. Please try learning the corner shape again.")
            self.btn_define_box.setEnabled(False)
            self.detected_corners = None

    def on_define_box_clicked(self):
        self.is_defining_box = True
        self.box_points.clear()
        if self.box_rect_item and self.box_rect_item.scene():
            self.scene.removeItem(self.box_rect_item)
        self.box_rect_item = None
        self.log("Click 4 points to define the content box: top-left, top-right, bottom-right, bottom-left.")
        QMessageBox.information(self, "Define Box", "Click the 4 points of the desired rectangular content area in order:\n1. Top-Left\n2. Top-Right\n3. Bottom-Right\n4. Bottom-Left")

    def add_box_point(self, point):
        if not self.is_defining_box or len(self.box_points) >= 4:
            return
        
        self.box_points.append(point)
        # Add a small visual marker for the clicked point
        self.scene.addEllipse(point.x()-3, point.y()-3, 6, 6, QPen(QColor("blue")), QBrush(QColor("blue")))
        self.log(f"Box point {len(self.box_points)}/4 added.")

        if len(self.box_points) == 4:
            self.is_defining_box = False
            self.log("4 box points defined. Warping content area...")
            
            # The points are QPointF, convert them for OpenCV
            self.original_box_points = np.array([(p.x(), p.y()) for p in self.box_points], dtype="float32")
            
            self.warp_content_box()

    def warp_content_box(self):
        """Warps the area defined by self.original_box_points and updates the scene."""
        if self.original_box_points is None or len(self.original_box_points) != 4:
            self.log("Cannot warp: Box points are not fully defined.")
            return

        self.warped_image, self.warp_matrix = self.engine.four_point_transform(self.current_image, self.original_box_points)

        if self.warped_image is not None:
            # Clear all graphical items from the scene, but keep data in memory
            items_to_remove = [item for item in self.scene.items() if not isinstance(item, QGraphicsPixmapItem)]
            for item in items_to_remove:
                self.scene.removeItem(item)

            # Clear graphical data models
            self.roi_items.clear()
            self.rois.clear()
            self.roi_list_widget.clear()
            
            # Now display the new warped image.
            self.display_image(self.warped_image)
            self.log("Content box warped. You can now draw ROIs on the straightened image.")
        else:
            self.log("Error during image warping.")

    def set_interaction_mode(self, mode_id):
        if mode_id == 0: # Select
            self.view.set_drawing_enabled(False)
            self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        else: # Draw
            self.view.set_drawing_enabled(True)
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)

    def select_roi_from_list(self, current, previous):
        if current is None:
            return
        row = self.roi_list_widget.row(current)
        if 0 <= row < len(self.roi_items):
            self.scene.clearSelection()
            rect_item, _, _ = self.roi_items[row]
            rect_item.setSelected(True)

    def on_roi_type_changed(self, new_type):
        if self.selected_roi_index is None:
            return

        roi_data = self.rois[self.selected_roi_index]
        if roi_data['type'] != new_type:
            roi_data['type'] = new_type

            if new_type == 'Answer' and 'start_question' not in roi_data:
                last_q_num = 0
                for r in self.rois:
                    if r.get('type') == 'Answer':
                        last_q_num = max(last_q_num, r.get('end_question', 0))
                
                start_q = last_q_num + 1
                num_q = 1
                end_q = start_q + num_q - 1
                roi_data.update({
                    'rows': str(num_q), 
                    'cols': '4', 
                    'values': ['A', 'B', 'C', 'D'],
                    'start_question': start_q, 
                    'end_question': end_q,
                    'correct_mark': '1', 
                    'wrong_mark': '0'
                })

            self.populate_roi_editor()

    def update_roi_from_fields(self):
        if self.selected_roi_index is None:
            return

        roi_data = self.rois[self.selected_roi_index]
        old_name = roi_data['name']

        try:
            # Update data model from fields
            roi_data['name'] = self.roi_name_edit.text()
            roi_data['x'] = float(self.roi_x_edit.text())
            roi_data['y'] = float(self.roi_y_edit.text())
            roi_data['width'] = float(self.roi_w_edit.text())
            roi_data['height'] = float(self.roi_h_edit.text())
            
            # ... (rest of the data update logic for different types)
            if roi_data['type'] == "Answer":
                roi_data['rows'] = self.ans_rows_edit.text()
                roi_data['cols'] = self.ans_cols_edit.text()
                roi_data['values'] = [v.strip() for v in self.ans_values_edit.text().split(',')]
                roi_data['start_question'] = int(self.roi_start_question_edit.text())
                roi_data['end_question'] = int(self.roi_end_question_edit.text())
                roi_data['correct_mark'] = self.roi_correct_mark_edit.text()
                roi_data['wrong_mark'] = self.roi_wrong_mark_edit.text()
            elif roi_data['type'] == "Identifier":
                roi_data['rows'] = self.ident_rows_edit.text()
                roi_data['cols'] = self.ident_cols_edit.text()
                roi_data['order'] = self.roi_order_combo.currentText()
                roi_data['values'] = [v.strip() for v in self.roi_values_edit.text().split(',')]
                roi_data['subtype'] = self.roi_identifier_subtype_combo.currentText()
            elif roi_data['type'] == "Qrcode":
                roi_data['role'] = self.roi_role_edit.text()


        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numbers for ROI properties.")
            self.populate_roi_editor() # Revert fields to original data
            return

        # Update graphical item from data model
        rect_item, text_item, _ = self.roi_items[self.selected_roi_index]
        
        # Set position and rect according to the new convention
        rect_item.setPos(roi_data['x'], roi_data['y'])
        rect_item.setRect(0, 0, roi_data['width'], roi_data['height'])

        # Update text item position
        text_item.setPlainText(roi_data['name'])
        text_item.setPos(rect_item.pos() - QPointF(0, 10))

        # Update list widget if name changed
        if old_name != roi_data['name']:
            self.roi_list_widget.item(self.selected_roi_index).setText(roi_data['name'])

        self.draw_roi_grid(roi_data, self.selected_roi_index)

    def _update_answer_roi_numbers(self):
        if self.selected_roi_index is None: return
        roi_data = self.rois[self.selected_roi_index]
        if roi_data.get('type') != 'Answer': return
        
        sender = self.sender()
        
        try:
            start_q = int(self.roi_start_question_edit.text())
            end_q = int(self.roi_end_question_edit.text())
            num_q = int(self.ans_rows_edit.text())

            if sender == self.roi_start_question_edit or sender == self.ans_rows_edit:
                end_q = start_q + num_q - 1
                self.roi_end_question_edit.setText(str(end_q))
            elif sender == self.roi_end_question_edit:
                num_q = end_q - start_q + 1
                if num_q < 1:
                    num_q = 1
                    end_q = start_q
                    self.roi_end_question_edit.setText(str(end_q))
                self.ans_rows_edit.setText(str(num_q))

        except ValueError:
            return
        
        self.update_roi_from_fields()

    def on_roi_geometry_changed(self, changed_item):
        if not isinstance(changed_item, EditableRectItem):
            return

        item_index = changed_item.data(0)
        if item_index is None or not (0 <= item_index < len(self.rois)):
            return
        
        rect = changed_item.rect()
        pos = changed_item.pos()

        roi_data = self.rois[item_index]
        roi_data['x'] = pos.x()
        roi_data['y'] = pos.y()
        roi_data['width'] = rect.width()
        roi_data['height'] = rect.height()

        # If the item that changed is the one selected, update the editor fields
        if item_index == self.selected_roi_index:
            self.populate_roi_editor(preserve_focus=True)

    def on_selection_changed(self):
        try:
            selected_items = self.scene.selectedItems()
            if len(selected_items) == 1 and isinstance(selected_items[0], EditableRectItem):
                item = selected_items[0]
                if item.data(0) is not None:
                    new_index = item.data(0)
                    if new_index != self.selected_roi_index:
                        self.selected_roi_index = new_index
                        self.roi_list_widget.setCurrentRow(self.selected_roi_index)
                    self.populate_roi_editor()
                    return

            self.selected_roi_index = None
            self.populate_roi_editor()
            self.roi_list_widget.clearSelection()
        except RuntimeError:
            # This can happen if the scene is deleted while a signal is pending.
            # It's safe to ignore in this context.
            self.log("Caught RuntimeError in on_selection_changed, ignoring.")

    def populate_roi_editor(self, preserve_focus=False):
        if self.selected_roi_index is None:
            self.roi_editor_group.setVisible(False)
            self.answer_editor_group.setVisible(False)
            self.identifier_editor_group.setVisible(False)
            self.qrcode_editor_group.setVisible(False)
            self.annotation_editor_group.setVisible(False)
            return

        self.roi_editor_group.setVisible(True)
        roi_data = self.rois[self.selected_roi_index]
        
        focused_widget = self.focusWidget() if preserve_focus else None

        roi_type = roi_data.get('type')
        self.roi_name_edit.setText(roi_data.get('name', ''))
        self.roi_type_combo.setCurrentText(roi_type)
        self.roi_x_edit.setText(f"{roi_data.get('x', 0):.2f}")
        self.roi_y_edit.setText(f"{roi_data.get('y', 0):.2f}")
        self.roi_w_edit.setText(f"{roi_data.get('width', 0):.2f}")
        self.roi_h_edit.setText(f"{roi_data.get('height', 0):.2f}")

        self.answer_editor_group.setVisible(False)
        self.identifier_editor_group.setVisible(False)
        self.qrcode_editor_group.setVisible(False)
        self.annotation_editor_group.setVisible(False)

        if roi_type == 'Answer':
            self.answer_editor_group.setVisible(True)
            self.ans_rows_edit.setText(roi_data.get('rows', ''))
            self.ans_cols_edit.setText(roi_data.get('cols', ''))
            self.ans_values_edit.setText(", ".join(roi_data.get('values', [])))
            self.roi_start_question_edit.setText(str(roi_data.get('start_question', '')))
            self.roi_end_question_edit.setText(str(roi_data.get('end_question', '')))
            self.roi_correct_mark_edit.setText(roi_data.get('correct_mark', ''))
            self.roi_wrong_mark_edit.setText(roi_data.get('wrong_mark', ''))
        elif roi_type == "Identifier":
            self.identifier_editor_group.setVisible(True)
            self.ident_rows_edit.setText(roi_data.get('rows', ''))
            self.ident_cols_edit.setText(roi_data.get('cols', ''))
            self.roi_order_combo.setCurrentText(roi_data.get('order', 'Row Wise'))
            self.roi_values_edit.setText(", ".join(roi_data.get('values', [])))
            self.roi_identifier_subtype_combo.setCurrentText(roi_data.get('subtype', 'Answer Script Identifier'))
        elif roi_type == "Qrcode":
            self.qrcode_editor_group.setVisible(True)
            self.roi_role_edit.setText(roi_data.get('role', ''))
        elif roi_type == "Annotation":
            self.annotation_editor_group.setVisible(True)
        
        if focused_widget and preserve_focus:
            focused_widget.setFocus()
            
    def load_image(self):
        dialog_key = "Open Image"
        initial_path = load_last_path(dialog_key)
        path, _ = QFileDialog.getOpenFileName(self, dialog_key, initial_path)
        if path:
            save_last_path(dialog_key, path)
            self.current_image = cv2.imread(path)
            if self.current_image is None:
                self.log(f"Error: Could not read image at {path}")
                return
            
            self.log(f"Image loaded: {path}")
            self.reset_template(keep_image=True)
            self.display_image(self.current_image)
            
            self.btn_learn_corner.setEnabled(True)
            self.template_combobox.setEnabled(True)
            self.btn_refresh_templates.setEnabled(True)

    def display_image(self, img):
        # Remove any existing pixmap before adding a new one
        for item in self.scene.items():
            if isinstance(item, QGraphicsPixmapItem):
                self.scene.removeItem(item)

        h, w, ch = img.shape
        bytes_per_line = ch * w
        rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.pixmap_item = self.scene.addPixmap(QPixmap.fromImage(q_img))
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def delete_selected_roi(self):
        if self.selected_roi_index is None: return
        index_to_delete = self.selected_roi_index
        
        self.log(f"Deleting ROI: {self.rois[index_to_delete]['name']}")

        del self.rois[index_to_delete]
        rect_item, text_item, grid_lines = self.roi_items.pop(index_to_delete)
        
        self.scene.removeItem(rect_item)
        self.scene.removeItem(text_item)
        for line in grid_lines:
            if line.scene(): self.scene.removeItem(line)

        self.roi_list_widget.takeItem(index_to_delete)

        for i, (rect_item, text_item, _) in enumerate(self.roi_items):
            rect_item.setData(0, i)
            text_item.setData(0, i)

        self.selected_roi_index = None
        self.populate_roi_editor()

    def add_roi(self, roi_data, select_after_creation=True):
        # Create a rect with top-left at (0,0)
        rect = QRectF(0, 0, roi_data['width'], roi_data['height'])
        final_rect_item = EditableRectItem(rect, self)
        # Set the item's position in the scene to the ROI's x and y
        final_rect_item.setPos(roi_data['x'], roi_data['y'])
        self.scene.addItem(final_rect_item)

        text_item = self.scene.addText(roi_data['name'])
        text_item.setPos(final_rect_item.pos() - QPointF(0, 10))
        text_item.setDefaultTextColor(QColor("green"))

        roi_index = len(self.rois)
        final_rect_item.setData(0, roi_index)
        text_item.setData(0, roi_index)

        self.rois.append(roi_data)
        self.roi_items.append((final_rect_item, text_item, []))
        self.roi_list_widget.addItem(roi_data['name'])
        self.draw_roi_grid(roi_data, roi_index)
        
        if select_after_creation:
            self.scene.clearSelection()
            final_rect_item.setSelected(True)
            self.roi_list_widget.setCurrentRow(roi_index)

    def save_template(self):
        if self.detected_corners is None or self.original_box_points is None:
            QMessageBox.warning(self, "Incomplete Setup", "Please detect 4 corners and define the 4-point content box before saving.")
            return

        rois_to_save = copy.deepcopy(self.rois)

        # If image was warped, transform ROI coordinates back to original image space
        if self.warp_matrix is not None:
            try:
                inverse_warp_matrix = np.linalg.inv(self.warp_matrix)
                for roi in rois_to_save:
                    # Get the four corners of the ROI in the warped image space
                    rect_corners = np.array([
                        [roi['x'], roi['y']],
                        [roi['x'] + roi['width'], roi['y']],
                        [roi['x'] + roi['width'], roi['y'] + roi['height']],
                        [roi['x'], roi['y'] + roi['height']]
                    ], dtype=np.float32)

                    # Transform these corners back to the original, unwarped image space
                    transformed_corners = cv2.perspectiveTransform(rect_corners.reshape(-1, 1, 2), inverse_warp_matrix)
                    
                    # The transformed shape is a quadrilateral.
                    # tl, tr, br, bl are its four corners.
                    tl, tr, br, bl = transformed_corners.reshape(4, 2)

                    # Calculate the average width and height of the quadrilateral
                    width_top = np.linalg.norm(tr - tl)
                    width_bottom = np.linalg.norm(br - bl)
                    avg_width = (width_top + width_bottom) / 2

                    height_left = np.linalg.norm(bl - tl)
                    height_right = np.linalg.norm(br - tr)
                    avg_height = (height_left + height_right) / 2

                    # Use the top-left corner of the transformed quad as the new x, y
                    x, y = tl[0], tl[1]

                    # Update the ROI data with the accurate, unwarped coordinates and dimensions
                    roi['x'], roi['y'], roi['width'], roi['height'] = float(x), float(y), float(avg_width), float(avg_height)

            except np.linalg.LinAlgError:
                QMessageBox.critical(self, "Error", "Could not process warp matrix. Cannot save ROI coordinates correctly.")
                return

        # Calculate relative offsets for box points from the top-left detected corner
        tl_corner_x = float(self.detected_corners[0][0])
        tl_corner_y = float(self.detected_corners[0][1])
        relative_box_points = [
            {'x': float(p[0]) - tl_corner_x, 'y': float(p[1]) - tl_corner_y} for p in self.original_box_points
        ]

        template_data = {
            'corner_properties': self.corner_properties,
            'template_corners': [ (float(p[0]), float(p[1])) for p in self.detected_corners.tolist() ],
            'box_points_relative': relative_box_points,
            'rois': rois_to_save
        }

        dialog_key = "Save Template"
        # The initial_path should be a directory, not a full file path, to allow the dialog to suggest a new name.
        last_saved_path = load_last_path(dialog_key)
        if last_saved_path and os.path.isfile(last_saved_path):
            initial_dir = os.path.dirname(last_saved_path)
            initial_filename = os.path.basename(last_saved_path)
        else:
            initial_dir = get_template_dir()
            initial_filename = "new_template.json" # Suggest a default new name

        path, _ = QFileDialog.getSaveFileName(self, dialog_key, os.path.join(initial_dir, initial_filename), "JSON Files (*.json)")
        if path:
            save_last_path(dialog_key, path)
            try:
                with open(path, 'w') as f:
                    json.dump(template_data, f, indent=4, cls=NumpyEncoder)
                self.log(f"Template saved successfully to {path}")
                self.populate_template_combobox() # Refresh list after saving a new template
            except Exception as e:
                self.log(f"Error saving template: {e}")

    def save_template_as(self):
        self.save_template() # Just reuse the main save logic

    def test_template(self):
        # TODO: Implement template testing logic
        self.log("Template testing not yet implemented.")
        QMessageBox.information(self, "Not Implemented", "The 'Test Template' functionality is not yet implemented.")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        view_rect = self.view.viewport().rect()
        button_size = self.zoom_in_button.sizeHint()
        margin = 10
        self.zoom_in_button.move(
            view_rect.left() + margin, 
            view_rect.bottom() - (button_size.height() * 2) - margin * 2
        )
        self.zoom_out_button.move(
            view_rect.left() + margin, 
            view_rect.bottom() - button_size.height() - margin
        )

    def reset_template(self, keep_image=False):
        self.log("Resetting template.")

        # Disconnect signal first to prevent any calls to on_selection_changed
        if self.scene: # Only disconnect if scene exists
            try:
                self.scene.selectionChanged.disconnect(self.on_selection_changed)
            except TypeError: # Handle case where it's not connected
                pass
        
        # Clear selected ROI index early
        self.selected_roi_index = None

        #self.btn_learn_corner.setEnabled(False)
        #self.btn_define_box.setEnabled(False)

        # Clear specific graphical elements managed by lists
        for item in self.learning_rects:
            if item.scene(): self.scene.removeItem(item)
        self.learning_rects.clear()

        for line in self.corner_box_lines:
            if line.scene(): self.scene.removeItem(line)
        self.corner_box_lines.clear()
        self.detected_corners = None

        # Remove ROIs and their associated graphical items
        for roi_item_tuple in self.roi_items:
            rect_item, text_item, grid_lines = roi_item_tuple
            if rect_item.scene(): self.scene.removeItem(rect_item)
            if text_item.scene(): self.scene.removeItem(text_item)
            for line in grid_lines:
                if line.scene(): self.scene.removeItem(line)
        self.rois.clear()
        self.roi_items.clear()
        self.roi_list_widget.clear()

        # Clear other visual elements (box points visual, corner handles)
        if self.box_rect_item and self.box_rect_item.scene(): self.scene.removeItem(self.box_rect_item)
        self.box_rect_item = None
        self.box_points.clear()
        self.corner_handles.clear() # Clear handles directly

        # Clear the scene's own items, but only non-pixmap if keeping image
        items_to_remove = []
        for item in self.scene.items():
            if not keep_image or not isinstance(item, QGraphicsPixmapItem):
                items_to_remove.append(item)
        for item in items_to_remove:
            self.scene.removeItem(item)

        # Reset state flags and properties
        self.is_defining_box = False
        self.is_setting_corner = False
        self.warped_image = None
        self.warp_matrix = None
        self.original_box_points = None
        if not keep_image:
            self.current_image = None
            self.pixmap_item = None
            # self.btn_load_template.setEnabled(False)
            self.corner_properties = {}
            self.template_corner_points = None
            
        self.set_interaction_mode(self.interaction_mode_group.checkedId())

        # Reconnect signal
        self.scene.selectionChanged.connect(self.on_selection_changed)

    def load_template_action(self, path=None):
        if self.current_image is None:
            self.log("Load template failed: No image loaded.")
            return
            
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Load Template", get_template_dir(), "JSON Files (*.json)")
        
        if not path:
            return

        try:
            self.log(f"Loading template from {path}...")
            with open(path, 'r') as f:
                template_data = json.load(f)

            self.reset_template(keep_image=True)

            # --- Warping Logic (as per answer_key_scanner) ---
            self.corner_properties = template_data.get('corner_properties', {})
            template_corners = np.array(template_data.get('template_corners'), dtype="float32")
            box_points_relative = template_data.get('box_points_relative', [])

            if len(template_corners) != 4 or len(box_points_relative) != 4:
                raise ValueError("Template is missing 'template_corners' or 'box_points_relative'.")

            # 1. Find corners in the current image
            page_corners = self.detector.find_corners(self.current_image, self.corner_properties)
            if page_corners is None:
                raise ValueError("Automatic corner detection failed on the new image using template properties.")
            self.detected_corners = page_corners # Store the detected corners
            self.log(f"DEBUG: Found page corners: {page_corners.tolist()}")

            # 2. Compute homography to find where the content box should be
            H, _ = cv2.findHomography(template_corners, page_corners)
            if H is None:
                raise ValueError("Could not compute homography from page corners.")
            self.log(f"DEBUG: Homography matrix: {H.tolist()}")

            # 3. Calculate the absolute points of the box in the template, then transform them
            tl_corner_template = template_corners[0]
            template_box_points_abs = np.array([[p['x'] + tl_corner_template[0], p['y'] + tl_corner_template[1]] for p in box_points_relative], dtype="float32")
            new_box_points = cv2.perspectiveTransform(template_box_points_abs.reshape(-1, 1, 2), H)
            
            self.log(f"DEBUG: Template box absolute points: {template_box_points_abs.tolist()}")
            self.log(f"DEBUG: Calculated new box points: {new_box_points.tolist()}")
            
            self.original_box_points = new_box_points.reshape(4, 2)

            # 4. Warp the image using these new box points
            self.warp_content_box()

            if self.warped_image is None:
                raise ValueError("Warping the content box resulted in an empty image.")

            # --- Plot ROIs on Warped Image ---
            if H is None or self.warp_matrix is None:
                raise ValueError("Could not compute necessary transformation matrices.")

            combined_matrix = self.warp_matrix @ H
            
            loaded_rois = template_data.get('rois', [])
            for roi_data in loaded_rois:
                # Get the corners of the ROI in the original template's coordinate space
                roi_corners = np.array([
                    [roi_data['x'], roi_data['y']],
                    [roi_data['x'] + roi_data['width'], roi_data['y']],
                    [roi_data['x'] + roi_data['width'], roi_data['y'] + roi_data['height']],
                    [roi_data['x'], roi_data['y'] + roi_data['height']]
                ], dtype=np.float32)

                # Transform ROI corners directly from template space to the final warped space
                final_roi_in_warp = cv2.perspectiveTransform(roi_corners.reshape(-1, 1, 2), combined_matrix)
                #final_roi_in_warp = roi_corners.reshape(-1, 1, 2).astype(np.float32)

                # Get the new bounding box and create the ROI
                x, y, w, h = cv2.boundingRect(final_roi_in_warp)
                
                scaled_roi = {
                    **roi_data,
                    'x': x, 'y': y, 'width': w, 'height': h
                }
                self.add_roi(scaled_roi, select_after_creation=False)
            
            self.log(f"Template loaded and {len(loaded_rois)} ROIs plotted on warped image.")
            self.set_interaction_mode(self.interaction_mode_group.checkedId())

        except Exception as e:
            self.log(f"Error loading template: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to load template:\n{str(e)}")

    def draw_roi_grid(self, roi_data, roi_index):
        if not (0 <= roi_index < len(self.roi_items)):
            return []

        # Remove old grid lines
        rect_item, text_item, old_grid_lines = self.roi_items[roi_index]
        for line in old_grid_lines:
            if line and line.scene():
                self.scene.removeItem(line)
        
        new_grid_lines = []
        rows, cols = 0, 0
        try:
            if roi_data['type'] in ['Identifier', 'Answer']:
                rows, cols = int(roi_data.get('rows', 0)), int(roi_data.get('cols', 0))
        except (ValueError, KeyError):
            rows, cols = 0, 0

        if rows > 1 or cols > 1:
            # Get geometry from the graphical item, which is the source of truth
            pos = rect_item.pos()
            rect = rect_item.rect()
            x, y, w, h = pos.x(), pos.y(), rect.width(), rect.height()

            pen = QPen(QColor("blue"), 1, Qt.PenStyle.DotLine)

            # Draw row lines
            if rows > 1:
                for i in range(1, rows):
                    line_y = y + i * (h / rows)
                    new_grid_lines.append(self.scene.addLine(x, line_y, x + w, line_y, pen))
            
            # Draw column lines
            if cols > 1:
                for i in range(1, cols):
                    line_x = x + i * (w / cols)
                    new_grid_lines.append(self.scene.addLine(line_x, y, line_x, y + h, pen))
        
        # Update the stored grid lines for this ROI
        self.roi_items[roi_index] = (rect_item, text_item, new_grid_lines)
        return new_grid_lines

    def toggle_grid_visibility(self):
        self.grid_visible = not self.grid_visible
        for _, _, grid_lines in self.roi_items:
            for line in grid_lines:
                line.setVisible(self.grid_visible)
        self.view.viewport().update()
        
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = TemplateBuilder()
    window.show()
    sys.exit(app.exec())