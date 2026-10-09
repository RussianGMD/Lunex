import os
import winsound
import requests
from PyQt6.QtCore import (
    Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, 
    pyqtProperty, QPoint, QRectF, QUrl, QTimer, QSize, QThread
)
from PyQt6.QtGui import (
    QPainter, QColor, QDoubleValidator, QIntValidator, QIcon
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QAbstractButton, QSlider, QLineEdit, QGraphicsOpacityEffect, 
    QComboBox, QFrame, QScrollArea
)
from PyQt6.QtMultimedia import QSoundEffect

CURRENT_VERSION = "1.1"
UPDATE_URL = "https://raw.githubusercontent.com/RussianGMD/iuerfh/refs/heads/main/version.txt"


def find_sound_file() -> str | None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "sounds", "click.WAV"),
        os.path.join(base_dir, "sounds", "click.wav"),
        os.path.abspath("sounds/click.WAV"),
        os.path.abspath("sounds/click.wav"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


class ClickSound:
    sound_path = None
    effect = None
    muted = False

    @classmethod
    def init(cls):
        cls.sound_path = find_sound_file()
        if cls.sound_path:
            try:
                cls.effect = QSoundEffect()
                cls.effect.setSource(QUrl.fromLocalFile(cls.sound_path))
                cls.effect.setVolume(0.6)
            except Exception:
                cls.effect = None

    @classmethod
    def play(cls):
        if cls.muted or not cls.sound_path:
            return
        try:
            winsound.PlaySound(cls.sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            if cls.effect:
                try:
                    cls.effect.play()
                except Exception:
                    pass


def get_icon_path(base_name: str, is_white: bool = False) -> str:
    if is_white:
        white_path = f"icons/{base_name}_white.png"
        if os.path.exists(white_path):
            return white_path
    return f"icons/{base_name}.png"


class UpdateCheckerThread(QThread):
    check_finished = pyqtSignal(bool, str)  # is_latest, remote_version

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


class AnimatedToggle(QAbstractButton):
    def __init__(self, parent=None, width=38, height=20):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(width, height)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._bg_off = QColor("#222226")
        self._bg_on = QColor("#3b82f6")
        self._circle_color = QColor("#ffffff")

        self._padding = 2
        self._circle_radius = (height - self._padding * 2) / 2
        self._circle_x = float(self._padding)

        self._anim = QPropertyAnimation(self, b"circle_position", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self.toggled.connect(self._handle_state_change)

    def hitButton(self, pos: QPoint) -> bool:
        return self.rect().contains(pos)

    @pyqtProperty(float)
    def circle_position(self):
        return self._circle_x

    @circle_position.setter
    def circle_position(self, pos):
        self._circle_x = pos
        self.update()

    def set_theme(self, is_white: bool):
        self._bg_off = QColor("#d1d5db") if is_white else QColor("#222226")
        self.update()

    def setCheckedSilently(self, checked: bool):
        self.blockSignals(True)
        self.setChecked(checked)
        end = self.width() - self._circle_radius * 2 - self._padding if checked else self._padding
        self._circle_x = float(end)
        self.update()
        self.blockSignals(False)

    def _handle_state_change(self, checked):
        ClickSound.play()
        start = self._circle_x
        end = self.width() - self._circle_radius * 2 - self._padding if checked else self._padding
        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(float(end))
        self._anim.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_color = self._bg_on if self.isChecked() else self._bg_off
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg_color)
        p.drawRoundedRect(self.rect(), self.height() / 2, self.height() / 2)

        p.setBrush(self._circle_color)
        p.drawEllipse(
            QRectF(
                self._circle_x, 
                self._padding, 
                self._circle_radius * 2, 
                self._circle_radius * 2
            )
        )


class SwitchRow(QFrame):
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

        self.set_theme(False)

    def set_theme(self, is_white: bool):
        self.toggle.set_theme(is_white)
        if is_white:
            self.label.setStyleSheet("color: #18181b; font-size: 13px; font-weight: 500;")
            self.setStyleSheet("""
                QFrame#switchRow {
                    background-color: #ffffff;
                    border: 1px solid #e4e4e7;
                    border-radius: 7px;
                }
                QFrame#switchRow:hover {
                    border: 1px solid #cbd5e1;
                }
            """)
        else:
            self.label.setStyleSheet("color: #e1e1e6; font-size: 13px; font-weight: 500;")
            self.setStyleSheet("""
                QFrame#switchRow {
                    background-color: #16161a;
                    border: 1px solid #23232a;
                    border-radius: 7px;
                }
                QFrame#switchRow:hover {
                    border: 1px solid #32323d;
                }
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

        self.set_theme(False)

    def set_theme(self, is_white: bool):
        if is_white:
            self.label.setStyleSheet("color: #18181b; font-size: 13px; font-weight: 500;")
            self.setStyleSheet("""
                QFrame#comboRow {
                    background-color: #ffffff;
                    border: 1px solid #e4e4e7;
                    border-radius: 7px;
                }
                QFrame#comboRow:hover {
                    border: 1px solid #cbd5e1;
                }
            """)
            self.combo.setStyleSheet("""
                QComboBox {
                    background-color: #f4f4f7;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    padding-left: 10px;
                    padding-right: 10px;
                    font-size: 9pt;
                    font-weight: 500;
                }
                QComboBox:hover {
                    border: 1px solid #3b82f6;
                }
                QComboBox::drop-down { border: none; width: 0px; }
                QComboBox QAbstractItemView {
                    background-color: #ffffff;
                    color: #18181b;
                    selection-background-color: #e0e7ff;
                    selection-color: #1d4ed8;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    padding: 4px;
                    outline: none;
                }
            """)
        else:
            self.label.setStyleSheet("color: #e1e1e6; font-size: 13px; font-weight: 500;")
            self.setStyleSheet("""
                QFrame#comboRow {
                    background-color: #16161a;
                    border: 1px solid #23232a;
                    border-radius: 7px;
                }
                QFrame#comboRow:hover {
                    border: 1px solid #32323d;
                }
            """)
            self.combo.setStyleSheet("""
                QComboBox {
                    background-color: #202026;
                    color: #c9c9d4;
                    border: 1px solid #2c2c36;
                    border-radius: 5px;
                    padding-left: 10px;
                    padding-right: 10px;
                    font-size: 9pt;
                    font-weight: 500;
                }
                QComboBox:hover {
                    border: 1px solid #3b82f6;
                    color: #ffffff;
                }
                QComboBox::drop-down { border: none; width: 0px; }
                QComboBox QAbstractItemView {
                    background-color: #16161a;
                    color: #e1e1e6;
                    selection-background-color: #26334d;
                    selection-color: #60a5fa;
                    border: 1px solid #2c2c38;
                    border-radius: 5px;
                    padding: 4px;
                    outline: none;
                }
            """)

    def _on_index_changed(self):
        ClickSound.play()
        self.value_changed.emit()


class FailSettingCard(QFrame):
    value_changed = pyqtSignal()

    def __init__(self, title: str, default_val: float, parent=None):
        super().__init__(parent)
        self.default_val = default_val
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

        self.input_field = QLineEdit(f"{default_val:.1f}")
        self.input_field.setFixedSize(48, 24)
        self.input_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        validator = QDoubleValidator(1.0, 100.0, 1, self)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
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
        self.slider.setRange(10, 1000)
        self.slider.setValue(int(default_val * 10))
        self.slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider.valueChanged.connect(self._on_slider_moved)
        layout.addWidget(self.slider)

        self.set_theme(False)

    def set_theme(self, is_white: bool):
        icon_path = get_icon_path("converter", is_white)
        if os.path.exists(icon_path):
            self.reset_btn.setIcon(QIcon(icon_path))
            self.reset_btn.setIconSize(QSize(13, 13))
            self.reset_btn.setText("")
        else:
            self.reset_btn.setText("R")

        if is_white:
            self.setStyleSheet("""
                QFrame#failSettingCard {
                    background-color: #ffffff;
                    border: 1px solid #e4e4e7;
                    border-radius: 7px;
                }
                QFrame#failSettingCard:hover {
                    border: 1px solid #cbd5e1;
                }
            """)
            self.title_lbl.setStyleSheet("color: #18181b; font-size: 12px; font-weight: 600;")
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #f4f4f7;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QLineEdit:focus { border: 1px solid #3b82f6; }
            """)
            self.reset_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f4f4f7;
                    color: #52525b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #e4e4e7;
                    border: 1px solid #3b82f6;
                }
            """)
            self.slider.setStyleSheet("""
                QSlider { height: 20px; }
                QSlider::groove:horizontal {
                    height: 5px;
                    background-color: #e4e4e7;
                    border: 1px solid #d4d4d8;
                    border-radius: 2px;
                }
                QSlider::sub-page:horizontal { background-color: #3b82f6; border-radius: 2px; }
                QSlider::handle:horizontal {
                    background-color: #ffffff;
                    border: 1px solid #a1a1aa;
                    width: 12px; height: 12px; margin: -4px 0; border-radius: 6px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#failSettingCard {
                    background-color: #16161a;
                    border: 1px solid #23232a;
                    border-radius: 7px;
                }
                QFrame#failSettingCard:hover {
                    border: 1px solid #32323d;
                }
            """)
            self.title_lbl.setStyleSheet("color: #e1e1e6; font-size: 12px; font-weight: 600;")
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #202026;
                    color: #ffffff;
                    border: 1px solid #2c2c36;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QLineEdit:focus { border: 1px solid #3b82f6; }
            """)
            self.reset_btn.setStyleSheet("""
                QPushButton {
                    background-color: #202026;
                    color: #8f8f9d;
                    border: 1px solid #2c2c36;
                    border-radius: 5px;
                    font-size: 13px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2b2b34;
                    border: 1px solid #3b82f6;
                    color: #ffffff;
                }
            """)
            self.slider.setStyleSheet("""
                QSlider { height: 20px; }
                QSlider::groove:horizontal {
                    height: 5px;
                    background-color: #202026;
                    border: 1px solid #2c2c36;
                    border-radius: 2px;
                }
                QSlider::sub-page:horizontal { background-color: #3b82f6; border-radius: 2px; }
                QSlider::handle:horizontal {
                    background-color: #ffffff;
                    border: none;
                    width: 12px; height: 12px; margin: -4px 0; border-radius: 6px;
                }
                QSlider::handle:horizontal:hover { background-color: #e2e8f0; }
            """)

    def get_value(self) -> float:
        return self.slider.value() / 10.0

    def set_value(self, val: float):
        val = max(1.0, min(100.0, float(val)))
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(val * 10)))
        self.slider.blockSignals(False)
        self.input_field.setText(f"{val:.1f}")

    def reset_value(self):
        ClickSound.play()
        self.set_value(self.default_val)
        self.value_changed.emit()

    def _on_slider_moved(self, int_val: int):
        float_val = int_val / 10.0
        self.input_field.setText(f"{float_val:.1f}")
        self.value_changed.emit()

    def _on_input_finished(self):
        txt = self.input_field.text().replace(",", ".").strip()
        try:
            val = float(txt)
        except ValueError:
            val = self.default_val
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
        self.set_theme(False)

    def set_theme(self, is_white: bool):
        if is_white:
            self.label.setStyleSheet("color: #18181b; font-size: 13px; font-weight: 500;")
            self.setStyleSheet("""
                QFrame#speedLimitCard {
                    background-color: #ffffff;
                    border: 1px solid #e4e4e7;
                    border-radius: 7px;
                }
                QFrame#speedLimitCard:hover {
                    border: 1px solid #cbd5e1;
                }
            """)
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #f4f4f7;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QLineEdit:focus { border: 1px solid #3b82f6; }
            """)
        else:
            self.label.setStyleSheet("color: #e1e1e6; font-size: 13px; font-weight: 500;")
            self.setStyleSheet("""
                QFrame#speedLimitCard {
                    background-color: #16161a;
                    border: 1px solid #23232a;
                    border-radius: 7px;
                }
                QFrame#speedLimitCard:hover {
                    border: 1px solid #32323d;
                }
            """)
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #202026;
                    color: #ffffff;
                    border: 1px solid #2c2c36;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QLineEdit:focus { border: 1px solid #3b82f6; }
            """)

    def get_value(self) -> float:
        txt = self.input_field.text().lower().replace("x", "").replace("х", "").replace(",", ".").strip()
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
        self.set_theme(False)

    def set_theme(self, is_white: bool):
        if is_white:
            self.label.setStyleSheet("color: #18181b; font-size: 13px; font-weight: 500;")
            self.setStyleSheet("""
                QFrame#speedChanceCard {
                    background-color: #ffffff;
                    border: 1px solid #e4e4e7;
                    border-radius: 7px;
                }
                QFrame#speedChanceCard:hover {
                    border: 1px solid #cbd5e1;
                }
            """)
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #f4f4f7;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QLineEdit:focus { border: 1px solid #3b82f6; }
            """)
        else:
            self.label.setStyleSheet("color: #e1e1e6; font-size: 13px; font-weight: 500;")
            self.setStyleSheet("""
                QFrame#speedChanceCard {
                    background-color: #16161a;
                    border: 1px solid #23232a;
                    border-radius: 7px;
                }
                QFrame#speedChanceCard:hover {
                    border: 1px solid #32323d;
                }
            """)
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #202026;
                    color: #ffffff;
                    border: 1px solid #2c2c36;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QLineEdit:focus { border: 1px solid #3b82f6; }
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

        self.set_theme(False)

    def set_theme(self, is_white: bool):
        icon_path = get_icon_path("converter", is_white)
        if os.path.exists(icon_path):
            self.reset_btn.setIcon(QIcon(icon_path))
            self.reset_btn.setIconSize(QSize(13, 13))
            self.reset_btn.setText("")
        else:
            self.reset_btn.setText("R")

        if is_white:
            self.setStyleSheet("""
                QFrame#stepSettingCard {
                    background-color: #ffffff;
                    border: 1px solid #e4e4e7;
                    border-radius: 7px;
                }
                QFrame#stepSettingCard:hover {
                    border: 1px solid #cbd5e1;
                }
            """)
            self.title_lbl.setStyleSheet("color: #18181b; font-size: 12px; font-weight: 600;")
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #f4f4f7;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QLineEdit:focus { border: 1px solid #3b82f6; }
            """)
            self.reset_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f4f4f7;
                    color: #52525b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #e4e4e7;
                    border: 1px solid #3b82f6;
                }
            """)
            self.slider.setStyleSheet("""
                QSlider { height: 20px; }
                QSlider::groove:horizontal {
                    height: 5px;
                    background-color: #e4e4e7;
                    border: 1px solid #d4d4d8;
                    border-radius: 2px;
                }
                QSlider::sub-page:horizontal { background-color: #3b82f6; border-radius: 2px; }
                QSlider::handle:horizontal {
                    background-color: #ffffff;
                    border: 1px solid #a1a1aa;
                    width: 12px; height: 12px; margin: -4px 0; border-radius: 6px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#stepSettingCard {
                    background-color: #16161a;
                    border: 1px solid #23232a;
                    border-radius: 7px;
                }
                QFrame#stepSettingCard:hover {
                    border: 1px solid #32323d;
                }
            """)
            self.title_lbl.setStyleSheet("color: #e1e1e6; font-size: 12px; font-weight: 600;")
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #202026;
                    color: #ffffff;
                    border: 1px solid #2c2c36;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QLineEdit:focus { border: 1px solid #3b82f6; }
            """)
            self.reset_btn.setStyleSheet("""
                QPushButton {
                    background-color: #202026;
                    color: #8f8f9d;
                    border: 1px solid #2c2c36;
                    border-radius: 5px;
                    font-size: 13px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2b2b34;
                    border: 1px solid #3b82f6;
                    color: #ffffff;
                }
            """)
            self.slider.setStyleSheet("""
                QSlider { height: 20px; }
                QSlider::groove:horizontal {
                    height: 5px;
                    background-color: #202026;
                    border: 1px solid #2c2c36;
                    border-radius: 2px;
                }
                QSlider::sub-page:horizontal { background-color: #3b82f6; border-radius: 2px; }
                QSlider::handle:horizontal {
                    background-color: #ffffff;
                    border: none;
                    width: 12px; height: 12px; margin: -4px 0; border-radius: 6px;
                }
                QSlider::handle:horizontal:hover { background-color: #e2e8f0; }
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
        ClickSound.play()
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

        self.set_theme(False)

    def set_theme(self, is_white: bool):
        icon_path = get_icon_path("converter", is_white)
        if os.path.exists(icon_path):
            self.reset_btn.setIcon(QIcon(icon_path))
            self.reset_btn.setIconSize(QSize(13, 13))
            self.reset_btn.setText("")
        else:
            self.reset_btn.setText("R")

        if is_white:
            self.setStyleSheet("""
                QFrame#transposeMacroCard {
                    background-color: #ffffff;
                    border: 1px solid #e4e4e7;
                    border-radius: 7px;
                }
                QFrame#transposeMacroCard:hover {
                    border: 1px solid #cbd5e1;
                }
            """)
            self.title_lbl.setStyleSheet("color: #18181b; font-size: 12px; font-weight: 600;")
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #f4f4f7;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QLineEdit:focus { border: 1px solid #3b82f6; }
            """)
            self.reset_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f4f4f7;
                    color: #52525b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #e4e4e7;
                    border: 1px solid #3b82f6;
                }
            """)
            self.slider.setStyleSheet("""
                QSlider { height: 20px; }
                QSlider::groove:horizontal {
                    height: 5px;
                    background-color: #e4e4e7;
                    border: 1px solid #d4d4d8;
                    border-radius: 2px;
                }
                QSlider::sub-page:horizontal { background-color: #3b82f6; border-radius: 2px; }
                QSlider::handle:horizontal {
                    background-color: #ffffff;
                    border: 1px solid #a1a1aa;
                    width: 12px; height: 12px; margin: -4px 0; border-radius: 6px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#transposeMacroCard {
                    background-color: #16161a;
                    border: 1px solid #23232a;
                    border-radius: 7px;
                }
                QFrame#transposeMacroCard:hover {
                    border: 1px solid #32323d;
                }
            """)
            self.title_lbl.setStyleSheet("color: #e1e1e6; font-size: 12px; font-weight: 600;")
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #202026;
                    color: #ffffff;
                    border: 1px solid #2c2c36;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QLineEdit:focus { border: 1px solid #3b82f6; }
            """)
            self.reset_btn.setStyleSheet("""
                QPushButton {
                    background-color: #202026;
                    color: #8f8f9d;
                    border: 1px solid #2c2c36;
                    border-radius: 5px;
                    font-size: 13px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2b2b34;
                    border: 1px solid #3b82f6;
                    color: #ffffff;
                }
            """)
            self.slider.setStyleSheet("""
                QSlider { height: 20px; }
                QSlider::groove:horizontal {
                    height: 5px;
                    background-color: #202026;
                    border: 1px solid #2c2c36;
                    border-radius: 2px;
                }
                QSlider::sub-page:horizontal { background-color: #3b82f6; border-radius: 2px; }
                QSlider::handle:horizontal {
                    background-color: #ffffff;
                    border: none;
                    width: 12px; height: 12px; margin: -4px 0; border-radius: 6px;
                }
                QSlider::handle:horizontal:hover { background-color: #e2e8f0; }
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
        ClickSound.play()
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

        self.set_theme(False)

    def set_theme(self, is_white: bool):
        if is_white:
            self.label.setStyleSheet("color: #18181b; font-size: 13px; font-weight: 500;")
            self.setStyleSheet("""
                QFrame#timerSettingRow {
                    background-color: #ffffff;
                    border: 1px solid #e4e4e7;
                    border-radius: 7px;
                }
                QFrame#timerSettingRow:hover {
                    border: 1px solid #cbd5e1;
                }
            """)
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #f4f4f7;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QLineEdit:focus { border: 1px solid #3b82f6; }
            """)
        else:
            self.label.setStyleSheet("color: #e1e1e6; font-size: 13px; font-weight: 500;")
            self.setStyleSheet("""
                QFrame#timerSettingRow {
                    background-color: #16161a;
                    border: 1px solid #23232a;
                    border-radius: 7px;
                }
                QFrame#timerSettingRow:hover {
                    border: 1px solid #32323d;
                }
            """)
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #202026;
                    color: #ffffff;
                    border: 1px solid #2c2c36;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QLineEdit:focus { border: 1px solid #3b82f6; }
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

        self.checker_thread = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(12)

        info_box = QVBoxLayout()
        info_box.setSpacing(2)
        info_box.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.version_lbl = QLabel(f"Current Version: {CURRENT_VERSION}")
        self.status_lbl = QLabel("You're updated to new update!")
        self.status_lbl.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 600;")

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
        self.set_theme(False)

    def set_theme(self, is_white: bool):
        self.is_white = is_white
        if is_white:
            self.setStyleSheet("""
                QFrame#updateCard {
                    background-color: #ffffff;
                    border: 1px solid #e4e4e7;
                    border-radius: 7px;
                }
                QFrame#updateCard:hover {
                    border: 1px solid #cbd5e1;
                }
            """)
            self.version_lbl.setStyleSheet("color: #18181b; font-size: 12px; font-weight: 600;")
            self.btn_check.setStyleSheet("""
                QPushButton {
                    background-color: #f4f4f7;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0 14px;
                }
                QPushButton:hover {
                    background-color: #e4e4e7;
                    border: 1px solid #3b82f6;
                }
                QPushButton:disabled {
                    background-color: rgba(244, 244, 247, 0.5);
                    color: #a1a1aa;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#updateCard {
                    background-color: #16161a;
                    border: 1px solid #23232a;
                    border-radius: 7px;
                }
                QFrame#updateCard:hover {
                    border: 1px solid #32323d;
                }
            """)
            self.version_lbl.setStyleSheet("color: #e1e1e6; font-size: 12px; font-weight: 600;")
            self.btn_check.setStyleSheet("""
                QPushButton {
                    background-color: #202026;
                    color: #ffffff;
                    border: 1px solid #2c2c36;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0 14px;
                }
                QPushButton:hover {
                    background-color: #2b2b34;
                    border: 1px solid #3b82f6;
                }
                QPushButton:disabled {
                    background-color: rgba(32, 32, 38, 0.5);
                    color: #636370;
                }
            """)

    def check_updates(self):
        ClickSound.play()
        self.btn_check.setEnabled(False)
        self.status_lbl.setText("Checking for updates...")
        self.status_lbl.setStyleSheet("color: #3b82f6; font-size: 11px; font-weight: 600;")

        self.checker_thread = UpdateCheckerThread(self)
        self.checker_thread.check_finished.connect(self._on_check_finished)
        self.checker_thread.start()

    def _on_check_finished(self, is_latest: bool, remote_ver: str):
        self.btn_check.setEnabled(True)
        if not remote_ver:
            self.status_lbl.setText("Failed to check updates")
            self.status_lbl.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: 600;")
        elif is_latest:
            self.status_lbl.setText("You're updated to new update!")
            self.status_lbl.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 600;")
        else:
            self.status_lbl.setText("Please, update to new version.")
            self.status_lbl.setStyleSheet("color: #eab308; font-size: 11px; font-weight: 600;")


class SettingsView(QWidget):
    state_changed = pyqtSignal()
    reset_recents_requested = pyqtSignal()
    open_debug_console_requested = pyqtSignal()
    close_debug_console_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        ClickSound.init()
        self.is_white = False
        self._setup_ui()

    def _setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.content_widget = QWidget()
        root_layout = QVBoxLayout(self.content_widget)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(10)

        # 1. MIDI PLAYER SETTINGS
        self.cat_player_header = QLabel("MIDI PLAYER SETTINGS")
        self.cat_player_header.setStyleSheet("color: #7b7b8a; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        root_layout.addWidget(self.cat_player_header)

        self.toggle_human_fail = SwitchRow("Human Fail")
        self.toggle_human_fail.toggle.toggled.connect(self._on_toggle_human_fail)
        root_layout.addWidget(self.toggle_human_fail)

        self.fails_container = QWidget()
        fails_layout = QVBoxLayout(self.fails_container)
        fails_layout.setContentsMargins(0, 0, 0, 0)
        fails_layout.setSpacing(8)

        
        top_fails_row = QHBoxLayout()
        top_fails_row.setContentsMargins(0, 0, 0, 0)
        top_fails_row.setSpacing(10)

        self.speed_fail_card = FailSettingCard("Speed Fail %", default_val=1.0)
        self.speed_fail_card.value_changed.connect(lambda: self.state_changed.emit())
        self.transpose_fail_card = FailSettingCard("Transpose Fail %", default_val=5.0)
        self.transpose_fail_card.value_changed.connect(lambda: self.state_changed.emit())

        top_fails_row.addWidget(self.speed_fail_card)
        top_fails_row.addWidget(self.transpose_fail_card)
        fails_layout.addLayout(top_fails_row)

        
        speed_limits_row = QHBoxLayout()
        speed_limits_row.setContentsMargins(0, 0, 0, 0)
        speed_limits_row.setSpacing(10)

        self.slow_speed_card = SpeedLimitCard("Slow Speed", default_val=0.8, is_slow=True)
        self.slow_speed_card.value_changed.connect(lambda: self.state_changed.emit())

        self.fast_speed_card = SpeedLimitCard("Fast Speed", default_val=1.2, is_slow=False)
        self.fast_speed_card.value_changed.connect(lambda: self.state_changed.emit())

        speed_limits_row.addWidget(self.slow_speed_card)
        speed_limits_row.addWidget(self.fast_speed_card)
        fails_layout.addLayout(speed_limits_row)

        
        speed_chances_row = QHBoxLayout()
        speed_chances_row.setContentsMargins(0, 0, 0, 0)
        speed_chances_row.setSpacing(10)

        self.slow_chance_card = SpeedChanceCard("Slow Chance %", default_val=50.0)
        self.slow_chance_card.value_changed.connect(lambda: self.state_changed.emit())

        self.fast_chance_card = SpeedChanceCard("Fast Chance %", default_val=50.0)
        self.fast_chance_card.value_changed.connect(lambda: self.state_changed.emit())

        speed_chances_row.addWidget(self.slow_chance_card)
        speed_chances_row.addWidget(self.fast_chance_card)
        fails_layout.addLayout(speed_chances_row)

        self.opacity_effect = QGraphicsOpacityEffect(self.fails_container)
        self.fails_container.setGraphicsEffect(self.opacity_effect)
        root_layout.addWidget(self.fails_container)

        # Timer Start и строка с секундами
        self.toggle_timer_start = SwitchRow("Timer Start")
        self.toggle_timer_start.toggle.toggled.connect(self._on_toggle_timer_start)
        root_layout.addWidget(self.toggle_timer_start)

        self.timer_seconds_row = TimerSettingRow("Seconds", default_val=3)
        self.timer_seconds_row.value_changed.connect(lambda: self.state_changed.emit())
        root_layout.addWidget(self.timer_seconds_row)
        self.timer_seconds_row.setVisible(False)

        # Loop Song и Console
        toggles_row = QHBoxLayout()
        toggles_row.setContentsMargins(0, 0, 0, 0)
        toggles_row.setSpacing(10)

        self.toggle_loop_song = SwitchRow("Loop Song")
        self.toggle_loop_song.toggle.toggled.connect(lambda: self.state_changed.emit())

        self.toggle_console = SwitchRow("Console")
        self.toggle_console.toggle.toggled.connect(lambda: self.state_changed.emit())

        toggles_row.addWidget(self.toggle_loop_song)
        toggles_row.addWidget(self.toggle_console)
        root_layout.addLayout(toggles_row)

        # Sliders row
        sliders_row = QHBoxLayout()
        sliders_row.setContentsMargins(0, 0, 0, 0)
        sliders_row.setSpacing(10)

        self.speed_step_card = StepSettingCard("Speed Hotkey Decrease Size", default_val=5, min_val=1, max_val=100)
        self.speed_step_card.value_changed.connect(lambda: self.state_changed.emit())

        self.macro_transpose_card = TransposeSettingCard("Transposition Macro", default_val=0, min_val=-24, max_val=24)
        self.macro_transpose_card.value_changed.connect(lambda: self.state_changed.emit())

        sliders_row.addWidget(self.speed_step_card)
        sliders_row.addWidget(self.macro_transpose_card)
        root_layout.addLayout(sliders_row)

        self.btn_reset_recents = QPushButton("Reset Recents MIDI Files")
        self.btn_reset_recents.setFixedHeight(32)
        self.btn_reset_recents.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_reset_recents.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_recents.clicked.connect(self._on_reset_recents_clicked)
        root_layout.addWidget(self.btn_reset_recents)

        # 2. DEBUG CONSOLE
        self.cat_debug_header = QLabel("DEBUG CONSOLE")
        self.cat_debug_header.setStyleSheet("color: #7b7b8a; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; margin-top: 4px;")
        root_layout.addWidget(self.cat_debug_header)

        debug_btn_layout = QHBoxLayout()
        debug_btn_layout.setContentsMargins(0, 0, 0, 0)
        debug_btn_layout.setSpacing(10)

        self.btn_open_debug = QPushButton("Open Debug Console")
        self.btn_open_debug.setFixedHeight(32)
        self.btn_open_debug.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_open_debug.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_debug.clicked.connect(self._on_open_debug_clicked)

        self.btn_close_debug = QPushButton("Close Debug Console")
        self.btn_close_debug.setFixedHeight(32)
        self.btn_close_debug.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_close_debug.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close_debug.clicked.connect(self._on_close_debug_clicked)

        debug_btn_layout.addWidget(self.btn_open_debug)
        debug_btn_layout.addWidget(self.btn_close_debug)
        root_layout.addLayout(debug_btn_layout)

        # 3. APP THEME
        self.cat_theme_header = QLabel("APP THEME")
        self.cat_theme_header.setStyleSheet("color: #7b7b8a; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; margin-top: 4px;")
        root_layout.addWidget(self.cat_theme_header)

        self.theme_row = ComboRow("Theme", ["Black (Standart)", "White"])
        self.theme_row.value_changed.connect(lambda: self.state_changed.emit())
        root_layout.addWidget(self.theme_row)

        # 4. APP UPDATE
        self.cat_update_header = QLabel("APP UPDATE")
        self.cat_update_header.setStyleSheet("color: #7b7b8a; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; margin-top: 4px;")
        root_layout.addWidget(self.cat_update_header)

        self.update_card = UpdateCard()
        root_layout.addWidget(self.update_card)

        root_layout.addStretch()

        self.scroll.setWidget(self.content_widget)
        outer_layout.addWidget(self.scroll)

        self._update_fails_availability(False)
        self._apply_reset_btn_style(is_success=False)

    def set_theme(self, is_white: bool):
        self.is_white = is_white
        color_header = "#71717a" if is_white else "#7b7b8a"

        self.cat_player_header.setStyleSheet(f"color: {color_header}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        self.cat_debug_header.setStyleSheet(f"color: {color_header}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; margin-top: 4px;")
        self.cat_theme_header.setStyleSheet(f"color: {color_header}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; margin-top: 4px;")
        self.cat_update_header.setStyleSheet(f"color: {color_header}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; margin-top: 4px;")

        self.toggle_human_fail.set_theme(is_white)
        self.speed_fail_card.set_theme(is_white)
        self.transpose_fail_card.set_theme(is_white)
        self.slow_speed_card.set_theme(is_white)
        self.fast_speed_card.set_theme(is_white)
        self.slow_chance_card.set_theme(is_white)
        self.fast_chance_card.set_theme(is_white)
        self.toggle_timer_start.set_theme(is_white)
        self.timer_seconds_row.set_theme(is_white)
        self.toggle_loop_song.set_theme(is_white)
        self.speed_step_card.set_theme(is_white)
        self.macro_transpose_card.set_theme(is_white)
        self.toggle_console.set_theme(is_white)
        self.theme_row.set_theme(is_white)
        self.update_card.set_theme(is_white)
        self._apply_reset_btn_style(is_success=False)

        if is_white:
            self.content_widget.setStyleSheet("background: transparent;")
            self.scroll.setStyleSheet("""
                QScrollArea { border: none; background: transparent; }
                QScrollBar:vertical {
                    border: none;
                    background: #f4f4f7;
                    width: 6px;
                    border-radius: 3px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background: #d4d4d8;
                    min-height: 25px;
                    border-radius: 3px;
                }
                QScrollBar::handle:vertical:hover { background: #3b82f6; }
                QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { border: none; background: none; height: 0px; }
                QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical { background: none; }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
            """)
            btn_debug_style = """
                QPushButton {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 0 14px;
                }
                QPushButton:hover {
                    background-color: #f4f4f7;
                    border: 1px solid #3b82f6;
                }
                QPushButton:pressed {
                    background-color: #e4e4e7;
                }
            """
        else:
            self.content_widget.setStyleSheet("background: transparent;")
            self.scroll.setStyleSheet("""
                QScrollArea { border: none; background: transparent; }
                QScrollBar:vertical {
                    border: none;
                    background: #101014;
                    width: 6px;
                    border-radius: 3px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background: #23232c;
                    min-height: 25px;
                    border-radius: 3px;
                }
                QScrollBar::handle:vertical:hover { background: #3b82f6; }
                QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { border: none; background: none; height: 0px; }
                QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical { background: none; }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
            """)
            btn_debug_style = """
                QPushButton {
                    background-color: #16161a;
                    color: #e1e1e6;
                    border: 1px solid #23232a;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 0 14px;
                }
                QPushButton:hover {
                    background-color: #202026;
                    border: 1px solid #3b82f6;
                    color: #ffffff;
                }
                QPushButton:pressed {
                    background-color: #121216;
                }
            """
        self.btn_open_debug.setStyleSheet(btn_debug_style)
        self.btn_close_debug.setStyleSheet(btn_debug_style)

    def _apply_reset_btn_style(self, is_success: bool = False):
        if is_success:
            self.btn_reset_recents.setStyleSheet("""
                QPushButton {
                    background-color: #12241b;
                    color: #10b981;
                    border: 1px solid #059669;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 0 16px;
                }
            """)
        else:
            if self.is_white:
                self.btn_reset_recents.setStyleSheet("""
                    QPushButton {
                        background-color: #ffffff;
                        color: #18181b;
                        border: 1px solid #e4e4e7;
                        border-radius: 6px;
                        font-size: 12px;
                        font-weight: 600;
                        padding: 0 16px;
                    }
                    QPushButton:hover {
                        background-color: #fee2e2;
                        border: 1px solid #ef4444;
                        color: #ef4444;
                    }
                    QPushButton:pressed {
                        background-color: #fecaca;
                    }
                """)
            else:
                self.btn_reset_recents.setStyleSheet("""
                    QPushButton {
                        background-color: #16161a;
                        color: #e1e1e6;
                        border: 1px solid #23232a;
                        border-radius: 6px;
                        font-size: 12px;
                        font-weight: 600;
                        padding: 0 16px;
                    }
                    QPushButton:hover {
                        background-color: #202026;
                        border: 1px solid #ef4444;
                        color: #ef4444;
                    }
                    QPushButton:pressed {
                        background-color: #121216;
                    }
                """)

    def _on_open_debug_clicked(self):
        ClickSound.play()
        self.open_debug_console_requested.emit()

    def _on_close_debug_clicked(self):
        ClickSound.play()
        self.close_debug_console_requested.emit()

    def _on_reset_recents_clicked(self):
        ClickSound.play()
        self.reset_recents_requested.emit()
        self.btn_reset_recents.setText("Recents Cleared!")
        self._apply_reset_btn_style(is_success=True)
        QTimer.singleShot(1500, self._restore_reset_btn)

    def _restore_reset_btn(self):
        self.btn_reset_recents.setText("Reset Recents MIDI Files")
        self._apply_reset_btn_style(is_success=False)

    def _on_toggle_human_fail(self, checked: bool):
        self._update_fails_availability(checked)
        self.state_changed.emit()

    def _on_toggle_timer_start(self, checked: bool):
        self.timer_seconds_row.setVisible(checked)
        self.state_changed.emit()

    def _update_fails_availability(self, enabled: bool):
        self.fails_container.setEnabled(enabled)
        self.opacity_effect.setOpacity(1.0 if enabled else 0.35)

    def get_speed_hotkey_step(self) -> int:
        return self.speed_step_card.get_value()

    def get_macro_transposition(self) -> int:
        return self.macro_transpose_card.get_value()

    def is_console_enabled(self) -> bool:
        return self.toggle_console.toggle.isChecked()

    def is_timer_start_enabled(self) -> bool:
        return self.toggle_timer_start.toggle.isChecked()

    def get_timer_seconds(self) -> int:
        return self.timer_seconds_row.get_value()

    def get_speed_fail_min(self) -> float:
        return self.slow_speed_card.get_value()

    def get_speed_fail_max(self) -> float:
        return self.fast_speed_card.get_value()

    def get_speed_fail_slow_pct(self) -> float:
        return self.slow_chance_card.get_value()

    def get_speed_fail_fast_pct(self) -> float:
        return self.fast_chance_card.get_value()

    def get_theme(self) -> str:
        return self.theme_row.combo.currentText()

    def get_save_data(self) -> dict:
        return {
            "human_fail": self.toggle_human_fail.toggle.isChecked(),
            "speed_fail_pct": self.speed_fail_card.get_value(),
            "transpose_fail_pct": self.transpose_fail_card.get_value(),
            "speed_fail_min": self.slow_speed_card.get_value(),
            "speed_fail_max": self.fast_speed_card.get_value(),
            "speed_fail_slow_pct": self.slow_chance_card.get_value(),
            "speed_fail_fast_pct": self.fast_chance_card.get_value(),
            "timer_start": self.toggle_timer_start.toggle.isChecked(),
            "timer_seconds": self.timer_seconds_row.get_value(),
            "loop_song": self.toggle_loop_song.toggle.isChecked(),
            "speed_hotkey_step": self.speed_step_card.get_value(),
            "macro_transposition": self.macro_transpose_card.get_value(),
            "console": self.toggle_console.toggle.isChecked(),
            "app_theme": self.theme_row.combo.currentText()
        }

    def load_save_data(self, data: dict):
        if not isinstance(data, dict):
            return

        is_hf = data.get("human_fail", False)
        self.toggle_human_fail.toggle.setCheckedSilently(is_hf)
        self._update_fails_availability(is_hf)
        self.speed_fail_card.set_value(data.get("speed_fail_pct", 1.0))
        self.transpose_fail_card.set_value(data.get("transpose_fail_pct", 5.0))
        self.slow_speed_card.set_value(data.get("speed_fail_min", 0.8))
        self.fast_speed_card.set_value(data.get("speed_fail_max", 1.2))
        self.slow_chance_card.set_value(data.get("speed_fail_slow_pct", 50.0))
        self.fast_chance_card.set_value(data.get("speed_fail_fast_pct", 50.0))

        is_timer = data.get("timer_start", False)
        self.toggle_timer_start.toggle.setCheckedSilently(is_timer)
        self.timer_seconds_row.setVisible(is_timer)
        self.timer_seconds_row.set_value(data.get("timer_seconds", 3))

        is_loop = data.get("loop_song", False)
        self.toggle_loop_song.toggle.setCheckedSilently(is_loop)

        step_val = data.get("speed_hotkey_step", 5)
        self.speed_step_card.set_value(step_val)

        macro_trans = data.get("macro_transposition", 0)
        self.macro_transpose_card.set_value(macro_trans)

        is_console = data.get("console", False)
        self.toggle_console.toggle.setCheckedSilently(is_console)

        saved_theme = data.get("app_theme", "Black (Standart)")
        idx = self.theme_row.combo.findText(saved_theme)
        if idx >= 0:
            self.theme_row.combo.blockSignals(True)
            self.theme_row.combo.setCurrentIndex(idx)
            self.theme_row.combo.blockSignals(False)