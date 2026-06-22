from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QMessageBox, QStackedWidget, QWidget)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
import requests
import json
from license_manager import get_machine_hash, save_license_key, LICENSE_URL

class RegistrationPage(QWidget):
    # Signal to notify the main window that registration was successful
    registration_successful = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registration Status")

        # --- Main Layout and Stacked Widget ---
        self.main_layout = QVBoxLayout(self)
        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack)

        # --- Create the two views ---
        self.status_view = self._create_status_view()
        self.register_view = self._create_register_view()

        self.stack.addWidget(self.status_view)
        self.stack.addWidget(self.register_view)

    def _create_status_view(self):
        """Creates the widget that shows the current license status."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        title_label = QLabel("Current License Status")
        font = title_label.font(); font.setPointSize(14); font.setBold(True)
        title_label.setFont(font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("Status: Unknown")
        font = self.status_label.font(); font.setPointSize(11)
        self.status_label.setFont(font)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.message_label = QLabel("Click 'Refresh' to check your current license status.")
        self.message_label.setWordWrap(True)
        font = self.message_label.font(); font.setPointSize(10)
        self.message_label.setFont(font)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.reregister_button = QPushButton("Register with New Key")
        self.reregister_button.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        
        self.refresh_button = QPushButton("Refresh Status")

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.reregister_button)

        layout.addWidget(title_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.message_label)
        layout.addStretch()
        layout.addLayout(button_layout)
        
        # --- Styling ---
        self.reregister_button.setObjectName("nav-button")
        self.refresh_button.setObjectName("nav-button-active")

        return widget

    def _create_register_view(self):
        """Creates the widget for entering a new license key."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.info_label = QLabel("Please enter your new license key to activate the application.")
        self.info_label.setWordWrap(True)
        
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Enter License Key")
        
        self.activation_status_label = QLabel("")
        self.activation_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.activate_button = QPushButton("Activate")
        self.back_button = QPushButton("Back to Status")

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.activate_button)
        button_layout.addWidget(self.back_button)
        
        layout.addWidget(self.info_label)
        layout.addWidget(self.key_input)
        layout.addWidget(self.activation_status_label)
        layout.addLayout(button_layout)

        # --- Connections ---
        self.activate_button.clicked.connect(self.handle_activation)
        self.back_button.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        
        # --- Styling ---
        self.activate_button.setObjectName("nav-button-active")
        self.back_button.setObjectName("nav-button")
        
        return widget
        
    def handle_activation(self):
        license_key = self.key_input.text().strip()
        if not license_key:
            self.show_message("Error", "License key cannot be empty.")
            return

        self.activation_status_label.setText("Activating, please wait...")
        self.activate_button.setEnabled(False)
        self.back_button.setEnabled(False)

        QTimer.singleShot(100, lambda: self.run_activation(license_key))
        
    def run_activation(self, license_key):
        machine_hash = get_machine_hash()
        app_name = "OMRApp"
        
        payload = {
            "key": license_key,
            "machine_hash": machine_hash,
            "app_name": app_name,
            "request_type": "activate"
        }
        
        try:
            response = requests.post(LICENSE_URL, json=payload, timeout=20)
            response.raise_for_status()
            response_data = response.json()
            
            if response_data.get("status") in ["SUCCESS_UNLIMITED", "SUCCESS_ACTIVATED"]:
                license_to_save = response_data.get("license", {"license_key": license_key, "machine_hash": machine_hash})
                if save_license_key(license_to_save):
                    self.show_message("Success", "Application activated successfully.")
                    self.registration_successful.emit() # EMIT SIGNAL
                    self.stack.setCurrentIndex(0) # Go back to status view
                else:
                    self.show_message("Error", "Could not save the license file.")
            else:
                message = response_data.get("message", "Unknown error during activation.")
                self.show_message("Activation Failed", message)

        except requests.exceptions.RequestException as e:
            self.show_message("Network Error", f"Could not connect to the license server: {e}")
        except json.JSONDecodeError:
            error_msg = f"Received an invalid response from the server. (Response code: {response.status_code})"
            if len(response.text) < 200:
                error_msg += f"\nResponse: {response.text}"
            self.show_message("Server Error", error_msg)
        except Exception as e:
            self.show_message("Error", f"An unexpected error occurred: {e}")

        # --- Reset UI on failure ---
        self.activation_status_label.setText("")
        self.activate_button.setEnabled(True)
        self.back_button.setEnabled(True)

    def show_message(self, title, message):
        QMessageBox.information(self, title, message)

    def update_status(self, is_valid, message):
        """Called by the main window to update the status display."""
        self.status_label.setText(f"Status: {'Valid' if is_valid else 'Invalid'}")
        self.message_label.setText(message)