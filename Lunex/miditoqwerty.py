import os
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, pyqtProperty, QPoint, QRectF, QUrl
from PyQt6.QtGui import QPainter, QColor, QIntValidator
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, 
    QAbstractButton, QFileDialog, QProgressBar, QComboBox, 
    QPlainTextEdit, QApplication, QSlider, QLineEdit
)
from PyQt6.QtMultimedia import QSoundEffect

from load_midi import MidiLoader
from drag import MidiDropCard
from convert import convert_midi_to_qwerty


def format_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}"


class ClickSound:
    effect = None

    @classmethod
    def init(cls):
        path = os.path.abspath("sounds/click.wav")
        if os.path.exists(path):
            cls.effect = QSoundEffect()
            cls.effect.setSource(QUrl.fromLocalFile(path))
            cls.effect.setVolume(0.6)

    @classmethod
    def play(cls):
        if cls.effect:
            cls.effect.play()


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


class SwitchRow(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 7)

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
                SwitchRow {
                    background-color: #ffffff;
                    border: 1px solid #e4e4e7;
                    border-radius: 6px;
                }
                SwitchRow:hover {
                    border: 1px solid #cbd5e1;
                }
            """)
        else:
            self.label.setStyleSheet("color: #e1e1e6; font-size: 13px; font-weight: 500;")
            self.setStyleSheet("""
                SwitchRow {
                    background-color: #16161a;
                    border: 1px solid #23232a;
                    border-radius: 6px;
                }
                SwitchRow:hover {
                    border: 1px solid #32323d;
                }
            """)


class MidiToQwertyView(QWidget):
    state_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        ClickSound.init()

        self.current_midi_data = None
        self.recent_midis = []
        self.converted_text = ""
        self.is_white = False

        self._setup_ui()

    def _setup_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(18)

        # Left Panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        self.midi_header = QLabel("MIDI")
        left_layout.addWidget(self.midi_header)

        self.midi_card = MidiDropCard()
        self.midi_card.file_dropped.connect(self._on_midi_dropped)

        card_layout = QVBoxLayout(self.midi_card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)

        self.select_btn = QPushButton("Select File")
        self.select_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_btn.setFixedHeight(30)
        self.select_btn.clicked.connect(self._select_file)
        card_layout.addWidget(self.select_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        path_box = QVBoxLayout()
        path_box.setSpacing(3)

        self.path_title = QLabel("PATH")
        path_box.addWidget(self.path_title)

        self.path_label = QLabel("No file selected")
        self.path_label.setWordWrap(True)
        path_box.addWidget(self.path_label)
        card_layout.addLayout(path_box)

        recent_box = QVBoxLayout()
        recent_box.setSpacing(4)

        self.recent_title = QLabel("RECENT FILES")
        recent_box.addWidget(self.recent_title)

        self.recent_combo = QComboBox()
        self.recent_combo.setFixedHeight(28)
        self.recent_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.recent_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.recent_combo.currentIndexChanged.connect(self._on_recent_selected)
        recent_box.addWidget(self.recent_combo)

        card_layout.addLayout(recent_box)
        left_layout.addWidget(self.midi_card)

        self.sheet_header = QLabel("CONVERTED SHEET")
        left_layout.addWidget(self.sheet_header)

        self.sheet_output = QPlainTextEdit()
        self.sheet_output.setReadOnly(True)
        self.sheet_output.setPlaceholderText("Converted QWERTY notes will appear here...")
        left_layout.addWidget(self.sheet_output, stretch=1)

        sheet_actions = QHBoxLayout()
        sheet_actions.setSpacing(8)

        self.btn_copy = QPushButton("Copy Sheet")
        self.btn_copy.setFixedHeight(28)
        self.btn_copy.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.clicked.connect(self._copy_sheet)

        self.btn_save_txt = QPushButton("Save to .txt")
        self.btn_save_txt.setFixedHeight(28)
        self.btn_save_txt.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_save_txt.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_txt.clicked.connect(self._save_to_txt)

        sheet_actions.addWidget(self.btn_copy)
        sheet_actions.addWidget(self.btn_save_txt)
        sheet_actions.addStretch()

        left_layout.addLayout(sheet_actions)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #ef4444; font-size: 12px; font-weight: 600;")
        left_layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignLeft)

        root_layout.addWidget(left_panel, stretch=3)

        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.settings_header = QLabel("CONVERT SETTINGS")
        right_layout.addWidget(self.settings_header)

        
        self.toggle_88_keys = SwitchRow("88 Keys")
        self.toggle_88_keys.toggle.toggled.connect(lambda: self.state_changed.emit())
        right_layout.addWidget(self.toggle_88_keys)

        
        self.toggle_temp = SwitchRow("Temp")
        self.toggle_temp.toggle.toggled.connect(lambda: self.state_changed.emit())
        right_layout.addWidget(self.toggle_temp)

        right_layout.addStretch()

        
        transpose_box = QVBoxLayout()
        transpose_box.setSpacing(4)

        self.transpose_title = QLabel("TRANSPOSE")
        transpose_box.addWidget(self.transpose_title)

        transpose_row = QHBoxLayout()
        transpose_row.setSpacing(8)

        self.transpose_input = QLineEdit("0")
        self.transpose_input.setFixedSize(48, 26)
        self.transpose_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.transpose_input.setValidator(QIntValidator(-24, 24, self))

        self.transpose_slider = QSlider(Qt.Orientation.Horizontal)
        self.transpose_slider.setRange(-24, 24)
        self.transpose_slider.setValue(0)
        self.transpose_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.transpose_slider.setCursor(Qt.CursorShape.PointingHandCursor)

        self.transpose_slider.valueChanged.connect(self._on_transpose_slider_changed)
        self.transpose_input.editingFinished.connect(self._on_transpose_input_changed)

        transpose_row.addWidget(self.transpose_input)
        transpose_row.addWidget(self.transpose_slider)
        transpose_box.addLayout(transpose_row)

        right_layout.addLayout(transpose_box)

        # Progress / Info section
        progress_box = QVBoxLayout()
        progress_box.setSpacing(4)

        time_row = QHBoxLayout()
        time_row.setContentsMargins(0, 0, 0, 0)

        self.time_title = QLabel("PROGRESS")
        self.time_label = QLabel("0:00:00 / 0:00:00")

        time_row.addWidget(self.time_title)
        time_row.addStretch()
        time_row.addWidget(self.time_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(5)

        progress_box.addLayout(time_row)
        progress_box.addWidget(self.progress_bar)
        right_layout.addLayout(progress_box)

        # Button of Convert
        self.btn_convert = QPushButton("Convert")
        self.btn_convert.setFixedHeight(32)
        self.btn_convert.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_convert.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_convert.clicked.connect(self._on_convert_clicked)
        self.btn_convert.setEnabled(False)

        right_layout.addWidget(self.btn_convert)
        root_layout.addWidget(right_panel, stretch=2)

        self.set_theme(False)

    def set_theme(self, is_white: bool):
        self.is_white = is_white
        color_header = "#71717a" if is_white else "#7b7b8a"

        self.midi_header.setStyleSheet(f"color: {color_header}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        self.path_title.setStyleSheet("color: #636370; font-size: 10px; font-weight: bold;")
        self.recent_title.setStyleSheet("color: #636370; font-size: 10px; font-weight: bold;")
        self.sheet_header.setStyleSheet(f"color: {color_header}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        self.settings_header.setStyleSheet(f"color: {color_header}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; margin-bottom: 2px;")
        self.transpose_title.setStyleSheet(f"color: {color_header}; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
        self.time_title.setStyleSheet(f"color: {color_header}; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")

        time_val_color = "#71717a" if is_white else "#8f8f9d"
        self.time_label.setStyleSheet(f"color: {time_val_color}; font-size: 11px; font-weight: 600;")

        if not self.current_midi_data:
            path_col = "#71717a" if is_white else "#9d9da8"
            self.path_label.setStyleSheet(f"color: {path_col}; font-size: 12px;")
        else:
            self.path_label.setStyleSheet("color: #3b82f6; font-size: 12px; font-weight: 500;")

        if hasattr(self.midi_card, "set_theme"):
            self.midi_card.set_theme(is_white)

        self.toggle_88_keys.set_theme(is_white)
        self.toggle_temp.set_theme(is_white)

        if is_white:
            self.select_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 500;
                    padding: 0 14px;
                }
                QPushButton:hover { background-color: #f4f4f7; border: 1px solid #a1a1aa; }
                QPushButton:pressed { background-color: #e4e4e7; }
            """)
            self.recent_combo.setStyleSheet("""
                QComboBox {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    padding-left: 10px;
                    padding-right: 10px;
                    font-size: 11px;
                    font-weight: 500;
                }
                QComboBox:hover { border: 1px solid #3b82f6; }
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
            self.sheet_output.setStyleSheet("""
                QPlainTextEdit {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #e4e4e7;
                    border-radius: 7px;
                    padding: 10px;
                    font-family: 'Consolas', 'Segoe UI', monospace;
                    font-size: 12px;
                }
                QPlainTextEdit:focus { border: 1px solid #3b82f6; }
            """)
            btn_sheet_style = """
                QPushButton {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0 14px;
                }
                QPushButton:hover { background-color: #f4f4f7; border: 1px solid #3b82f6; }
            """
            self.btn_copy.setStyleSheet(btn_sheet_style)
            self.btn_save_txt.setStyleSheet(btn_sheet_style)

            self.transpose_input.setStyleSheet("""
                QLineEdit {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QLineEdit:focus { border: 1px solid #3b82f6; }
            """)
            self.transpose_slider.setStyleSheet("""
                QSlider { height: 26px; }
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
                    width: 12px; height: 12px; margin: -3px 0; border-radius: 6px;
                }
                QSlider::handle:horizontal:hover { background-color: #f4f4f7; }
            """)
            self.progress_bar.setStyleSheet("""
                QProgressBar { background-color: #e4e4e7; border: 1px solid #d4d4d8; border-radius: 2px; }
                QProgressBar::chunk { background-color: #3b82f6; border-radius: 2px; }
            """)
            self.btn_convert.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover { background-color: #f4f4f7; border: 1px solid #3b82f6; }
                QPushButton:pressed { background-color: #e4e4e7; }
                QPushButton:disabled {
                    background-color: rgba(228, 228, 231, 0.4);
                    color: rgba(24, 24, 27, 0.25);
                    border: 1px solid rgba(212, 212, 216, 0.4);
                }
            """)
        else:
            self.select_btn.setStyleSheet("""
                QPushButton {
                    background-color: #202026;
                    color: #ffffff;
                    border: 1px solid #2c2c36;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 500;
                    padding: 0 14px;
                }
                QPushButton:hover { background-color: #2b2b34; border: 1px solid #3d3d4a; }
                QPushButton:pressed { background-color: #1a1a20; }
            """)
            self.recent_combo.setStyleSheet("""
                QComboBox {
                    background-color: #1a1a20;
                    color: #c9c9d4;
                    border: 1px solid #282832;
                    border-radius: 5px;
                    padding-left: 10px;
                    padding-right: 10px;
                    font-size: 11px;
                    font-weight: 500;
                }
                QComboBox:hover { border: 1px solid #3b82f6; color: #ffffff; }
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
            self.sheet_output.setStyleSheet("""
                QPlainTextEdit {
                    background-color: #16161a;
                    color: #e1e1e6;
                    border: 1px solid #23232a;
                    border-radius: 7px;
                    padding: 10px;
                    font-family: 'Consolas', 'Segoe UI', monospace;
                    font-size: 12px;
                }
                QPlainTextEdit:focus { border: 1px solid #3b82f6; }
            """)
            btn_sheet_style = """
                QPushButton {
                    background-color: #16161a;
                    color: #ffffff;
                    border: 1px solid #23232a;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0 14px;
                }
                QPushButton:hover { background-color: #202026; border: 1px solid #3b82f6; }
            """
            self.btn_copy.setStyleSheet(btn_sheet_style)
            self.btn_save_txt.setStyleSheet(btn_sheet_style)

            self.transpose_input.setStyleSheet("""
                QLineEdit {
                    background-color: #16161a;
                    color: #ffffff;
                    border: 1px solid #23232a;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QLineEdit:focus { border: 1px solid #3b82f6; }
            """)
            self.transpose_slider.setStyleSheet("""
                QSlider { height: 26px; }
                QSlider::groove:horizontal {
                    height: 5px;
                    background-color: #16161a;
                    border: 1px solid #23232a;
                    border-radius: 2px;
                }
                QSlider::sub-page:horizontal { background-color: #3b82f6; border-radius: 2px; }
                QSlider::handle:horizontal {
                    background-color: #ffffff;
                    border: none;
                    width: 12px; height: 12px; margin: -3px 0; border-radius: 6px;
                }
                QSlider::handle:horizontal:hover { background-color: #e2e8f0; }
            """)
            self.progress_bar.setStyleSheet("""
                QProgressBar { background-color: #16161a; border: 1px solid #23232a; border-radius: 2px; }
                QProgressBar::chunk { background-color: #3b82f6; border-radius: 2px; }
            """)
            self.btn_convert.setStyleSheet("""
                QPushButton {
                    background-color: #16161a;
                    color: #ffffff;
                    border: 1px solid #23232a;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover { background-color: #202026; border: 1px solid #3b82f6; }
                QPushButton:pressed { background-color: #121216; }
                QPushButton:disabled {
                    background-color: rgba(22, 22, 26, 0.25);
                    color: rgba(255, 255, 255, 0.2);
                    border: 1px solid rgba(35, 35, 42, 0.25);
                }
            """)

    def _set_transpose_value(self, val: int):
        val = max(-24, min(24, int(val)))
        self.transpose_slider.blockSignals(True)
        self.transpose_slider.setValue(val)
        self.transpose_slider.blockSignals(False)

        self.transpose_input.setText(f"+{val}" if val > 0 else str(val))
        self.state_changed.emit()

    def _on_transpose_slider_changed(self, val: int):
        self.transpose_input.setText(f"+{val}" if val > 0 else str(val))
        self.state_changed.emit()

    def _on_transpose_input_changed(self):
        text = self.transpose_input.text().strip().replace("+", "")
        try:
            val = int(text)
        except ValueError:
            val = 0
        self._set_transpose_value(val)

    def _clean_recent_list(self):
        seen = set()
        cleaned = []
        for path in self.recent_midis:
            if path and os.path.isfile(path):
                norm = os.path.normcase(os.path.abspath(path))
                if norm not in seen:
                    seen.add(norm)
                    cleaned.append(os.path.abspath(path))
        self.recent_midis = cleaned[:12]

    def _update_recent_combo(self):
        self._clean_recent_list()
        self.recent_combo.blockSignals(True)
        self.recent_combo.clear()
        self.recent_combo.addItem("Select Recent MIDI...", None)

        for path in self.recent_midis:
            self.recent_combo.addItem(os.path.basename(path), path)

        if self.current_midi_data:
            cur_norm = os.path.normcase(os.path.abspath(self.current_midi_data["path"]))
            for i in range(1, self.recent_combo.count()):
                p = self.recent_combo.itemData(i)
                if p and os.path.normcase(os.path.abspath(p)) == cur_norm:
                    self.recent_combo.setCurrentIndex(i)
                    break
        else:
            self.recent_combo.setCurrentIndex(0)

        self.recent_combo.blockSignals(False)

    def _on_recent_selected(self, index: int):
        if index <= 0:
            return
        file_path = self.recent_combo.itemData(index)
        if not file_path:
            return

        ClickSound.play()
        if not os.path.isfile(file_path):
            self._show_error("Selected File No Longer Exists!")
            norm_target = os.path.normcase(os.path.abspath(file_path))
            self.recent_midis = [p for p in self.recent_midis if os.path.normcase(os.path.abspath(p)) != norm_target]
            self._update_recent_combo()
            self.state_changed.emit()
            return

        if self.current_midi_data:
            if os.path.normcase(os.path.abspath(file_path)) == os.path.normcase(os.path.abspath(self.current_midi_data["path"])):
                return

        self._load_midi_file(file_path)

    def _on_midi_dropped(self, file_path: str):
        norm_incoming = os.path.normcase(os.path.abspath(file_path))
        if self.current_midi_data:
            if norm_incoming == os.path.normcase(os.path.abspath(self.current_midi_data["path"])):
                ClickSound.play()
                self._show_error("The MIDI File Already a Selected!")
                return
        self._load_midi_file(file_path)

    def _select_file(self):
        ClickSound.play()
        file_path, _ = QFileDialog.getOpenFileName(self, "Select MIDI File", "", "MIDI Files (*.mid)")
        if file_path:
            self._load_midi_file(file_path)

    def _load_midi_file(self, file_path: str, silent: bool = False):
        try:
            real_path = os.path.abspath(file_path)
            norm_target = os.path.normcase(real_path)

            self.current_midi_data = MidiLoader.load(real_path)
            self.path_label.setText(self.current_midi_data["path"])
            self.path_label.setStyleSheet("color: #3b82f6; font-size: 12px; font-weight: 500;")
            self.status_label.setText("")

            total_dur = self.current_midi_data.get("duration", 0.0)
            self.time_label.setText(f"0:00:00 / {format_time(total_dur)}")
            self.progress_bar.setValue(0)
            self.btn_convert.setEnabled(True)

            self.recent_midis = [p for p in self.recent_midis if os.path.normcase(os.path.abspath(p)) != norm_target]
            self.recent_midis.insert(0, real_path)
            self._update_recent_combo()

            if not silent:
                self.state_changed.emit()
        except Exception as e:
            self.path_label.setText(f"Error: {str(e)}")
            self.path_label.setStyleSheet("color: #ff5f56; font-size: 12px;")
            self.btn_convert.setEnabled(False)

    def _on_convert_clicked(self):
        ClickSound.play()
        if not self.current_midi_data:
            self._show_error("MIDI File not Loaded!")
            return

        notes = self.current_midi_data.get("notes", [])
        tempos = self.current_midi_data.get("tempos", [])
        is_88 = self.toggle_88_keys.toggle.isChecked()
        is_temp = self.toggle_temp.toggle.isChecked()
        transpose_val = self.transpose_slider.value()

        result = convert_midi_to_qwerty(
            notes, 
            keys_88=is_88, 
            tempos=tempos, 
            include_tempo=is_temp,
            transpose=transpose_val
        )
        self.converted_text = result
        self.sheet_output.setPlainText(result)

        QApplication.clipboard().setText(result)
        self.progress_bar.setValue(1000)

        self._show_status("Converted & Copied to Clipboard!", is_error=False)

    def _copy_sheet(self):
        ClickSound.play()
        text = self.sheet_output.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self._show_status("Copied to Clipboard!", is_error=False)
        else:
            self._show_error("No sheet to copy!")

    def _save_to_txt(self):
        ClickSound.play()
        text = self.sheet_output.toPlainText()
        if not text:
            self._show_error("No sheet to save!")
            return

        def_name = ""
        if self.current_midi_data:
            def_name = os.path.splitext(self.current_midi_data.get("name", "sheet"))[0] + ".txt"

        path, _ = QFileDialog.getSaveFileName(self, "Save QWERTY Sheet", def_name, "Text Files (*.txt)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                self._show_status("Saved Successfully!", is_error=False)
            except Exception as e:
                self._show_error(f"Save failed: {str(e)}")

    def _show_error(self, text: str):
        self._show_status(text, is_error=True)

    def _show_status(self, text: str, is_error: bool = False):
        color = "#ef4444" if is_error else "#10b981"
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600;")
        self.status_label.setText(text)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(3000, lambda: self.status_label.setText("") if self.status_label.text() == text else None)

    def get_save_data(self) -> dict:
        return {
            "recent_midis": self.recent_midis,
            "last_midi_path": self.current_midi_data["path"] if self.current_midi_data else None,
            "keys_88": self.toggle_88_keys.toggle.isChecked(),
            "temp": self.toggle_temp.toggle.isChecked(),
            "transpose": self.transpose_slider.value()
        }

    def load_save_data(self, data: dict):
        if not isinstance(data, dict):
            return
        self.recent_midis = data.get("recent_midis", [])
        self._clean_recent_list()

        is_88 = data.get("keys_88", False)
        self.toggle_88_keys.toggle.setCheckedSilently(is_88)

        is_temp = data.get("temp", False)
        self.toggle_temp.toggle.setCheckedSilently(is_temp)

        saved_transpose = data.get("transpose", 0)
        self._set_transpose_value(saved_transpose)

        last_path = data.get("last_midi_path")
        if last_path and os.path.isfile(last_path):
            self._load_midi_file(last_path, silent=True)
        else:
            self._update_recent_combo()