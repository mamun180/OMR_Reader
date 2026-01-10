from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextBrowser, QSizePolicy
from PyQt6.QtCore import Qt

class AboutWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("about_page")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # App Name and Version
        title_label = QLabel("OptiMark Pro")
        font = title_label.font()
        font.setPointSize(20)
        font.setBold(True)
        title_label.setFont(font)
        layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addSpacing(15)

        version_label = QLabel("OMR Sheet Evaluation Software")
        font = version_label.font()
        font.setPointSize(12)
        version_label.setFont(font)
        layout.addWidget(version_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        version_label = QLabel("Version: 1.0.0")
        font = version_label.font()
        font.setPointSize(10)
        version_label.setFont(font)
        layout.addWidget(version_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addSpacing(20)

        # Description
        description_label = QLabel(
            "This application is designed to automate the evaluation of Optical Mark Recognition (OMR) "
            "answer sheets for academic examinations. It provides a fast, reliable, and offline solution "
            "for processing multiple-choice assessments with minimal manual intervention."
        )
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
        
        layout.addSpacing(15)

        # Key Features
        features_title = QLabel("<b>Key Features</b>")
        layout.addWidget(features_title)
        self.features_text_browser = QTextBrowser() # Made it an instance variable
        self.features_text_browser.setObjectName("about-features-browser")
        self.features_text_browser.setReadOnly(True)
        self.features_text_browser.setHtml(
            "<ul>"
            "<li>Automatic detection and evaluation of OMR sheets</li>"
            "<li>Customizable answer key and template support</li>"
            "<li>Batch processing and result export to Dynamic Excel sheets</li>"
            "<li>Detailed analytics and performance reports</li>"
            "<li>Manual review and correction options</li>"
            "<li>User-friendly interface with step-by-step guidance</li>"
            "<li>High accuracy with advanced image processing algorithms</li>"
            "<li>Multiple answer sheet processing support</li>"
            "<li>versatile and adaptable to various OMR formats</li>"
            "<li>support qr code scanning</li>"
            "<li>multiple bubble detection smart solutions</li>"
            "<li>Lightweight and easy to install</li>"
            "<li>Fully offline operation after installation</li>"
            "</ul>"
        )
        self.features_text_browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff) # Disable internal scrolling
        self.features_text_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff) # Disable internal scrolling
        self.features_text_browser.setFrameStyle(0) # No border
        # self.features_text_browser.setMinimumHeight(150) # Removed to allow natural expansion
        self.features_text_browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.features_text_browser)

        layout.addSpacing(15)

        # Intended Use
        intended_use_title = QLabel("<b>Intended Use</b>")
        layout.addWidget(intended_use_title)
        intended_use_text = QLabel(
            "This software is intended for educational assessment purposes. "
            "Users are advised to verify results before official publication. "
            "The developer is not responsible for errors caused by improper scanning or incorrect configuration."
        )
        intended_use_text.setWordWrap(True)
        layout.addWidget(intended_use_text)

        layout.addSpacing(15)
        
        # License Info
        license_title = QLabel("<b>License Information</b>")
        layout.addWidget(license_title)
        license_text = QLabel(
            "This software is licensed for use on a single computer. "
            "Internet access is required only during installation or license activation."
        )
        license_text.setWordWrap(True)
        layout.addWidget(license_text)

        layout.addSpacing(15)

        # Developer
        developer_title = QLabel("<b>Developer</b>")
        layout.addWidget(developer_title)
        developer_text = QLabel("Developed by Md. Mamunur Rashid<br>Assistant Teacher, Physics<br>Chattogram Cantonment Public College<br>Chattogram, Bangladesh")
        layout.addWidget(developer_text)

        layout.addSpacing(15)

        # Support
        support_title = QLabel("<b>Support</b>")
        layout.addWidget(support_title)
        support_text = QLabel("Email: mamunur.rashid180@gmail.com")
        layout.addWidget(support_text)
        
        # Removed layout.addStretch() to allow content to push layout size

        # Copyright
        copyright_label = QLabel("©2026 Md. Mamunur Rashid. All rights reserved.")
        font = copyright_label.font()
        font.setPointSize(8)
        font.setItalic(True)
        copyright_label.setFont(font)
        layout.addWidget(copyright_label, alignment=Qt.AlignmentFlag.AlignCenter)
