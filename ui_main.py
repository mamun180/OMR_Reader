import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QTabWidget, QLabel, QHBoxLayout, QGraphicsDropShadowEffect, 
                             QScrollArea, QStatusBar, QStyle, QMessageBox, QPushButton, QSplashScreen, QFrame)
from PyQt6.QtCore import QSettings, Qt, QSize, QTimer
from PyQt6.QtGui import QFont, QPixmap, QPainter, QPainterPath
from theme import apply_stylesheet_and_floatation
from license_manager import verify_license, load_license_key, decrypt_and_load_module
from resource_path import resource_path

# --- Pre-computation and imports that are always safe ---
def _get_circular_pixmap(pixmap, size):
    target = QPixmap(size, size)
    target.fill(Qt.GlobalColor.transparent)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    scaled_pixmap = pixmap.scaled(QSize(size, size), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setClipPath(path)
    x = int((size - scaled_pixmap.width()) / 2)
    y = int((size - scaled_pixmap.height()) / 2)
    painter.drawPixmap(x, y, scaled_pixmap)
    painter.end()
    return target

class OMRApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OptiMark Pro")
        self.setObjectName("OMRAppMainWindow")
        
        # Page widgets will be created on-demand
        self.home_page_widget = None
        self.registration_page = None
        self.settings_page = None
        self.about_page = None
        self.builder_page = None
        self.scanner_page = None
        self.checker_page = None
        self.navigation_page = None

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        self.bottom_panel = QFrame()
        self.bottom_panel.setObjectName("bottomInfoPanel")
        self.bottom_panel.setStyleSheet("#bottomInfoPanel { border-top: 1px solid #ccc; }")
        bottom_layout = QHBoxLayout(self.bottom_panel)
        bottom_layout.setContentsMargins(10, 0, 10, 0)
        
        copyright_label = QLabel("© Md. Mamunur Rashid; Email: mamunur.rashid180@gmail.com; Phone: +8801620694000 [All Rights Reserved]")
        font = copyright_label.font(); font.setPointSize(8); font.setItalic(True)
        copyright_label.setFont(font)
        
        version_label = QLabel("Version: 1.0.0"); version_label.setFont(font)

        bottom_layout.addWidget(copyright_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(version_label)
        
        main_layout.addWidget(self.bottom_panel)
        main_layout.setStretch(0, 98); main_layout.setStretch(1, 2)
        
        # UI is built assuming license is valid because this class is only called after a successful check
        self.build_full_ui()

        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.apply_theme_to_all()
        
        home_index = self.find_tab_by_name("Home")
        if home_index is not None:
            self.tab_widget.setCurrentIndex(home_index)
        self._on_tab_changed(self.tab_widget.currentIndex())

    def build_full_ui(self):
        """Creates and enables all features for a licensed user."""
        # --- Dynamically import pages ---
        from ui_builder import TemplateBuilder
        from ui_answer_key_scanner import AnswerKeyScannerWindow
        from ui_checker import CheckerWindow
        from ui_navigation import NavigationScreen
        from ui_settings import SettingsPage
        from ui_about import AboutWindow
        from ui_registration import RegistrationPage

        # --- Instantiate Pages ---
        self.home_page_widget = self._create_home_page()
        self.navigation_page = NavigationScreen(self.tab_widget)
        self.builder_page = TemplateBuilder()
        self.scanner_page = AnswerKeyScannerWindow()
        self.checker_page = CheckerWindow()
        self.settings_page = SettingsPage()
        about_scroll = QScrollArea(); about_scroll.setWidgetResizable(True); about_scroll.setWidget(AboutWindow())
        self.about_page = about_scroll
        self.registration_page = RegistrationPage()

        # --- Add Tabs in Order ---
        self.tab_widget.addTab(self.home_page_widget, "Home")
        self.tab_widget.insertTab(1, self.navigation_page, "Navigation")
        self.tab_widget.addTab(self.builder_page, "Template Builder")
        self.tab_widget.addTab(self.scanner_page, "Answer Key Scanner")
        self.tab_widget.addTab(self.checker_page, "Answer Checker")
        self.tab_widget.addTab(self.settings_page, "Settings")
        self.tab_widget.addTab(self.about_page, "About")
        self.tab_widget.addTab(self.registration_page, "Registration")

        # --- Connect Signals ---
        self.settings_page.settings_saved.connect(self.apply_theme_to_all)
        self.registration_page.registration_successful.connect(self.handle_registration_success)
        self.registration_page.refresh_button.clicked.connect(self.update_registration_status)
        
        # --- Apply Icons ---
        icon_map = {
            "Home": QStyle.StandardPixmap.SP_ComputerIcon,
            "Navigation": QStyle.StandardPixmap.SP_DirLinkIcon,
            "Template Builder": QStyle.StandardPixmap.SP_FileIcon,
            "Answer Key Scanner": QStyle.StandardPixmap.SP_DialogYesButton,
            "Answer Checker": QStyle.StandardPixmap.SP_DialogApplyButton,
            "Settings": QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "About": QStyle.StandardPixmap.SP_MessageBoxInformation,
            "Registration": QStyle.StandardPixmap.SP_DialogApplyButton,
        }
        for i in range(self.tab_widget.count()):
            tab_name = self.tab_widget.tabText(i)
            if tab_name in icon_map: self.tab_widget.setTabIcon(i, self.style().standardIcon(icon_map[tab_name]))
        
        self.start_button.setText("Start the Process")

    def _create_home_page(self):
        # ... (code remains the same)
        home_widget = QWidget()
        layout = QVBoxLayout(home_widget); layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label = QLabel(); pixmap = QPixmap(resource_path("images/logo.jpg"))
        circular_pixmap = _get_circular_pixmap(pixmap, 100); logo_label.setPixmap(circular_pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shadow = QGraphicsDropShadowEffect(); shadow.setBlurRadius(15); logo_label.setGraphicsEffect(shadow)
        layout.addWidget(logo_label)
        title_label = QLabel("Chattogram Cantonment Public College"); title_label.setObjectName("collegeTitleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(title_label)
        self.subtitle_label = QLabel("OMR Sheet Scanner"); font = self.subtitle_label.font(); font.setPointSize(14)
        self.subtitle_label.setFont(font); self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subtitle_label)
        self.start_button = QPushButton("Start the Process")
        self.start_button.setObjectName("start_button")
        self.start_button.clicked.connect(self._on_start_process_clicked)
        layout.addWidget(self.start_button)
        return home_widget

    def handle_registration_success(self):
        QMessageBox.information(self, "Success", "Registration successful! Please restart the application.")
        self.close()

    def update_registration_status(self):
        is_valid, message = verify_license()
        if self.registration_page:
            self.registration_page.update_status(is_valid, message)

    def _on_start_process_clicked(self):
        target_index = self.find_tab_by_name("Navigation")
        if target_index is not None: self.tab_widget.setCurrentIndex(target_index)

    def _on_tab_changed(self, index):
        if index == -1: return
        is_home_or_nav = self.tab_widget.tabText(index) in ["Home", "Navigation"]
        self.tab_widget.tabBar().setVisible(not is_home_or_nav)

    def find_tab_by_name(self, name):
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == name: return i
        return None

    def apply_theme_to_all(self):
        apply_stylesheet_and_floatation(self)
        for page in [self.builder_page, self.scanner_page, self.checker_page, self.settings_page, self.registration_page, self.about_page, self.navigation_page]:
            if page and hasattr(page, 'apply_theme'): page.apply_theme()

    def closeEvent(self, event):
        if self.checker_page: self.checker_page.save_settings()
        super().closeEvent(event)

if __name__ == "__main__":
    # --- Pre-UI License and Decryption Check ---
    print("Verifying license...")
    is_valid, message = verify_license()

    if not is_valid:
        print(f"License is not valid: {message}")
        # Even if not valid, we need to launch a minimal UI for registration
        from ui_registration import RegistrationPage # Local import
        app = QApplication(sys.argv)
        reg_window = RegistrationPage()
        reg_window.registration_successful.connect(app.quit)
        reg_window.show()
        sys.exit(app.exec())

    print("License valid. Decrypting core modules...")
    # Decrypt and load the modules in dependency order
    corner_detector_module = decrypt_and_load_module('corner_detector')
    core_omr_module = decrypt_and_load_module('core_omr')

    if core_omr_module is None or corner_detector_module is None:
        print("FATAL: Could not decrypt or load core application components. The application may be corrupt, or the license is invalid for this machine.")
        # We cannot show a QMessageBox here as QApplication is not running.
        # A simple console message is the only option.
        sys.exit(1)

    print("Core modules loaded. Starting application...")
    # --- Start Main Application ---
    app = QApplication(sys.argv)

    splash_pix = QPixmap(resource_path("images/com_flash.png"))
    splash_pix = splash_pix.scaled(350, 350, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint)
    splash.show()

    window = OMRApp()

    def show_main_window():
        splash.close()
        window.showMaximized()

    QTimer.singleShot(3000, show_main_window)

    sys.exit(app.exec())

