import os
import requests
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThread
from PyQt6.QtGui import QDoubleValidator, QIntValidator, QIcon
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QLineEdit, QComboBox, QFrame
)

from themes import BLACK_THEME, WHITE_THEME
from core_utils import get_icon_path, SoundManager
from ui_components import AnimatedToggle

# Version & Update Configuration
CURRENT_VERSION = "1.2"
UPDATE_URL = "https://raw.githubusercontent.com/RussianGMD/iuerfh/refs/heads/main/version.txt"

DEFAULT_SETTINGS_BLACK = BLACK_THEME["settings"]
DEFAULT_SETTINGS_WHITE = WHITE_THEME["settings"]


class UpdateCheckerThread(QThread):
    check_finished = pyqtSignal(bool, str)

    def run(self):
        try:
            resp = requests.get(UPDATE_URL, timeout=6)
            if resp.status_code == 200:
                remote_version = resp.text.strip()
                is_latest = (remote_version == CURRENT_VERSION)
                self.check_finished.emit(is_latest, remote_version)
            else:
                self.check_finished.emit(False, "")
        except Exception:
            self.check_finished.emit(False, "")


class SettingsSwitchRow(QFrame):
    def __init__(self, title: str, compact: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("switchRow")
        self.setFixedHeight(38)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)

        self.label = QLabel(title)
        self.toggle = AnimatedToggle()

        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.toggle)
        self.set_theme(DEFAULT_SETTINGS_BLACK)

    def set_theme(self, theme: dict | bool):
        if isinstance(theme, bool):
            theme = DEFAULT_SETTINGS_WHITE if theme else DEFAULT_SETTINGS_BLACK
        self.toggle.set_theme(theme)
        self.label.setStyleSheet(f"color: {theme.get('row_text', '#e1e1e6')}; font-size: 13px; font-weight: 500;")
        self.setStyleSheet(f"""
            QFrame#switchRow {{
                background-color: {theme.get("card_bg", "#16161a")};
                border: 1px solid {theme.get("card_border", "#23232a")};
                border-radius: 7px;
            }}
            QFrame#switchRow:hover {{
                border: 1px solid {theme.get("card_hover_border", "#32323d")};
            }}
        """)


class ComboRow(QFrame):
    value_changed = pyqtSignal()

    def __init__(self, title: str, items: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName("comboRow")
        self.setFixedHeight(38)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)

        self.label = QLabel(title)
        self.combo = QComboBox()
        self.combo.addItems(items)
        self.combo.setFixedHeight(26)
        self.combo.setFixedWidth(160)
        self.combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.combo.currentIndexChanged.connect(self._on_index_changed)

        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.combo)
        self.set_theme(DEFAULT_SETTINGS_BLACK)

    def set_theme(self, theme: dict | bool):
        if isinstance(theme, bool):
            theme = DEFAULT_SETTINGS_WHITE if theme else DEFAULT_SETTINGS_BLACK
        self.label.setStyleSheet(f"color: {theme.get('row_text', '#e1e1e6')}; font-size: 13px; font-weight: 500;")
        self.setStyleSheet(f"""
            QFrame#comboRow {{
                background-color: {theme.get("card_bg", "#16161a")};
                border: 1px solid {theme.get("card_border", "#23232a")};
                border-radius: 7px;
            }}
            QFrame#comboRow:hover {{
                border: 1px solid {theme.get("card_hover_border", "#32323d")};
            }}
        """)
        self.combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {theme.get("combo_bg", "#202026")};
                color: {theme.get("combo_text", "#c9c9d4")};
                border: 1px solid {theme.get("combo_border", "#2c2c36")};
                border-radius: 5px;
                padding-left: 10px;
                padding-right: 10px;
                font-size: 9pt;
                font-weight: 500;
            }}
            QComboBox:hover {{
                border: 1px solid {theme.get("combo_hover_border", "#3b82f6")};
                color: {theme.get("combo_hover_text", "#ffffff")};
            }}
            QComboBox::drop-down {{ border: none; width: 0px; }}
            QComboBox QAbstractItemView {{
                background-color: {theme.get("combo_popup_bg", "#16161a")};
                color: {theme.get("combo_popup_text", "#e1e1e6")};
                selection-background-color: {theme.get("combo_selection_bg", "#26334d")};
                selection-color: {theme.get("combo_selection_text", "#60a5fa")};
                border: 1px solid {theme.get("combo_popup_border", "#2c2c38")};
                border-radius: 5px;
                padding: 4px;
                outline: none;
            }}
        """)

    def _on_index_changed(self):
        self.value_changed.emit()
        SoundManager.play()


class FailDelayRow(QFrame):
    value_changed = pyqtSignal()

    def __init__(self, title: str = "Fail Delay (ms)", default_val: int = 500, parent=None):
        super().__init__(parent)
        self.default_val = default_val
        self.setObjectName("failDelayRow")
        self.setFixedHeight(38)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(8)

        self.label = QLabel(title)
        self.input_field = QLineEdit()
        self.input_field.setFixedSize(68, 26)
        self.input_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_field.editingFinished.connect(self._on_input_finished)

        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.input_field)

        self.set_value(default_val)
        self.set_theme(DEFAULT_SETTINGS_BLACK)

    def set_theme(self, theme: dict | bool):
        if isinstance(theme, bool):
            theme = DEFAULT_SETTINGS_WHITE if theme else DEFAULT_SETTINGS_BLACK
        self.label.setStyleSheet(f"color: {theme.get('row_text', '#e1e1e6')}; font-size: 13px; font-weight: 500;")
        self.setStyleSheet(f"""
            QFrame#failDelayRow {{
                background-color: {theme.get("card_bg", "#16161a")};
                border: 1px solid {theme.get("card_border", "#23232a")};
                border-radius: 7px;
            }}
            QFrame#failDelayRow:hover {{
                border: 1px solid {theme.get("card_hover_border", "#32323d")};
            }}
        """)
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.get("input_bg", "#202026")};
                color: {theme.get("input_text", "#ffffff")};
                border: 1px solid {theme.get("input_border", "#2c2c36")};
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
            }}
            QLineEdit:focus {{
                border: 1px solid {theme.get("input_focus_border", "#3b82f6")};
            }}
        """)

    def get_value(self) -> int:
        txt = self.input_field.text().lower().replace("ms", "").replace(" ", "").strip()
        try:
            val = int(float(txt))
        except ValueError:
            val = self.default_val
        return max(1, min(60000, val))

    def set_value(self, val: int):
        val = max(1, min(60000, int(val)))
        self.input_field.setText(f"{val}ms")

    def _on_input_finished(self):
        val = self.get_value()
        self.set_value(val)
        self.value_changed.emit()


class FailNotesCountCard(QFrame):
    value_changed = pyqtSignal()

    def __init__(self, title: str = "How Many Fail Notes", default_val: int = 1, parent=None):
        super().__init__(parent)
        self.default_val = max(1, int(default_val))
        self.setObjectName("failNotesCountCard")
        self.setFixedHeight(68)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 10)
        layout.setSpacing(6)

        self.title_lbl = QLabel(title)
        self.title_lbl.setFixedHeight(18)
        layout.addWidget(self.title_lbl)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(8)

        self.input_field = QLineEdit(str(self.default_val))
        self.input_field.setFixedHeight(26)
        self.input_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        validator = QIntValidator(1, 999999, self)
        self.input_field.setValidator(validator)
        self.input_field.editingFinished.connect(self._on_input_finished)
        bottom_row.addWidget(self.input_field, stretch=1)

        self.reset_btn = QPushButton()
        self.reset_btn.setFixedSize(26, 26)
        self.reset_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_btn.setToolTip("Reset to default")
        self.reset_btn.clicked.connect(self.reset_value)
        bottom_row.addWidget(self.reset_btn)

        layout.addLayout(bottom_row)
        self.set_theme(DEFAULT_SETTINGS_BLACK)

    def set_theme(self, theme: dict | bool):
        if isinstance(theme, bool):
            is_white = theme
            theme = DEFAULT_SETTINGS_WHITE if is_white else DEFAULT_SETTINGS_BLACK
        else:
            is_white = bool(theme.get("is_white", False))

        icon_path = get_icon_path("converter", is_white)
        if os.path.exists(icon_path):
            self.reset_btn.setIcon(QIcon(icon_path))
            self.reset_btn.setIconSize(QSize(13, 13))
            self.reset_btn.setText("")
        else:
            self.reset_btn.setText("R")

        self.setStyleSheet(f"""
            QFrame#failNotesCountCard {{
                background-color: {theme.get("card_bg", "#16161a")};
                border: 1px solid {theme.get("card_border", "#23232a")};
                border-radius: 7px;
            }}
            QFrame#failNotesCountCard:hover {{
                border: 1px solid {theme.get("card_hover_border", "#32323d")};
            }}
        """)
        self.title_lbl.setStyleSheet(f"color: {theme.get('row_text', '#e1e1e6')}; font-size: 12px; font-weight: 600;")
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.get("input_bg", "#202026")};
                color: {theme.get("input_text", "#ffffff")};
                border: 1px solid {theme.get("input_border", "#2c2c36")};
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
            }}
            QLineEdit:focus {{
                border: 1px solid {theme.get("input_focus_border", "#3b82f6")};
            }}
        """)
        self.reset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get("icon_btn_bg", "#202026")};
                color: {theme.get("icon_btn_text", "#8f8f9d")};
                border: 1px solid {theme.get("icon_btn_border", "#2c2c36")};
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme.get("icon_btn_hover_bg", "#2b2b34")};
                border: 1px solid {theme.get("icon_btn_hover_border", "#3b82f6")};
                color: {theme.get("icon_btn_hover_text", "#ffffff")};
            }}
        """)

    def get_value(self) -> int:
        txt = self.input_field.text().strip()
        try:
            val = int(txt)
        except ValueError:
            val = self.default_val
        if val <= 0:
            val = self.default_val
        return max(1, val)

    def set_value(self, val: int):
        try:
            v = int(val)
        except ValueError:
            v = self.default_val
        if v <= 0:
            v = self.default_val
        self.input_field.setText(str(max(1, v)))

    def reset_value(self):
        SoundManager.play()
        self.set_value(self.default_val)
        self.value_changed.emit()

    def _on_input_finished(self):
        val = self.get_value()
        self.set_value(val)
        self.value_changed.emit()


class FailSettingCard(QFrame):
    value_changed = pyqtSignal()

    def __init__(self, title: str, default_val: float, parent=None):
        super().__init__(parent)
        self.default_val = max(0.01, min(100.0, float(default_val)))
        self.setObjectName("failSettingCard")
        self.setFixedHeight(70)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        self.title_lbl = QLabel(title)
        self.title_lbl.setFixedHeight(24)
        top_row.addWidget(self.title_lbl)
        top_row.addStretch()

        self.input_field = QLineEdit(self._format_val(self.default_val))
        self.input_field.setFixedSize(52, 24)
        self.input_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_field.editingFinished.connect(self._on_input_finished)
        top_row.addWidget(self.input_field)

        self.reset_btn = QPushButton()
        self.reset_btn.setFixedSize(24, 24)
        self.reset_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_btn.setToolTip("Reset to default")
        self.reset_btn.clicked.connect(self.reset_value)
        top_row.addWidget(self.reset_btn)

        layout.addLayout(top_row)

        # Slider range: 1 to 10000 (representing 0.01% to 100.00%)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setFixedHeight(20)
        self.slider.setRange(1, 10000)
        self.slider.setValue(int(round(self.default_val * 100)))
        self.slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider.valueChanged.connect(self._on_slider_moved)
        layout.addWidget(self.slider)

        self.set_theme(DEFAULT_SETTINGS_BLACK)

    @staticmethod
    def _format_val(val: float) -> str:
        formatted = f"{val:.2f}".rstrip("0").rstrip(".")
        return formatted if formatted else "0.01"

    def set_theme(self, theme: dict | bool):
        if isinstance(theme, bool):
            is_white = theme
            theme = DEFAULT_SETTINGS_WHITE if is_white else DEFAULT_SETTINGS_BLACK
        else:
            is_white = bool(theme.get("is_white", False))

        icon_path = get_icon_path("converter", is_white)
        if os.path.exists(icon_path):
            self.reset_btn.setIcon(QIcon(icon_path))
            self.reset_btn.setIconSize(QSize(13, 13))
            self.reset_btn.setText("")
        else:
            self.reset_btn.setText("R")

        self.setStyleSheet(f"""
            QFrame#failSettingCard {{
                background-color: {theme.get("card_bg", "#16161a")};
                border: 1px solid {theme.get("card_border", "#23232a")};
                border-radius: 7px;
            }}
            QFrame#failSettingCard:hover {{
                border: 1px solid {theme.get("card_hover_border", "#32323d")};
            }}
        """)
        self.title_lbl.setStyleSheet(f"color: {theme.get('row_text', '#e1e1e6')}; font-size: 12px; font-weight: 600;")
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.get("input_bg", "#202026")};
                color: {theme.get("input_text", "#ffffff")};
                border: 1px solid {theme.get("input_border", "#2c2c36")};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
            }}
            QLineEdit:focus {{
                border: 1px solid {theme.get("input_focus_border", "#3b82f6")};
            }}
        """)
        self.reset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get("icon_btn_bg", "#202026")};
                color: {theme.get("icon_btn_text", "#8f8f9d")};
                border: 1px solid {theme.get("icon_btn_border", "#2c2c36")};
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme.get("icon_btn_hover_bg", "#2b2b34")};
                border: 1px solid {theme.get("icon_btn_hover_border", "#3b82f6")};
                color: {theme.get("icon_btn_hover_text", "#ffffff")};
            }}
        """)
        self.slider.setStyleSheet(f"""
            QSlider {{ height: 20px; }}
            QSlider::groove:horizontal {{
                height: 5px;
                background-color: {theme.get("slider_groove_bg", "#202026")};
                border: 1px solid {theme.get("slider_groove_border", "#2c2c36")};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background-color: {theme.get("slider_subpage_bg", "#3b82f6")};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background-color: {theme.get("slider_handle_bg", "#ffffff")};
                border: {theme.get("slider_handle_border", "none")};
                width: 12px; height: 12px; margin: -4px 0; border-radius: 6px;
            }}
            QSlider::handle:horizontal:hover {{
                background-color: {theme.get("slider_handle_hover_bg", "#e2e8f0")};
            }}
        """)

    def get_value(self) -> float:
        return round(self.slider.value() / 100.0, 2)

    def set_value(self, val: float):
        val = max(0.01, min(100.0, round(float(val), 2)))
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(val * 100)))
        self.slider.blockSignals(False)
        self.input_field.setText(self._format_val(val))

    def reset_value(self):
        SoundManager.play()
        self.set_value(self.default_val)
        self.value_changed.emit()

    def _on_slider_moved(self, int_val: int):
        float_val = round(int_val / 100.0, 2)
        self.input_field.setText(self._format_val(float_val))
        self.value_changed.emit()

    def _on_input_finished(self):
        txt = self.input_field.text().replace("%", "").replace(",", ".").strip()
        try:
            val = float(txt)
        except ValueError:
            val = self.default_val
        if val <= 0.0:
            val = 0.01
        self.set_value(val)
        self.value_changed.emit()

class SpeedLimitCard(QFrame):
    value_changed = pyqtSignal()

    def __init__(self, title: str, default_val: float, is_slow: bool = True, parent=None):
        super().__init__(parent)
        self.default_val = default_val
        self.is_slow = is_slow
        self.setObjectName("speedLimitCard")
        self.setFixedHeight(38)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(8)

        self.label = QLabel(title)
        self.input_field = QLineEdit()
        self.input_field.setFixedSize(54, 26)
        self.input_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_field.editingFinished.connect(self._on_input_finished)

        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.input_field)

        self.set_value(default_val)
        self.set_theme(DEFAULT_SETTINGS_BLACK)

    def set_theme(self, theme: dict | bool):
        if isinstance(theme, bool):
            theme = DEFAULT_SETTINGS_WHITE if theme else DEFAULT_SETTINGS_BLACK
        self.label.setStyleSheet(f"color: {theme.get('row_text', '#e1e1e6')}; font-size: 13px; font-weight: 500;")
        self.setStyleSheet(f"""
            QFrame#speedLimitCard {{
                background-color: {theme.get("card_bg", "#16161a")};
                border: 1px solid {theme.get("card_border", "#23232a")};
                border-radius: 7px;
            }}
            QFrame#speedLimitCard:hover {{
                border: 1px solid {theme.get("card_hover_border", "#32323d")};
            }}
        """)
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.get("input_bg", "#202026")};
                color: {theme.get("input_text", "#ffffff")};
                border: 1px solid {theme.get("input_border", "#2c2c36")};
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
            }}
            QLineEdit:focus {{
                border: 1px solid {theme.get("input_focus_border", "#3b82f6")};
            }}
        """)

    def get_value(self) -> float:
        txt = self.input_field.text().lower().replace("x", "").replace(" ", "").replace(",", ".").strip()
        try:
            val = float(txt)
        except ValueError:
            val = self.default_val
        if self.is_slow:
            return max(0.01, min(1.0, val))
        else:
            return max(1.0, min(10.0, val))

    def set_value(self, val: float):
        if self.is_slow:
            val = max(0.01, min(1.0, float(val)))
        else:
            val = max(1.0, min(10.0, float(val)))
        formatted = f"{val:.2f}".rstrip('0').rstrip('.')
        self.input_field.setText(f"{formatted}x")

    def _on_input_finished(self):
        val = self.get_value()
        self.set_value(val)
        self.value_changed.emit()


class SpeedChanceCard(QFrame):
    value_changed = pyqtSignal()

    def __init__(self, title: str, default_val: float = 50.0, parent=None):
        super().__init__(parent)
        self.default_val = default_val
        self.setObjectName("speedChanceCard")
        self.setFixedHeight(38)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(8)

        self.label = QLabel(title)
        self.input_field = QLineEdit()
        self.input_field.setFixedSize(54, 26)
        self.input_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_field.editingFinished.connect(self._on_input_finished)

        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.input_field)

        self.set_value(default_val)
        self.set_theme(DEFAULT_SETTINGS_BLACK)

    def set_theme(self, theme: dict | bool):
        if isinstance(theme, bool):
            theme = DEFAULT_SETTINGS_WHITE if theme else DEFAULT_SETTINGS_BLACK
        self.label.setStyleSheet(f"color: {theme.get('row_text', '#e1e1e6')}; font-size: 13px; font-weight: 500;")
        self.setStyleSheet(f"""
            QFrame#speedChanceCard {{
                background-color: {theme.get("card_bg", "#16161a")};
                border: 1px solid {theme.get("card_border", "#23232a")};
                border-radius: 7px;
            }}
            QFrame#speedChanceCard:hover {{
                border: 1px solid {theme.get("card_hover_border", "#32323d")};
            }}
        """)
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.get("input_bg", "#202026")};
                color: {theme.get("input_text", "#ffffff")};
                border: 1px solid {theme.get("input_border", "#2c2c36")};
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
            }}
            QLineEdit:focus {{
                border: 1px solid {theme.get("input_focus_border", "#3b82f6")};
            }}
        """)

    def get_value(self) -> float:
        txt = self.input_field.text().replace("%", "").replace(",", ".").strip()
        try:
            val = float(txt)
        except ValueError:
            val = self.default_val
        return max(0.0, min(100.0, val))

    def set_value(self, val: float):
        val = max(0.0, min(100.0, float(val)))
        formatted = f"{val:.1f}".rstrip('0').rstrip('.')
        self.input_field.setText(f"{formatted}%")

    def _on_input_finished(self):
        val = self.get_value()
        self.set_value(val)
        self.value_changed.emit()


class StepSettingCard(QFrame):
    value_changed = pyqtSignal()

    def __init__(self, title: str, default_val: int = 5, min_val: int = 1, max_val: int = 100, parent=None):
        super().__init__(parent)
        self.default_val = default_val
        self.min_val = min_val
        self.max_val = max_val
        self.setObjectName("stepSettingCard")
        self.setFixedHeight(70)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        self.title_lbl = QLabel(title)
        self.title_lbl.setFixedHeight(24)
        top_row.addWidget(self.title_lbl)
        top_row.addStretch()

        self.input_field = QLineEdit(str(default_val))
        self.input_field.setFixedSize(48, 24)
        self.input_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        validator = QIntValidator(min_val, max_val, self)
        self.input_field.setValidator(validator)
        self.input_field.editingFinished.connect(self._on_input_finished)
        top_row.addWidget(self.input_field)

        self.reset_btn = QPushButton()
        self.reset_btn.setFixedSize(24, 24)
        self.reset_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_btn.setToolTip("Reset to default")
        self.reset_btn.clicked.connect(self.reset_value)
        top_row.addWidget(self.reset_btn)

        layout.addLayout(top_row)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setFixedHeight(20)
        self.slider.setRange(min_val, max_val)
        self.slider.setValue(default_val)
        self.slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider.valueChanged.connect(self._on_slider_moved)
        layout.addWidget(self.slider)

        self.set_theme(DEFAULT_SETTINGS_BLACK)

    def set_theme(self, theme: dict | bool):
        if isinstance(theme, bool):
            is_white = theme
            theme = DEFAULT_SETTINGS_WHITE if is_white else DEFAULT_SETTINGS_BLACK
        else:
            is_white = bool(theme.get("is_white", False))

        icon_path = get_icon_path("converter", is_white)
        if os.path.exists(icon_path):
            self.reset_btn.setIcon(QIcon(icon_path))
            self.reset_btn.setIconSize(QSize(13, 13))
            self.reset_btn.setText("")
        else:
            self.reset_btn.setText("R")

        self.setStyleSheet(f"""
            QFrame#stepSettingCard {{
                background-color: {theme.get("card_bg", "#16161a")};
                border: 1px solid {theme.get("card_border", "#23232a")};
                border-radius: 7px;
            }}
            QFrame#stepSettingCard:hover {{
                border: 1px solid {theme.get("card_hover_border", "#32323d")};
            }}
        """)
        self.title_lbl.setStyleSheet(f"color: {theme.get('row_text', '#e1e1e6')}; font-size: 12px; font-weight: 600;")
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.get("input_bg", "#202026")};
                color: {theme.get("input_text", "#ffffff")};
                border: 1px solid {theme.get("input_border", "#2c2c36")};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
            }}
            QLineEdit:focus {{
                border: 1px solid {theme.get("input_focus_border", "#3b82f6")};
            }}
        """)
        self.reset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get("icon_btn_bg", "#202026")};
                color: {theme.get("icon_btn_text", "#8f8f9d")};
                border: 1px solid {theme.get("icon_btn_border", "#2c2c36")};
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme.get("icon_btn_hover_bg", "#2b2b34")};
                border: 1px solid {theme.get("icon_btn_hover_border", "#3b82f6")};
                color: {theme.get("icon_btn_hover_text", "#ffffff")};
            }}
        """)
        self.slider.setStyleSheet(f"""
            QSlider {{ height: 20px; }}
            QSlider::groove:horizontal {{
                height: 5px;
                background-color: {theme.get("slider_groove_bg", "#202026")};
                border: 1px solid {theme.get("slider_groove_border", "#2c2c36")};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background-color: {theme.get("slider_subpage_bg", "#3b82f6")};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background-color: {theme.get("slider_handle_bg", "#ffffff")};
                border: {theme.get("slider_handle_border", "none")};
                width: 12px; height: 12px; margin: -4px 0; border-radius: 6px;
            }}
            QSlider::handle:horizontal:hover {{
                background-color: {theme.get("slider_handle_hover_bg", "#e2e8f0")};
            }}
        """)

    def get_value(self) -> int:
        return self.slider.value()

    def set_value(self, val: int):
        val = max(self.min_val, min(self.max_val, int(val)))
        self.slider.blockSignals(True)
        self.slider.setValue(val)
        self.slider.blockSignals(False)
        self.input_field.setText(str(val))

    def reset_value(self):
        SoundManager.play()
        self.set_value(self.default_val)
        self.value_changed.emit()

    def _on_slider_moved(self, int_val: int):
        self.input_field.setText(str(int_val))
        self.value_changed.emit()

    def _on_input_finished(self):
        txt = self.input_field.text().strip()
        try:
            val = int(txt)
        except ValueError:
            val = self.default_val
        self.set_value(val)
        self.value_changed.emit()


class TransposeSettingCard(QFrame):
    value_changed = pyqtSignal()

    def __init__(self, title: str, default_val: int = 0, min_val: int = -24, max_val: int = 24, parent=None):
        super().__init__(parent)
        self.default_val = default_val
        self.min_val = min_val
        self.max_val = max_val
        self.setObjectName("transposeMacroCard")
        self.setFixedHeight(70)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        self.title_lbl = QLabel(title)
        self.title_lbl.setFixedHeight(24)
        top_row.addWidget(self.title_lbl)
        top_row.addStretch()

        self.input_field = QLineEdit("0")
        self.input_field.setFixedSize(48, 24)
        self.input_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        validator = QIntValidator(min_val, max_val, self)
        self.input_field.setValidator(validator)
        self.input_field.editingFinished.connect(self._on_input_finished)
        top_row.addWidget(self.input_field)

        self.reset_btn = QPushButton()
        self.reset_btn.setFixedSize(24, 24)
        self.reset_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_btn.setToolTip("Reset to default")
        self.reset_btn.clicked.connect(self.reset_value)
        top_row.addWidget(self.reset_btn)

        layout.addLayout(top_row)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setFixedHeight(20)
        self.slider.setRange(min_val, max_val)
        self.slider.setValue(default_val)
        self.slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider.valueChanged.connect(self._on_slider_moved)
        layout.addWidget(self.slider)

        self.set_theme(DEFAULT_SETTINGS_BLACK)

    def set_theme(self, theme: dict | bool):
        if isinstance(theme, bool):
            is_white = theme
            theme = DEFAULT_SETTINGS_WHITE if is_white else DEFAULT_SETTINGS_BLACK
        else:
            is_white = bool(theme.get("is_white", False))

        icon_path = get_icon_path("converter", is_white)
        if os.path.exists(icon_path):
            self.reset_btn.setIcon(QIcon(icon_path))
            self.reset_btn.setIconSize(QSize(13, 13))
            self.reset_btn.setText("")
        else:
            self.reset_btn.setText("R")

        self.setStyleSheet(f"""
            QFrame#transposeMacroCard {{
                background-color: {theme.get("card_bg", "#16161a")};
                border: 1px solid {theme.get("card_border", "#23232a")};
                border-radius: 7px;
            }}
            QFrame#transposeMacroCard:hover {{
                border: 1px solid {theme.get("card_hover_border", "#32323d")};
            }}
        """)
        self.title_lbl.setStyleSheet(f"color: {theme.get('row_text', '#e1e1e6')}; font-size: 12px; font-weight: 600;")
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.get("input_bg", "#202026")};
                color: {theme.get("input_text", "#ffffff")};
                border: 1px solid {theme.get("input_border", "#2c2c36")};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
            }}
            QLineEdit:focus {{
                border: 1px solid {theme.get("input_focus_border", "#3b82f6")};
            }}
        """)
        self.reset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get("icon_btn_bg", "#202026")};
                color: {theme.get("icon_btn_text", "#8f8f9d")};
                border: 1px solid {theme.get("icon_btn_border", "#2c2c36")};
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme.get("icon_btn_hover_bg", "#2b2b34")};
                border: 1px solid {theme.get("icon_btn_hover_border", "#3b82f6")};
                color: {theme.get("icon_btn_hover_text", "#ffffff")};
            }}
        """)
        self.slider.setStyleSheet(f"""
            QSlider {{ height: 20px; }}
            QSlider::groove:horizontal {{
                height: 5px;
                background-color: {theme.get("slider_groove_bg", "#202026")};
                border: 1px solid {theme.get("slider_groove_border", "#2c2c36")};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background-color: {theme.get("slider_subpage_bg", "#3b82f6")};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background-color: {theme.get("slider_handle_bg", "#ffffff")};
                border: {theme.get("slider_handle_border", "none")};
                width: 12px; height: 12px; margin: -4px 0; border-radius: 6px;
            }}
            QSlider::handle:horizontal:hover {{
                background-color: {theme.get("slider_handle_hover_bg", "#e2e8f0")};
            }}
        """)

    def get_value(self) -> int:
        return self.slider.value()

    def set_value(self, val: int):
        val = max(self.min_val, min(self.max_val, int(val)))
        self.slider.blockSignals(True)
        self.slider.setValue(val)
        self.slider.blockSignals(False)
        self.input_field.setText(f"+{val}" if val > 0 else str(val))

    def reset_value(self):
        SoundManager.play()
        self.set_value(self.default_val)
        self.value_changed.emit()

    def _on_slider_moved(self, int_val: int):
        self.input_field.setText(f"+{int_val}" if int_val > 0 else str(int_val))
        self.value_changed.emit()

    def _on_input_finished(self):
        txt = self.input_field.text().strip().replace("+", "")
        try:
            val = int(txt)
        except ValueError:
            val = self.default_val
        self.set_value(val)
        self.value_changed.emit()


class TimerSettingRow(QFrame):
    value_changed = pyqtSignal()

    def __init__(self, title: str = "Seconds", default_val: int = 3, parent=None):
        super().__init__(parent)
        self.default_val = default_val
        self.setObjectName("timerSettingRow")
        self.setFixedHeight(38)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)

        self.label = QLabel(title)
        self.input_field = QLineEdit(str(default_val))
        self.input_field.setFixedSize(54, 26)
        self.input_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        validator = QIntValidator(1, 999999, self)
        self.input_field.setValidator(validator)
        self.input_field.editingFinished.connect(self._on_input_finished)

        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.input_field)
        self.set_theme(DEFAULT_SETTINGS_BLACK)

    def set_theme(self, theme: dict | bool):
        if isinstance(theme, bool):
            theme = DEFAULT_SETTINGS_WHITE if theme else DEFAULT_SETTINGS_BLACK
        self.label.setStyleSheet(f"color: {theme.get('row_text', '#e1e1e6')}; font-size: 13px; font-weight: 500;")
        self.setStyleSheet(f"""
            QFrame#timerSettingRow {{
                background-color: {theme.get("card_bg", "#16161a")};
                border: 1px solid {theme.get("card_border", "#23232a")};
                border-radius: 7px;
            }}
            QFrame#timerSettingRow:hover {{
                border: 1px solid {theme.get("card_hover_border", "#32323d")};
            }}
        """)
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.get("input_bg", "#202026")};
                color: {theme.get("input_text", "#ffffff")};
                border: 1px solid {theme.get("input_border", "#2c2c36")};
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
            }}
            QLineEdit:focus {{
                border: 1px solid {theme.get("input_focus_border", "#3b82f6")};
            }}
        """)

    def get_value(self) -> int:
        txt = self.input_field.text().strip()
        try:
            return max(1, int(txt))
        except ValueError:
            return self.default_val

    def set_value(self, val: int):
        val = max(1, int(val))
        self.input_field.setText(str(val))

    def _on_input_finished(self):
        txt = self.input_field.text().strip()
        try:
            val = max(1, int(txt))
        except ValueError:
            val = self.default_val
        self.set_value(val)
        self.value_changed.emit()


class UpdateCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("updateCard")
        self.setFixedHeight(54)
        self.is_white = False
        self.theme_data = dict(DEFAULT_SETTINGS_BLACK)
        self._status_state = "ok"
        self.checker_thread = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(12)

        info_box = QVBoxLayout()
        info_box.setSpacing(2)
        info_box.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.version_lbl = QLabel(f"Current Version: {CURRENT_VERSION}")
        self.status_lbl = QLabel("You're updated to new update!")

        info_box.addWidget(self.version_lbl)
        info_box.addWidget(self.status_lbl)

        layout.addLayout(info_box)
        layout.addStretch()

        self.btn_check = QPushButton("Check for Updates")
        self.btn_check.setFixedHeight(28)
        self.btn_check.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check.clicked.connect(self.check_updates)
        layout.addWidget(self.btn_check)

        self.set_theme(DEFAULT_SETTINGS_BLACK)

    def _update_status_style(self):
        t = self.theme_data
        color_map = {
            "ok": t.get("update_status_ok", "#10b981"),
            "checking": t.get("update_status_checking", "#3b82f6"),
            "error": t.get("update_status_error", "#ef4444"),
            "warn": t.get("update_status_warn", "#eab308"),
        }
        col = color_map.get(self._status_state, "#10b981")
        self.status_lbl.setStyleSheet(f"color: {col}; font-size: 11px; font-weight: 600;")

    def set_theme(self, theme: dict | bool):
        if isinstance(theme, bool):
            self.is_white = theme
            self.theme_data = dict(DEFAULT_SETTINGS_WHITE if theme else DEFAULT_SETTINGS_BLACK)
        else:
            self.is_white = bool(theme.get("is_white", False))
            base = DEFAULT_SETTINGS_WHITE if self.is_white else DEFAULT_SETTINGS_BLACK
            merged = dict(base)
            merged.update(theme)
            self.theme_data = merged

        t = self.theme_data
        self.setStyleSheet(f"""
            QFrame#updateCard {{
                background-color: {t.get("card_bg", "#16161a")};
                border: 1px solid {t.get("card_border", "#23232a")};
                border-radius: 7px;
            }}
            QFrame#updateCard:hover {{
                border: 1px solid {t.get("card_hover_border", "#32323d")};
            }}
        """)
        self.version_lbl.setStyleSheet(f"color: {t.get('row_text', '#e1e1e6')}; font-size: 12px; font-weight: 600;")
        self.btn_check.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get("update_btn_bg", "#202026")};
                color: {t.get("update_btn_text", "#ffffff")};
                border: 1px solid {t.get("update_btn_border", "#2c2c36")};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background-color: {t.get("update_btn_hover_bg", "#2b2b34")};
                border: 1px solid {t.get("update_btn_hover_border", "#3b82f6")};
            }}
            QPushButton:disabled {{
                background-color: {t.get("update_btn_disabled_bg", "rgba(32, 32, 38, 0.5)")};
                color: {t.get("update_btn_disabled_text", "#636370")};
            }}
        """)
        self._update_status_style()

    def check_updates(self):
        SoundManager.play()
        self.btn_check.setEnabled(False)
        self.status_lbl.setText("Checking for updates...")
        self._status_state = "checking"
        self._update_status_style()

        self.checker_thread = UpdateCheckerThread(self)
        self.checker_thread.check_finished.connect(self._on_check_finished)
        self.checker_thread.start()

    def _on_check_finished(self, is_latest: bool, remote_ver: str):
        self.btn_check.setEnabled(True)
        if not remote_ver:
            self.status_lbl.setText("Failed to check updates")
            self._status_state = "error"
        elif is_latest:
            self.status_lbl.setText("You're updated to new update!")
            self._status_state = "ok"
        else:
            self.status_lbl.setText("Please, update to new version.")
            self._status_state = "warn"
        self._update_status_style()