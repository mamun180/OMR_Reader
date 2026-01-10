from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QPushButton, QWidget, QToolButton
from PyQt6.QtGui import QColor
from PyQt6.QtCore import QSettings

def get_theme_stylesheet():
    """
    Generates the full stylesheet for the application based on QSettings.
    """
    settings = QSettings("OptiMark Pro", "Defaults")
    color_name = settings.value("theme_color", "")
    opacity_percent = settings.value("theme_opacity_percent", 70, type=int)

    header_text_color = settings.value("header_text_color", "#000000")
    panel_text_color = settings.value("panel_text_color", "#FFFFFF")
    button_color_name = settings.value("button_color", "#FFFFFF")
    font_family = settings.value("font_family", "Segoe UI")
    font_size = settings.value("font_size", 12, type=int)
    button_height = settings.value("button_height", 30, type=int)
    
    if not color_name:
        return ""

    base_color = QColor(color_name)
    button_color = QColor(button_color_name)
    
    main_bg_color = base_color.name()
    
    alpha_value = int(opacity_percent * 2.55)
    panel_bg_color = f"rgba(0, 0, 0, {alpha_value})" 
    
    return f"""
        QMainWindow, QDialog, QWidget {{
            font-family: "{font_family}";
            font-size: {font_size}px;
        }}

        QMainWindow#OMRAppMainWindow, QDialog {{
            background-color: {main_bg_color};
        }}
        QStackedWidget > QWidget, QWidget#about_page {{
            background-color: transparent;
            border: none;
        }}

        QGroupBox, QFrame {{
            background-color: {panel_bg_color};
            color: {panel_text_color};
            border: 1px solid rgba(0,0,0,100);
            border-radius: 4px;
            margin-top: 1ex; 
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 3px;
            color: black;
            font-weight: bold;
        }}
        QGroupBox QLabel, QGroupBox QRadioButton, QGroupBox QCheckBox {{
            color: {panel_text_color};
            background-color: transparent;
        }}

        QRadioButton::indicator:checked {{
            background-color: steelblue;
            border: 1px solid steelblue;
            color: white;
        }}

        QCheckBox::indicator {{
            background-color: white;
            border: 1px solid #ccc;
            width: 15px;
            height: 15px;
            border-radius: 3px;
        }}
        QCheckBox::indicator:checked {{
            background-color: steelblue;
            border: 1px solid black;
            image: url('data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%20viewBox=%220%200%2024%2024%22%20fill=%22none%22%20stroke=%22white%22%20stroke-width=%223%22%20stroke-linecap=%22round%22%20stroke-linejoin=%22round%22%3E%3Cpolyline%20points=%2220%206%209%2017%204%2012%22%3E%3C/polyline%3E%3C/svg%3E');
        }}

        QTextEdit#log_panel, QWidget#left_panel_widget, QWidget#right_panel_widget {{
            background-color: {panel_bg_color};
            color: {panel_text_color};
            border-radius: 5px;
        }}

        QPushButton, QPushButton#corner-button, QToolButton {{
            background-color: {button_color.name()};
            color: {header_text_color};
            padding: 8px 12px;
            border-radius: 4px;
            border: 1px solid rgba(0,0,0,0.2);
            text-align: center;
            min-height: {button_height}px;
        }}

        QPushButton#start_button, QPushButton#nav-button {{
            font-size: {font_size + 8}px;
            font-weight: bold;
        }}

        QPushButton#start_button {{
             background-color: {button_color.darker(120).name()};
             color: {header_text_color};
             min-height: 40px; /* Lower height */
             font-size: {font_size + 6}px; /* Adjusted font size */
             border-style: outset; /* 3D effect */
             border-width: 2px;
             border-color: #f0f0f0 #a0a0a0 #a0a0a0 #f0f0f0;
        }}
        QPushButton#start_button:pressed {{
            border-style: inset;
        }}

        QPushButton#nav-button {{
            background-color: white;
            color: black;
            text-align: center;
        }}
        QPushButton#nav-button-active {{
            background-color: {button_color.name()};
            color: {header_text_color};
            text-align: center;
            font-size: {font_size + 8}px;
            font-weight: bold;
        }}
        QPushButton#btn_stop_scan {{
            background-color: #dc3545; /* Bootstrap danger red */
            color: white; /* Ensure text is visible */
            font-weight: bold;
        }}
        QPushButton#btn_stop_scan:hover {{
            background-color: #c82333; /* Darker red on hover */
        }}
        QPushButton#btn_stop_scan:pressed {{
            background-color: #bd2130; /* Even darker on pressed */
            border-style: inset;
        }}
        QPushButton:hover, QPushButton#corner-button:hover, QToolButton:hover {{
            background-color: {button_color.darker(110).name()};
        }}
        QPushButton:pressed, QPushButton#corner-button:pressed, QToolButton:pressed {{
            background-color: {button_color.darker(130).name()};
            border-style: inset;
        }}
        QPushButton:disabled, QToolButton:disabled {{
            background-color: #d3d3d3;
            color: #a0a0a0;
        }}

        QTabWidget::pane {{
            border-top: 2px solid {base_color.darker(180).name()};
        }}
        QTabBar::tab {{
            background: white;
            color: black;
            border: 1px solid #ccc;
            border-bottom: none; 
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 8px 20px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background: {base_color.name()};
            color: {header_text_color};
            border-bottom-color: {button_color.name()};
        }}
        QTabBar::tab:!selected:hover {{
            background: #f0f0f0;
        }}
        
        QLabel {{
            color: {header_text_color};
            background-color: transparent; 
            border: none;
        }}
        QLabel#collegeTitleLabel {{
            font-size: 20px;
        }}
        
        QLineEdit, QTextEdit, QComboBox {{
            background-color: #FFFFFF;
            color: #000000;
            border: 1px solid #ccc;
            border-radius: 3px;
            padding: 4px;
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        QComboBox::down-arrow {{
            image: url(C:/Users/mamun/Downloads/down-arrow.png);
            width: 12px;
            height: 12px;
        }}
         QComboBox QAbstractItemView {{
            background-color: white;
            color: black;
            selection-background-color: {base_color.lighter(120).name()};
        }}
        
        QScrollArea {{
            background-color: transparent;
            border: none;
        }}
        
        QTextBrowser#about-features-browser {{
            background-color: transparent;
            border: none;
            color: {panel_text_color};
        }}
    """

def apply_stylesheet_and_floatation(widget: QWidget):
    """
    Applies the global stylesheet and adds a "floatation" effect (drop shadow) to all buttons.
    We are assuming "floatation" means a drop shadow effect for a "floating" look.
    """
    stylesheet = get_theme_stylesheet()
    widget.setStyleSheet(stylesheet)
    
    buttons = widget.findChildren(QPushButton)
    tool_buttons = widget.findChildren(QToolButton)
    
    for button in buttons + tool_buttons:
        # Avoid applying effect multiple times if function is called repeatedly
        if not button.graphicsEffect():
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(15)
            shadow.setOffset(1, 1)
            shadow.setColor(QColor(0, 0, 0, 60))
            button.setGraphicsEffect(shadow)
