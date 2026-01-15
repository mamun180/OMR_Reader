import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QTabWidget, QLabel, QHBoxLayout, QGraphicsDropShadowEffect, 
                             QScrollArea, QStatusBar, QStyle, QMessageBox, QPushButton, QSplashScreen)
from PyQt6.QtCore import QSettings, Qt, QSize, QThread, QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPixmap, QPainter, QPainterPath
from ui_builder import TemplateBuilder
from ui_answer_key_scanner import AnswerKeyScannerWindow
from ui_checker import CheckerWindow
from ui_settings import SettingsPage
from ui_about import AboutWindow
from ui_registration import RegistrationPage
from ui_navigation import NavigationScreen
from ui_manual import ManualWindow
from theme import apply_stylesheet_and_floatation
from license_manager import verify_license
from resource_path import resource_path

class LicenseWorker(QObject):
    finished = pyqtSignal(bool, str, bool)

    def __init__(self, show_success_popup=False):
        super().__init__()
        self.show_success_popup = show_success_popup

    def check(self):
        is_valid, message = verify_license()
        self.finished.emit(is_valid, message, self.show_success_popup)

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
        self.is_licensed = False # Add license state flag

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0,0,0,0)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        self._create_tabs()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        copyright_label = QLabel("© Md. Mamunur Rashid; Email: mamunur.rashid180@gmail.com; Phone: +8801620694000 [All Rights Reserved]")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        font = copyright_label.font()
        font.setPointSize(8)
        font.setItalic(True)
        copyright_label.setFont(font)
        self.status_bar.addWidget(copyright_label)

        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        
        self.apply_theme_to_all()
        self.check_license()
        
        home_index = self.find_tab_by_name("Home")
        if home_index is not None:
            self.tab_widget.setCurrentIndex(home_index)
        self._on_tab_changed(self.tab_widget.currentIndex())


    def _create_tabs(self):
        self.home_page_widget = self._create_home_page()
        self.builder_page = TemplateBuilder()
        self.scanner_page = AnswerKeyScannerWindow()
        self.checker_page = CheckerWindow()
        self.settings_page = SettingsPage()
        
        about_scroll = QScrollArea()
        about_scroll.setWidgetResizable(True)
        about_scroll.setWidget(AboutWindow())
        self.about_page = about_scroll
        self.registration_page = RegistrationPage()

        # Add all main tabs first
        self.tab_widget.addTab(self.home_page_widget, "Home")
        self.tab_widget.addTab(self.builder_page, "Template Builder")
        self.tab_widget.addTab(self.scanner_page, "Answer Key Scanner")
        self.tab_widget.addTab(self.checker_page, "Answer Checker")
        self.tab_widget.addTab(self.settings_page, "Settings")
        self.tab_widget.addTab(self.about_page, "About")
        self.tab_widget.addTab(self.registration_page, "Registration")

        # Add the User Manual tab
        self.manual_page = ManualWindow()
        self.tab_widget.addTab(self.manual_page, "User Manual")

        # --- Add Icons to Tabs ---
        icon_map = {
            "Home": QStyle.StandardPixmap.SP_ComputerIcon,
            "Template Builder": QStyle.StandardPixmap.SP_FileIcon,
            "Answer Key Scanner": QStyle.StandardPixmap.SP_DialogYesButton,
            "Answer Checker": QStyle.StandardPixmap.SP_DialogApplyButton,
            "Settings": QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "About": QStyle.StandardPixmap.SP_MessageBoxInformation,
            "Registration": QStyle.StandardPixmap.SP_DialogApplyButton,
            "User Manual": QStyle.StandardPixmap.SP_DirHomeIcon
        }
        for i in range(self.tab_widget.count()):
            tab_name = self.tab_widget.tabText(i)
            icon = self.style().standardIcon(icon_map.get(tab_name, QStyle.StandardPixmap.SP_FileIcon))
            self.tab_widget.setTabIcon(i, icon)

        # Now create and insert the navigation page, then hide it
        self.navigation_page = NavigationScreen(self.tab_widget)
        self.tab_widget.insertTab(1, self.navigation_page, "Navigation")
        self.tab_widget.setTabIcon(1, self.style().standardIcon(QStyle.StandardPixmap.SP_DirLinkIcon))
        self.tab_widget.tabBar().setTabVisible(1, False)




        # --- Connect Signals ---
        self.registration_page.registration_successful.connect(lambda: self.check_license(show_success_popup=True))
        self.settings_page.settings_saved.connect(self.apply_theme_to_all)
        self.registration_page.refresh_button.clicked.connect(self.update_registration_status)


    def _create_home_page(self):
        home_widget = QWidget()
        layout = QVBoxLayout(home_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo_label = QLabel()
        pixmap = QPixmap(resource_path("images/logo.jpg"))
        circular_pixmap = _get_circular_pixmap(pixmap, 100)
        logo_label.setPixmap(circular_pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        logo_label.setGraphicsEffect(shadow)
        layout.addWidget(logo_label)

        title_label = QLabel("Chattogram Cantonment Public College")
        title_label.setObjectName("collegeTitleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        self.subtitle_label = QLabel("OMR Sheet Scanner")
        font = self.subtitle_label.font(); font.setPointSize(14)
        self.subtitle_label.setFont(font)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subtitle_label)

        self.start_button = QPushButton("Start the Process")
        self.start_button.setObjectName("start_button")
        self.start_button.clicked.connect(self._on_start_process_clicked)
        layout.addWidget(self.start_button)
        
        return home_widget

    def _on_start_process_clicked(self):
        if self.is_licensed:
            target_tab = "Navigation" # Changed to Navigation
        else:
            target_tab = "Registration"
            
        target_index = self.find_tab_by_name(target_tab)
        if target_index is not None:
            self.tab_widget.setCurrentIndex(target_index)

    def _on_tab_changed(self, index):
        current_tab_name = self.tab_widget.tabText(index)
        if current_tab_name in ["Home", "Navigation"]:
            self.tab_widget.tabBar().setVisible(False)
        else:
            self.tab_widget.tabBar().setVisible(True)

    def find_tab_by_name(self, name):
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == name:
                return i
        return None

    def apply_theme_to_all(self):
        apply_stylesheet_and_floatation(self)
        if hasattr(self.builder_page, 'apply_theme'): self.builder_page.apply_theme()
        if hasattr(self.scanner_page, 'apply_theme'): self.scanner_page.apply_theme()
        if hasattr(self.checker_page, 'apply_theme'): self.checker_page.apply_theme()

    def check_license(self, show_success_popup=False):
        self.thread = QThread()
        self.worker = LicenseWorker(show_success_popup)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.check)
        self.worker.finished.connect(self._handle_license_result)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def _handle_license_result(self, is_valid, message, show_success_popup):
        self.is_licensed = is_valid
        if is_valid:
            self.unlock_ui(show_popup=show_success_popup)
        else:
            self.lock_ui()
        self.update_registration_status()

    def lock_ui(self):
        """Disables features when the license is invalid."""
        restricted_tabs = ["Template Builder", "Answer Key Scanner", "Answer Checker", "Settings"]
        
        for i in range(self.tab_widget.count()):
            tab_name = self.tab_widget.tabText(i)
            if tab_name in restricted_tabs:
                self.tab_widget.setTabEnabled(i, False)
            else:
                self.tab_widget.setTabEnabled(i, True)

        self.start_button.setText("Register Application")
        self.start_button.setEnabled(True) # Ensure button is enabled
        self.subtitle_label.setText("Application is not registered")
        self.subtitle_label.setStyleSheet("color: #d32f2f;")


    def unlock_ui(self, show_popup=False):
        """Enables all features after a successful license validation."""
        for i in range(self.tab_widget.count()):
            self.tab_widget.setTabEnabled(i, True)
            
        self.start_button.setText("Start the Process")
        self.start_button.setEnabled(True)
        self.subtitle_label.setText("OMR Sheet Scanner")
        self.subtitle_label.setStyleSheet("")
        
        if show_popup:
            QMessageBox.information(self, "Success", "License activated successfully. All features are now enabled.")

    def update_registration_status(self):
        # Create a worker to check the license status in the background
        self.reg_status_thread = QThread()
        self.reg_status_worker = LicenseWorker()
        self.reg_status_worker.moveToThread(self.reg_status_thread)
        
        # Connect signals
        self.reg_status_thread.started.connect(self.reg_status_worker.check)
        self.reg_status_worker.finished.connect(lambda is_valid, message, show_popup: self._handle_reg_status_update(is_valid, message))
        self.reg_status_worker.finished.connect(self.reg_status_thread.quit)
        self.reg_status_worker.finished.connect(self.reg_status_worker.deleteLater)
        self.reg_status_thread.finished.connect(self.reg_status_thread.deleteLater)
        
        # Start the thread
        self.reg_status_thread.start()

    def _handle_reg_status_update(self, is_valid, message):
        if hasattr(self, 'registration_page') and self.registration_page:
            self.registration_page.update_status(is_valid, message)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Create and show splash screen
    splash_pix = QPixmap(resource_path("images/com_flash.png"))
    splash_pix = splash_pix.scaled(350, 350, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint)
    splash.show()

    window = OMRApp()

    # Close splash screen and show main window after a delay
    def show_main_window():
        splash.close()
        window.showMaximized()

    QTimer.singleShot(3000, show_main_window) # 3 seconds delay

    sys.exit(app.exec())
