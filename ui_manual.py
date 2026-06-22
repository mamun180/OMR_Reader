import sys
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QListWidget, QListWidgetItem, QFrame, QStyle,
                             QApplication, QMessageBox) # Removed QPrintDialog
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewDialog
from PyQt6.QtWebEngineCore import QWebEnginePage # Added QWebEnginePage for WebAction.Copy
from PyQt6.QtGui import QDesktopServices, QPageLayout, QPageSize
from PyQt6.QtCore import QUrl, Qt, QSize, QEventLoop, QStandardPaths, QMarginsF
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
        
        # Add print and copy buttons
        self.print_button = QPushButton()
        self.print_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.print_button.setIconSize(QSize(24, 24))
        self.print_button.setToolTip("Print Manual")
        self.print_button.clicked.connect(self._print_manual)
        
        self.copy_button = QPushButton()
        self.copy_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.copy_button.setIconSize(QSize(24, 24))
        self.copy_button.setToolTip("Copy Text")
        self.copy_button.clicked.connect(self._copy_manual)

        # Layout for print and copy buttons
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.print_button)
        button_layout.addWidget(self.copy_button)
        button_layout.addStretch() # Push buttons to the left
        sidebar_layout.addLayout(button_layout)
        
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
    
    def _print_manual(self):
        self.print_button.setEnabled(False) # Disable button to prevent re-entrancy

        temp_dir = os.path.join(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation), "manual_previews")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        # Create a unique filename to avoid conflicts and allow multiple previews
        pdf_filename = f"manual_preview_{os.getpid()}_{hash(self.web_view.url())}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)

        def pdf_data_received_callback(pdf_data_bytes):
            if pdf_data_bytes:
                try:
                    with open(pdf_path, "wb") as f:
                        f.write(pdf_data_bytes)
                    QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))
                except Exception as e:
                    QMessageBox.warning(self, "Print Error", f"Failed to save or open PDF: {e}")
            else:
                QMessageBox.warning(self, "Print Error", "Failed to generate print preview PDF (no data).")
            
            self.print_button.setEnabled(True) # Re-enable the print button

        # Default page layout: A4, Portrait.
        default_page_layout = QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait, QMarginsF())
        
        self.web_view.page().printToPdf(pdf_data_received_callback, pageLayout=default_page_layout)

    def _copy_manual(self):
        # QWebEngineView.page().selectedText() is asynchronous.
        # For direct copy of selection, triggerAction is better.
        # If nothing is selected, we can copy the whole page's plain text.
        
        # Try to copy selected text first
        self.web_view.page().triggerAction(QWebEnginePage.WebAction.Copy)
        
        # Check if anything was actually copied (this check is not entirely reliable with triggerAction)
        # A more robust way would involve checking clipboard content after a short delay,
        # but for simplicity, we'll assume triggerAction worked if text was selected.
        # If not, we can fall back to copying all text.
        
        # Asynchronous retrieval of selected text, not ideal for immediate copy
        # self.web_view.page().runJavaScript("window.getSelection().toString();", 
        #     lambda selection: self._copy_text_to_clipboard(selection))

        # Fallback: if user wants to copy everything if nothing is selected
        # This requires getting the plain text, which can be done via JavaScript or toPlainText()
        # For QWebEngineView.toPlainText, you need to connect to a signal
        self.web_view.page().toPlainText(self._copy_all_text_to_clipboard)

    def _copy_all_text_to_clipboard(self, text):
        clipboard = QApplication.clipboard()
        # Only copy if clipboard is empty (meaning no selection was copied by triggerAction)
        # Or if we explicitly want to copy all text regardless of selection.
        # For now, let's copy all text as a fallback if no selection.
        if not clipboard.text(): # Only if clipboard is empty after triggerAction.
            clipboard.setText(text)
            QMessageBox.information(self, "Copy", "All manual text copied to clipboard.")
        else:
            QMessageBox.information(self, "Copy", "Selected text copied to clipboard.")

