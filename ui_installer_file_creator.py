import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QTabWidget, QLabel, QLineEdit, QPushButton, QFileDialog, QListWidget, 
                             QHBoxLayout, QMessageBox)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon

class InstallerBuilder(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Professional Installer Builder - Developer Edition")
        self.setFixedSize(700, 550)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        self.setup_ui()
        self.apply_styles()

    def setup_ui(self):
        # --- Tab 1: Project Metadata ---
        self.meta_tab = QWidget()
        self.tabs.addTab(self.meta_tab, "1. Project Info")
        meta_layout = QVBoxLayout(self.meta_tab)
        
        self.app_name_le = QLineEdit()
        self.app_name_le.setPlaceholderText("e.g., OptiMark Pro")
        self.app_title_le = QLineEdit()
        self.app_title_le.setPlaceholderText("e.g., Advanced OMR Scanner")
        self.app_version_le = QLineEdit()
        self.app_version_le.setPlaceholderText("1.0.0")
        
        meta_layout.addWidget(QLabel("Application Name:"))
        meta_layout.addWidget(self.app_name_le)
        meta_layout.addWidget(QLabel("Application Title (UI):"))
        meta_layout.addWidget(self.app_title_le)
        meta_layout.addWidget(QLabel("Version:"))
        meta_layout.addWidget(self.app_version_le)
        
        self.icon_le = QLineEdit()
        self.icon_le.setPlaceholderText("Path to .ico file")
        btn_icon = QPushButton("Select Icon")
        btn_icon.clicked.connect(self.select_icon)
        
        icon_layout = QHBoxLayout()
        icon_layout.addWidget(self.icon_le)
        icon_layout.addWidget(btn_icon)
        meta_layout.addWidget(QLabel("Application Icon:"))
        meta_layout.addLayout(icon_layout)
        meta_layout.addStretch()

        # --- Tab 2: File Selection ---
        self.file_tab = QWidget()
        self.tabs.addTab(self.file_tab, "2. File Selection")
        file_layout = QVBoxLayout(self.file_tab)
        
        self.main_file_le = QLineEdit()
        self.main_file_le.setPlaceholderText("Select Main Entry File (e.g., main.py)")
        btn_main = QPushButton("Browse")
        btn_main.clicked.connect(self.select_main_file)
        
        file_layout.addWidget(QLabel("Main Entry File:"))
        h_main = QHBoxLayout()
        h_main.addWidget(self.main_file_le)
        h_main.addWidget(btn_main)
        file_layout.addLayout(h_main)
        
        self.extra_files_list = QListWidget()
        btn_add_files = QPushButton("Add Additional Files (.py, .json, .txt)")
        btn_add_files.clicked.connect(self.add_extra_files)
        btn_add_folder = QPushButton("Add Asset Folder")
        btn_add_folder.clicked.connect(self.add_asset_folder)
        btn_clear = QPushButton("Clear Selection")
        btn_clear.clicked.connect(lambda: self.extra_files_list.clear())
        
        file_layout.addWidget(QLabel("Additional Files & Resources:"))
        file_layout.addWidget(self.extra_files_list)
        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_add_files)
        btn_row.addWidget(btn_add_folder)
        btn_row.addWidget(btn_clear)
        file_layout.addLayout(btn_row)

        # --- Tab 3: Build Configuration ---
        self.build_tab = QWidget()
        self.tabs.addTab(self.build_tab, "3. Build Config")
        build_layout = QVBoxLayout(self.build_tab)
        
        self.output_type = QListWidget()
        self.output_type.addItems(["Single EXE (Portable)", "Windows Installer (.msi)"])
        self.output_type.setCurrentRow(0)
        self.output_type.setFixedHeight(60)
        
        self.encryption_key_le = QLineEdit()
        self.encryption_key_le.setEchoMode(QLineEdit.EchoMode.Password)
        self.encryption_key_le.setPlaceholderText("AES-256 Key for Module Encryption")
        
        build_layout.addWidget(QLabel("Output Type:"))
        build_layout.addWidget(self.output_type)
        build_layout.addWidget(QLabel("Security Configuration:"))
        build_layout.addWidget(self.encryption_key_le)
        
        self.shortcut_cb = QPushButton("Desktop Icon Creation (Enabled)")
        self.shortcut_cb.setCheckable(True)
        self.shortcut_cb.setChecked(True)
        build_layout.addWidget(self.shortcut_cb)
        build_layout.addStretch()

        # --- Build Button ---
        self.build_btn = QPushButton("BUILD SECURE INSTALLER")
        self.build_btn.setObjectName("buildButton")
        self.build_btn.setMinimumHeight(50)
        self.build_btn.clicked.connect(self.run_build_process)
        self.layout.addWidget(self.build_btn)

    def select_icon(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Icon", "", "Icon Files (*.ico)")
        if file: self.icon_le.setText(file)

    def select_main_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Main File", "", "Python Files (*.py)")
        if file: self.main_file_le.setText(file)

    def add_extra_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files")
        if files: self.extra_files_list.addItems(files)

    def add_asset_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder: self.extra_files_list.addItem(f"[DIR] {folder}")

    def run_build_process(self):
        # Validation
        if not self.main_file_le.text():
            QMessageBox.warning(self, "Error", "Main entry file is required.")
            return
        
        # Simulating the build process as requested
        QMessageBox.information(self, "Build Started", 
                                f"Building installer for {self.app_name_le.text()} v{self.app_version_le.text()}...\n"
                                "1. Encrypting Python modules (AES-256)...\n"
                                "2. Bundling assets...\n"
                                "3. Generating secure launcher...\n"
                                "4. Compiling via PyInstaller...")
        
    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f0f0; }
            QLabel { font-weight: bold; color: #333; margin-top: 5px; }
            QLineEdit { padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
            QPushButton { padding: 8px; background-color: #2196F3; color: white; border: none; border-radius: 4px; }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton#buildButton { background-color: #4CAF50; font-size: 14px; font-weight: bold; }
            QPushButton#buildButton:hover { background-color: #45a049; }
            QTabWidget::pane { border: 1px solid #ccc; }
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = InstallerBuilder()
    window.show()
    sys.exit(app.exec())
