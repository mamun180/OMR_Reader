from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QGridLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QPixmap
from resource_path import resource_path

class NavigationScreen(QWidget):
    def __init__(self, tab_widget, parent=None):
        super().__init__(parent)
        self.tab_widget = tab_widget
        self.initUI()

    def initUI(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(20)

        # Logo
        logo_label = QLabel()
        pixmap = QPixmap(resource_path("images/logo.jpg"))
        logo_label.setPixmap(pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header_layout.addWidget(logo_label)

        # Title
        title_label = QLabel("Chattogram Cantonment Public College (OMR Checker) v:1.0.0")
        title_label.setObjectName("collegeTitleLabel")
        header_layout.addWidget(title_label)
        header_layout.addStretch(1) # Add stretch to push content to the left
        
        self.main_layout.addLayout(header_layout)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.main_layout.addWidget(separator)

        # Grid of buttons
        grid_layout = QGridLayout()
        grid_layout.setSpacing(20)
        grid_layout.setContentsMargins(20, 20, 20, 20)
        
        self.main_layout.addLayout(grid_layout)
        self.main_layout.addStretch(1)


        tabs = []
        for i in range(self.tab_widget.count()):
            tab_name = self.tab_widget.tabText(i)
            tab_icon = self.tab_widget.tabIcon(i)
            # Exclude 'Home', and the navigation tab itself
            if tab_name not in ["Home", "Navigation"]:
                tabs.append((tab_name, tab_icon))

        # Create buttons in a grid
        row, col = 0, 0
        for tab_name, tab_icon in tabs:
            button = QPushButton(f"  {tab_name}")
            button.setIcon(tab_icon)
            button.setIconSize(QSize(32, 32))
            button.setFixedSize(200, 60)
            button.clicked.connect(lambda _, name=tab_name: self.on_nav_button_clicked(name))
            grid_layout.addWidget(button, row, col)
            
            col += 1
            if col > 3: # 4 buttons per row
                col = 0
                row += 1

    def on_nav_button_clicked(self, tab_name):
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == tab_name:
                self.tab_widget.setCurrentIndex(i)
                break
