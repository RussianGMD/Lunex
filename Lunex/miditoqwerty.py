import os
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QProgressBar, QComboBox,
    QPlainTextEdit, QApplication, QSlider, QLineEdit
)

from themes import BLACK_THEME, WHITE_THEME
from load_midi import MidiLoader
from drag import MidiDropCard
from convert import convert_midi_to_qwerty
from core_utils import format_time, SoundManager, truncate_text
from ui_components import SwitchRow

DEFAULT_CONVERTER_BLACK = BLACK_THEME["converter"]
DEFAULT_CONVERTER_WHITE = WHITE_THEME["converter"]


ClickSound = SoundManager


class MidiToQwertyView(QWidget):
    state_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_midi_data = None
        self.recent_midis = []
        self.converted_text = ""
        self.is_white = False
        self.theme_data = dict(DEFAULT_CONVERTER_BLACK)
        self._last_status_is_error = True
        self._setup_ui()

    def _setup_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(18)

        # left panel: MIDI Card and Previews
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
        left_layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignLeft)

        root_layout.addWidget(left_panel, stretch=3)

        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.settings_header = QLabel("CONVERT SETTINGS")
        right_layout.addWidget(self.settings_header)

        self.toggle_88_keys = SwitchRow("88 Keys", theme_section="converter")
        self.toggle_88_keys.toggle.toggled.connect(lambda: self.state_changed.emit())
        right_layout.addWidget(self.toggle_88_keys)

        self.toggle_temp = SwitchRow("Temp", theme_section="converter")
        self.toggle_temp.toggle.toggled.connect(lambda: self.state_changed.emit())
        right_layout.addWidget(self.toggle_temp)

        right_layout.addStretch()

        # TRANSPOSE (-24 .. +24)
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

        # Кнопка Convert
        self.btn_convert = QPushButton("Convert")
        self.btn_convert.setFixedHeight(32)
        self.btn_convert.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_convert.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_convert.clicked.connect(self._on_convert_clicked)
        self.btn_convert.setEnabled(False)
        right_layout.addWidget(self.btn_convert)

        root_layout.addWidget(right_panel, stretch=2)
        self.set_theme(DEFAULT_CONVERTER_BLACK)

    def set_theme(self, theme_or_is_white: dict | bool):
        if isinstance(theme_or_is_white, dict):
            self.is_white = bool(theme_or_is_white.get("is_white", False))
            base = DEFAULT_CONVERTER_WHITE if self.is_white else DEFAULT_CONVERTER_BLACK
            merged = dict(base)
            merged.update(theme_or_is_white)
            self.theme_data = merged
        else:
            self.is_white = bool(theme_or_is_white)
            self.theme_data = dict(DEFAULT_CONVERTER_WHITE if self.is_white else DEFAULT_CONVERTER_BLACK)

        t = self.theme_data
        sec_col = t.get("section_header_text", "#7b7b8a")
        sub_col = t.get("sub_header_text", "#636370")

        self.midi_header.setStyleSheet(f"color: {sec_col}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        self.path_title.setStyleSheet(f"color: {sub_col}; font-size: 10px; font-weight: bold;")
        self.recent_title.setStyleSheet(f"color: {sub_col}; font-size: 10px; font-weight: bold;")
        self.sheet_header.setStyleSheet(f"color: {sec_col}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        self.settings_header.setStyleSheet(f"color: {sec_col}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; margin-bottom: 2px;")
        self.transpose_title.setStyleSheet(f"color: {sec_col}; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
        self.time_title.setStyleSheet(f"color: {sec_col}; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")

        self.time_label.setStyleSheet(f"color: {t.get('time_label_text', '#8f8f9d')}; font-size: 11px; font-weight: 600;")

        if not self.current_midi_data:
            self.path_label.setStyleSheet(f"color: {t.get('path_text_idle', '#9d9da8')}; font-size: 12px;")
        else:
            self.path_label.setStyleSheet(f"color: {t.get('path_text_loaded', '#3b82f6')}; font-size: 12px; font-weight: 500;")

        status_col = (
            t.get("status_error_text", "#ef4444")
            if self._last_status_is_error
            else t.get("status_success_text", "#10b981")
        )
        self.status_label.setStyleSheet(f"color: {status_col}; font-size: 12px; font-weight: 600;")

        if hasattr(self.midi_card, "set_theme"):
            self.midi_card.set_theme(t)
        self.toggle_88_keys.set_theme(t)
        self.toggle_temp.set_theme(t)

        self.select_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get("select_btn_bg", "#202026")};
                color: {t.get("select_btn_text", "#ffffff")};
                border: 1px solid {t.get("select_btn_border", "#2c2c36")};
                border-radius: 5px;
                font-size: 12px;
                font-weight: 500;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background-color: {t.get("select_btn_hover_bg", "#2b2b34")};
                border: 1px solid {t.get("select_btn_hover_border", "#3d3d4a")};
            }}
            QPushButton:pressed {{
                background-color: {t.get("select_btn_pressed_bg", "#1a1a20")};
            }}
        """)

        self.recent_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {t.get("combo_bg", "#1a1a20")};
                color: {t.get("combo_text", "#c9c9d4")};
                border: 1px solid {t.get("combo_border", "#282832")};
                border-radius: 5px;
                padding-left: 10px;
                padding-right: 10px;
                font-size: 11px;
                font-weight: 500;
            }}
            QComboBox:hover {{
                border: 1px solid {t.get("combo_hover_border", "#3b82f6")};
                color: {t.get("combo_hover_text", "#ffffff")};
            }}
            QComboBox::drop-down {{ border: none; width: 0px; }}
            QComboBox QAbstractItemView {{
                background-color: {t.get("combo_popup_bg", "#16161a")};
                color: {t.get("combo_popup_text", "#e1e1e6")};
                selection-background-color: {t.get("combo_selection_bg", "#26334d")};
                selection-color: {t.get("combo_selection_text", "#60a5fa")};
                border: 1px solid {t.get("combo_popup_border", "#2c2c38")};
                border-radius: 5px;
                padding: 4px;
                outline: none;
            }}
        """)

        self.sheet_output.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {t.get("sheet_bg", "#16161a")};
                color: {t.get("sheet_text", "#e1e1e6")};
                border: 1px solid {t.get("sheet_border", "#23232a")};
                border-radius: 7px;
                padding: 10px;
                font-family: 'Consolas', 'Segoe UI', monospace;
                font-size: 12px;
            }}
            QPlainTextEdit:focus {{
                border: 1px solid {t.get("sheet_focus_border", "#3b82f6")};
            }}
        """)

        btn_sheet_style = f"""
            QPushButton {{
                background-color: {t.get("sheet_btn_bg", "#16161a")};
                color: {t.get("sheet_btn_text", "#ffffff")};
                border: 1px solid {t.get("sheet_btn_border", "#23232a")};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background-color: {t.get("sheet_btn_hover_bg", "#202026")};
                border: 1px solid {t.get("sheet_btn_hover_border", "#3b82f6")};
            }}
        """
        self.btn_copy.setStyleSheet(btn_sheet_style)
        self.btn_save_txt.setStyleSheet(btn_sheet_style)

        self.transpose_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {t.get("input_bg", "#16161a")};
                color: {t.get("input_text", "#ffffff")};
                border: 1px solid {t.get("input_border", "#23232a")};
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
            }}
            QLineEdit:focus {{
                border: 1px solid {t.get("input_focus_border", "#3b82f6")};
            }}
        """)

        self.transpose_slider.setStyleSheet(f"""
            QSlider {{ height: 26px; }}
            QSlider::groove:horizontal {{
                height: 5px;
                background-color: {t.get("slider_groove_bg", "#16161a")};
                border: 1px solid {t.get("slider_groove_border", "#23232a")};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background-color: {t.get("slider_subpage_bg", "#3b82f6")};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background-color: {t.get("slider_handle_bg", "#ffffff")};
                border: {t.get("slider_handle_border", "none")};
                width: 12px; height: 12px; margin: -3px 0; border-radius: 6px;
            }}
            QSlider::handle:horizontal:hover {{
                background-color: {t.get("slider_handle_hover_bg", "#e2e8f0")};
            }}
        """)

        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {t.get("progress_bg", "#16161a")};
                border: 1px solid {t.get("progress_border", "#23232a")};
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {t.get("progress_chunk", "#3b82f6")};
                border-radius: 2px;
            }}
        """)

        self.btn_convert.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get("convert_btn_bg", "#16161a")};
                color: {t.get("convert_btn_text", "#ffffff")};
                border: 1px solid {t.get("convert_btn_border", "#23232a")};
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {t.get("convert_btn_hover_bg", "#202026")};
                border: 1px solid {t.get("convert_btn_hover_border", "#3b82f6")};
            }}
            QPushButton:pressed {{
                background-color: {t.get("convert_btn_pressed_bg", "#121216")};
            }}
            QPushButton:disabled {{
                background-color: {t.get("convert_btn_disabled_bg", "rgba(22, 22, 26, 0.25)")};
                color: {t.get("convert_btn_disabled_text", "rgba(255, 255, 255, 0.2)")};
                border: 1px solid {t.get("convert_btn_disabled_border", "rgba(35, 35, 42, 0.25)")};
            }}
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
            self.recent_combo.addItem(truncate_text(os.path.basename(path), 50), path)

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

        SoundManager.play()

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
                SoundManager.play()
                self._show_error("The MIDI File Already a Selected!")
                return
        self._load_midi_file(file_path)

    def _select_file(self):
        SoundManager.play()
        file_path, _ = QFileDialog.getOpenFileName(self, "Select MIDI File", "", "MIDI Files (*.mid)")
        if file_path:
            self._load_midi_file(file_path)

    def _load_midi_file(self, file_path: str, silent: bool = False):
        t = self.theme_data
        try:
            real_path = os.path.abspath(file_path)
            norm_target = os.path.normcase(real_path)

            self.current_midi_data = MidiLoader.load(real_path)
            self.path_label.setText(truncate_text(self.current_midi_data["path"], 50))
            self.path_label.setToolTip(self.current_midi_data["path"])
            self.path_label.setStyleSheet(
                f"color: {t.get('path_text_loaded', '#3b82f6')}; font-size: 12px; font-weight: 500;"
            )
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
            self.path_label.setStyleSheet(
                f"color: {t.get('path_text_error', '#ff5f56')}; font-size: 12px;"
            )
            self.btn_convert.setEnabled(False)

    def _on_convert_clicked(self):
        SoundManager.play()
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
        SoundManager.play()
        text = self.sheet_output.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self._show_status("Copied to Clipboard!", is_error=False)
        else:
            self._show_error("No sheet to copy!")

    def _save_to_txt(self):
        SoundManager.play()
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
        self._last_status_is_error = is_error
        t = self.theme_data
        color = t.get("status_error_text", "#ef4444") if is_error else t.get("status_success_text", "#10b981")
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600;")
        self.status_label.setText(text)
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