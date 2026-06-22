from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QGridLayout,
                             QHBoxLayout, QLabel, QFrame, QGraphicsDropShadowEffect)
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon, QColor, QFont
from resource_path import resource_path


class NavigationScreen(QWidget):
    refresh_requested = pyqtSignal()

    # (step_badge, tab_name, description, gradient_dark, gradient_light)
    WORKFLOW_STEPS = [
        ("01", "Template Builder",   "Design your OMR\nanswer sheet template",      "#1d4ed8", "#60a5fa"),
        ("02", "Answer Key Scanner", "Scan and save answer\nkeys for each exam",     "#166534", "#4ade80"),
        ("03", "Answer Checker",     "Grade student sheets\nin bulk or manually",    "#9a3412", "#fb923c"),
        ("04", "Result Combiner",    "Merge results from\nmultiple subjects",         "#581c87", "#c084fc"),
    ]

    OTHER_TABS = {
        "Settings":     "Configure paths, patterns and matching rules",
        "About":        "About OptiMark Pro",
        "Registration": "Activate your software license",
        "User Manual":  "Step-by-step user guide",
    }

    def __init__(self, tab_widget, parent=None):
        super().__init__(parent)
        self.tab_widget = tab_widget
        self.initUI()

    def initUI(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header bar ────────────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("nav_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 10, 20, 10)
        header_layout.setSpacing(14)

        home_btn = QPushButton()
        home_btn.setIcon(QIcon(resource_path("images/optimark.ico")))
        home_btn.setIconSize(QSize(38, 38))
        home_btn.setFixedSize(48, 48)
        home_btn.setFlat(True)
        home_btn.setToolTip("Go to Home and Refresh Application State")
        home_btn.clicked.connect(self._on_home_button_clicked)
        header_layout.addWidget(home_btn)

        logo_lbl = QLabel()
        pix = QPixmap(resource_path("images/logo.jpg"))
        logo_lbl.setPixmap(
            pix.scaled(46, 46, Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
        )
        header_layout.addWidget(logo_lbl)

        title_lbl = QLabel("Chattogram Cantonment Public College  ·  OMR Sheet Scanner  v1.0")
        title_lbl.setObjectName("collegeTitleLabel")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        root.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(sep)

        # ── Content ───────────────────────────────────────────────────────────
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 18, 28, 18)
        content_layout.setSpacing(14)
        root.addWidget(content)

        # Build tab icon map
        tab_icons = {}
        for i in range(self.tab_widget.count()):
            tab_icons[self.tab_widget.tabText(i)] = self.tab_widget.tabIcon(i)

        # Section header: SCAN WORKFLOW
        content_layout.addWidget(self._section_label("SCAN WORKFLOW", "#3b82f6"))

        # 2 × 2 card grid
        grid = QGridLayout()
        grid.setSpacing(18)
        grid.setContentsMargins(0, 4, 0, 4)

        for idx, (step, tab_name, desc, dark, light) in enumerate(self.WORKFLOW_STEPS):
            icon = tab_icons.get(tab_name, QIcon())
            card = self._make_workflow_card(
                step, tab_name, desc, icon, dark, light,
                lambda n=tab_name: self.on_nav_button_clicked(n)
            )
            grid.addWidget(card, idx // 2, idx % 2)

        content_layout.addLayout(grid)

        # Section header: OTHER TOOLS
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        content_layout.addWidget(sep2)

        content_layout.addWidget(self._section_label("OTHER TOOLS", "#94a3b8"))

        tools_row = QHBoxLayout()
        tools_row.setSpacing(10)
        for tab_name, tip in self.OTHER_TABS.items():
            icon = tab_icons.get(tab_name, QIcon())
            btn = QPushButton(f"  {tab_name}")
            btn.setIcon(icon)
            btn.setIconSize(QSize(20, 20))
            btn.setFixedHeight(38)
            btn.setMinimumWidth(145)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _, n=tab_name: self.on_nav_button_clicked(n))
            tools_row.addWidget(btn)
        tools_row.addStretch()
        content_layout.addLayout(tools_row)
        content_layout.addStretch()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _section_label(self, text, color):
        """A small coloured accent bar + bold uppercase section title."""
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        accent = QFrame()
        accent.setFrameShape(QFrame.Shape.VLine)
        accent.setFixedWidth(4)
        accent.setFixedHeight(18)
        accent.setStyleSheet(f"background: {color}; border: none; border-radius: 2px;")
        layout.addWidget(accent)

        lbl = QLabel(text)
        font = lbl.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() - 1)
        lbl.setFont(font)
        lbl.setStyleSheet(f"color: {color}; background: transparent; letter-spacing: 1px;")
        layout.addWidget(lbl)
        layout.addStretch()
        return w

    def _make_workflow_card(self, step, title, description, icon,
                            dark_color, light_color, on_click):
        card = QFrame()
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setFrameShape(QFrame.Shape.NoFrame)
        card.setFixedHeight(140)
        card.setMinimumWidth(200)
        card.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {dark_color}, stop:1 {light_color});
                border-radius: 14px;
            }}
            QFrame:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {light_color}, stop:1 {dark_color});
            }}
            QLabel {{
                color: white;
                background: transparent;
                border: none;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 90))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        # Top row: circular step badge + icon
        top_row = QHBoxLayout()
        top_row.setSpacing(0)

        badge = QLabel(step)
        badge.setFixedSize(36, 36)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet("""
            QLabel {
                background: rgba(255, 255, 255, 0.22);
                border-radius: 18px;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid rgba(255,255,255,0.4);
            }
        """)
        top_row.addWidget(badge)
        top_row.addStretch()

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(32, 32)
        p = icon.pixmap(QSize(30, 30))
        if not p.isNull():
            icon_lbl.setPixmap(p)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(icon_lbl)

        layout.addLayout(top_row)

        # Title
        title_lbl = QLabel(title)
        f = title_lbl.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 2)
        title_lbl.setFont(f)
        layout.addWidget(title_lbl)

        # Description
        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(
            "QLabel { color: rgba(255,255,255,0.82); background: transparent; }"
        )
        layout.addWidget(desc_lbl)

        card.mousePressEvent = (
            lambda e, fn=on_click: fn() if e.button() == Qt.MouseButton.LeftButton else None
        )
        return card

    def on_nav_button_clicked(self, tab_name):
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == tab_name:
                self.tab_widget.setCurrentIndex(i)
                break

    def _on_home_button_clicked(self):
        self.refresh_requested.emit()
