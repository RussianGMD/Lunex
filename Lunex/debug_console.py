import os
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QPlainTextEdit, QFileDialog
)
from themes import BLACK_THEME, WHITE_THEME
from core_utils import SoundManager

DEFAULT_DEBUG_BLACK = BLACK_THEME["debug_console"]
DEFAULT_DEBUG_WHITE = WHITE_THEME["debug_console"]


ClickSound = SoundManager


class DebugConsoleWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lunex - Debug Console")
        self.resize(620, 400)
        self.setMinimumSize(420, 260)

        base_dir = os.path.dirname(os.path.abspath(__file__))
        ico_file = os.path.join(base_dir, "icon.ico")
        if os.path.exists(ico_file):
            self.setWindowIcon(QIcon(ico_file))

        self.is_white = False
        self.theme_data = dict(DEFAULT_DEBUG_BLACK)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Top Action Bar
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(8)

        self.title_label = QLabel("DEBUG CONSOLE")
        self.title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        top_bar.addWidget(self.title_label)
        top_bar.addStretch()

        self.btn_save = QPushButton("Save to File")
        self.btn_copy = QPushButton("Copy")
        self.btn_clear = QPushButton("Clear")

        for btn in (self.btn_save, self.btn_copy, self.btn_clear):
            btn.setFixedHeight(28)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            top_bar.addWidget(btn)

        self.btn_save.clicked.connect(self.save_to_file)
        self.btn_copy.clicked.connect(self.copy_logs)
        self.btn_clear.clicked.connect(self.clear_logs)

        layout.addLayout(top_bar)

        # Log Output Box
        self.text_box = QPlainTextEdit()
        self.text_box.setReadOnly(True)
        self.text_box.setMaximumBlockCount(5000)
        self.text_box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.text_box)

        self.set_theme(DEFAULT_DEBUG_BLACK)

    def append_log(self, text: str):
        self.text_box.appendPlainText(text)
        sb = self.text_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    def save_to_file(self):
        SoundManager.play()
        text = self.text_box.toPlainText()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Debug Console",
            "debug_console.txt",
            "Text Files (*.txt);;All Files (*.*)"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(text)
            except Exception:
                pass

    def copy_logs(self):
        SoundManager.play()
        text = self.text_box.toPlainText()
        if text:
            QApplication.clipboard().setText(text)

    def clear_logs(self):
        SoundManager.play()
        self.text_box.clear()

    def set_theme(self, theme_or_is_white: dict | bool):
        if isinstance(theme_or_is_white, dict):
            self.is_white = bool(theme_or_is_white.get("is_white", False))
            base = DEFAULT_DEBUG_WHITE if self.is_white else DEFAULT_DEBUG_BLACK
            merged = dict(base)
            merged.update(theme_or_is_white)
            self.theme_data = merged
        else:
            self.is_white = bool(theme_or_is_white)
            self.theme_data = dict(DEFAULT_DEBUG_WHITE if self.is_white else DEFAULT_DEBUG_BLACK)

        t = self.theme_data
        self.setStyleSheet(f"background-color: {t.get('window_bg', '#0c0c0e')};")
        self.title_label.setStyleSheet(f"color: {t.get('title_text', '#ffffff')};")

        btn_style = f"""
            QPushButton {{
                background-color: {t.get("btn_bg", "#16161a")};
                color: {t.get("btn_text", "#e1e1e6")};
                border: 1px solid {t.get("btn_border", "#23232a")};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: {t.get("btn_hover_bg", "#202026")};
                border: 1px solid {t.get("btn_hover_border", "#3b82f6")};
                color: {t.get("btn_hover_text", "#ffffff")};
            }}
        """
        for btn in (self.btn_save, self.btn_copy, self.btn_clear):
            btn.setStyleSheet(btn_style)

        sb_bg = t.get("scrollbar_bg", "#f4f4f7" if self.is_white else "#101014")
        sb_handle = t.get("scrollbar_handle_bg", "#d4d4d8" if self.is_white else "#23232c")
        sb_hover = t.get("scrollbar_handle_hover_bg", "#3b82f6")

        self.text_box.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {t.get("textbox_bg", "#16161a")};
                color: {t.get("textbox_text", "#e1e1e6")};
                border: 1px solid {t.get("textbox_border", "#23232a")};
                border-radius: 6px;
                padding: 8px;
                font-family: 'Consolas', 'Segoe UI', monospace;
                font-size: 9.5pt;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {sb_bg};
                width: 6px;
                border-radius: 3px;
                margin: 2px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {sb_handle};
                min-height: 25px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {sb_hover};
            }}
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical {{
                border: none;
                background: none;
                height: 0px;
            }}
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
                background: none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)