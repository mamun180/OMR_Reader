import sys
import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem, QFrame
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, Qt
from resource_path import resource_path

class ManualWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_bengali = False
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                      stop:0 #4a90e2, stop:1 #50e3c2);
        """)
        sidebar_layout = QVBoxLayout(sidebar)

        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("""
            QListWidget {
                color: white;
                background-color: transparent;
                border: none;
            }
            QListWidget::item {
                padding: 10px;
            }
            QListWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
            QListWidget::item:selected {
                background-color: rgba(255, 255, 255, 0.3);
            }
        """)
        sidebar_layout.addWidget(self.nav_list)
        self.populate_nav_list()
        self.nav_list.currentItemChanged.connect(self.navigate_to_section)

        self.translate_button = QPushButton("Translate to বাংলা")
        self.translate_button.setStyleSheet("color: white; padding: 10px;")
        self.translate_button.clicked.connect(self.toggle_language)
        sidebar_layout.addWidget(self.translate_button)
        
        # Web View
        self.web_view = QWebEngineView()
        
        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.web_view)
        
        self.load_manual()

    def populate_nav_list(self):
        self.nav_list.clear()
        sections = [
            ("Introduction", "#introduction"),
            ("Installation", "#installation"),
            ("Registration", "#registration"),
            ("Template Builder", "#template-builder"),
            ("Answer Key Scanner", "#answer-key-scanner"),
            ("Answer Checker", "#answer-checker"),
            ("Settings", "#settings"),
        ]
        for name, anchor in sections:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, anchor)
            self.nav_list.addItem(item)

    def navigate_to_section(self, current, previous):
        if current:
            anchor = current.data(Qt.ItemDataRole.UserRole)
            self.web_view.page().runJavaScript(f"document.querySelector('{anchor}').scrollIntoView();")

    def toggle_language(self):
        self.is_bengali = not self.is_bengali
        self.load_manual()
        if self.is_bengali:
            self.translate_button.setText("Translate to English")
        else:
            self.translate_button.setText("Translate to বাংলা")

    def load_manual(self):
        if self.is_bengali:
            manual_path = resource_path("user_manual_bn.html")
        else:
            manual_path = resource_path("user_manual.html")
        
        self.web_view.setUrl(QUrl.fromLocalFile(manual_path))
