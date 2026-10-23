import os
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel,
    QPushButton, QFileDialog, QProgressBar, QComboBox,
    QSlider, QLineEdit
)

from themes import BLACK_THEME, WHITE_THEME
from load_midi import MidiLoader
from drag import MidiDropCard
from core_utils import format_time, SoundManager, truncate_text
from ui_components import AutoRefreshComboBox, KeybindSlot
from midi_output_player import MidiOutputPlayer, rtmidi

DEFAULT_MUSIC_BLACK = BLACK_THEME["music"]
DEFAULT_MUSIC_WHITE = WHITE_THEME["music"]


ClickSound = SoundManager


class MusicView(QWidget):
    state_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_midi_data = None
        self.recent_midis = []
        self.selected_port_name = None
        self.is_white = False
        self.theme_data = dict(DEFAULT_MUSIC_BLACK)

        self.player = MidiOutputPlayer(self)
        self.player.finished.connect(self._on_player_finished)
        self.player.progress_changed.connect(self._on_progress_changed)

        self._setup_ui()
        self.refresh_ports()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(14)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(12)
        top_bar.addStretch()

        selector_container = QHBoxLayout()
        selector_container.setSpacing(8)
        self.output_label = QLabel("MIDI OUTPUT")
        selector_container.addWidget(self.output_label)

        self.output_combo = AutoRefreshComboBox()
        self.output_combo.refresh_callback = self.refresh_ports
        self.output_combo.setFixedSize(220, 28)
        self.output_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.output_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.output_combo.currentIndexChanged.connect(self._on_port_selected)
        selector_container.addWidget(self.output_combo)

        top_bar.addLayout(selector_container)
        root_layout.addLayout(top_bar)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(18)

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

        self.keybinds_header = QLabel("KEYBINDS")
        left_layout.addWidget(self.keybinds_header)

        self.keybinds_card = QWidget()
        self.keybinds_card.setObjectName("musicKeybindsCard")
        keybinds_grid = QGridLayout(self.keybinds_card)
        keybinds_grid.setContentsMargins(12, 12, 12, 12)
        keybinds_grid.setHorizontalSpacing(10)
        keybinds_grid.setVerticalSpacing(10)

        self.bind_start = KeybindSlot("Start", "F1", theme_section="music")
        self.bind_pause = KeybindSlot("Pause", "F2", theme_section="music")
        self.bind_end = KeybindSlot("End", "F3", theme_section="music")

        for slot in (self.bind_start, self.bind_pause, self.bind_end):
            slot.button.key_changed.connect(self.state_changed.emit)

        keybinds_grid.addWidget(self.bind_start, 0, 0)
        keybinds_grid.addWidget(self.bind_pause, 0, 1)
        keybinds_grid.addWidget(self.bind_end, 0, 2)

        left_layout.addWidget(self.keybinds_card)
        left_layout.addStretch()

        self.status_label = QLabel("")
        left_layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignLeft)

        content_layout.addWidget(left_panel, stretch=3)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        self.info_header = QLabel("DEVICE & TRACK INFO")
        right_layout.addWidget(self.info_header)

        self.info_card = QWidget()
        self.info_card.setObjectName("infoCard")
        info_grid = QGridLayout(self.info_card)
        info_grid.setContentsMargins(14, 14, 14, 14)
        info_grid.setHorizontalSpacing(14)
        info_grid.setVerticalSpacing(10)

        self.info_titles = []

        def make_row(row_idx, title):
            t_lbl = QLabel(title)
            self.info_titles.append(t_lbl)
            v_lbl = QLabel("—")
            info_grid.addWidget(t_lbl, row_idx, 0)
            info_grid.addWidget(v_lbl, row_idx, 1)
            return v_lbl

        self.info_status = make_row(0, "STATUS")
        self.info_device = make_row(1, "DEVICE")
        self.info_notes = make_row(2, "NOTES")
        self.info_duration = make_row(3, "DURATION")

        right_layout.addWidget(self.info_card)
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

        controls_container = QHBoxLayout()
        controls_container.setSpacing(6)
        self.btn_start = QPushButton("Start")
        self.btn_pause = QPushButton("Pause")
        self.btn_end = QPushButton("End")

        for btn in (self.btn_start, self.btn_pause, self.btn_end):
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setEnabled(False)
            controls_container.addWidget(btn)

        self.btn_start.clicked.connect(self._on_start_clicked)
        self.btn_pause.clicked.connect(self._on_pause_clicked)
        self.btn_end.clicked.connect(self._on_end_clicked)

        right_layout.addLayout(controls_container)
        content_layout.addWidget(right_panel, stretch=2)
        root_layout.addLayout(content_layout)

        self.set_theme(DEFAULT_MUSIC_BLACK)
        self._update_info_card()

    def set_theme(self, theme_or_is_white: dict | bool):
        if isinstance(theme_or_is_white, dict):
            self.is_white = bool(theme_or_is_white.get("is_white", False))
            base = DEFAULT_MUSIC_WHITE if self.is_white else DEFAULT_MUSIC_BLACK
            merged = dict(base)
            merged.update(theme_or_is_white)
            self.theme_data = merged
        else:
            self.is_white = bool(theme_or_is_white)
            self.theme_data = dict(DEFAULT_MUSIC_WHITE if self.is_white else DEFAULT_MUSIC_BLACK)

        t = self.theme_data
        sec_col = t.get("section_header_text", "#7b7b8a")
        sub_col = t.get("sub_header_text", "#636370")

        self.output_label.setStyleSheet(f"color: {sub_col}; font-size: 10px; font-weight: bold;")
        self.midi_header.setStyleSheet(f"color: {sec_col}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        self.path_title.setStyleSheet(f"color: {sub_col}; font-size: 10px; font-weight: bold;")
        self.recent_title.setStyleSheet(f"color: {sub_col}; font-size: 10px; font-weight: bold;")
        self.keybinds_header.setStyleSheet(f"color: {sec_col}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        self.info_header.setStyleSheet(f"color: {sec_col}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        self.transpose_title.setStyleSheet(f"color: {sec_col}; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
        self.time_title.setStyleSheet(f"color: {sec_col}; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")

        for t_lbl in self.info_titles:
            t_lbl.setStyleSheet(f"color: {sub_col}; font-size: 11px; font-weight: 600;")

        if self.current_midi_data:
            self.path_label.setStyleSheet(
                f"color: {t.get('path_text_loaded', '#3b82f6')}; font-size: 12px; font-weight: 500;"
            )
        else:
            self.path_label.setStyleSheet(
                f"color: {t.get('path_text_idle', '#9d9da8')}; font-size: 12px;"
            )

        self.status_label.setStyleSheet(
            f"color: {t.get('status_error_text', '#ef4444')}; font-size: 12px; font-weight: 600;"
        )
        self.time_label.setStyleSheet(
            f"color: {t.get('time_label_text', '#8f8f9d')}; font-size: 11px; font-weight: 600;"
        )

        if hasattr(self.midi_card, "set_theme"):
            self.midi_card.set_theme(t)

        for slot in (self.bind_start, self.bind_pause, self.bind_end):
            slot.set_theme(t)

        card_bg = t.get("card_bg", "#16161a")
        card_border = t.get("card_border", "#23232a")

        self.keybinds_card.setStyleSheet(f"""
            QWidget#musicKeybindsCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 7px;
            }}
        """)
        self.info_card.setStyleSheet(f"""
            QWidget#infoCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 7px;
            }}
        """)

        combo_hover_border = t.get("combo_hover_border", "#3b82f6")
        combo_hover_text = t.get("combo_hover_text", "#ffffff")
        popup_bg = t.get("combo_popup_bg", "#16161a")
        popup_text = t.get("combo_popup_text", "#e1e1e6")
        popup_border = t.get("combo_popup_border", "#2c2c38")
        sel_bg = t.get("combo_selection_bg", "#26334d")
        sel_text = t.get("combo_selection_text", "#60a5fa")

        self.output_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {t.get("output_combo_bg", "#16161a")};
                color: {t.get("output_combo_text", "#c9c9d4")};
                border: 1px solid {t.get("output_combo_border", "#23232a")};
                border-radius: 5px;
                padding-left: 10px;
                padding-right: 10px;
                font-size: 11px;
                font-weight: 500;
            }}
            QComboBox:hover {{
                border: 1px solid {combo_hover_border};
                color: {combo_hover_text};
            }}
            QComboBox::drop-down {{ border: none; width: 0px; }}
            QComboBox QAbstractItemView {{
                background-color: {popup_bg};
                color: {popup_text};
                selection-background-color: {sel_bg};
                selection-color: {sel_text};
                border: 1px solid {popup_border};
                border-radius: 5px;
                padding: 4px;
                outline: none;
            }}
        """)

        self.recent_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {t.get("recent_combo_bg", "#1a1a20")};
                color: {t.get("recent_combo_text", "#c9c9d4")};
                border: 1px solid {t.get("recent_combo_border", "#282832")};
                border-radius: 5px;
                padding-left: 10px;
                padding-right: 10px;
                font-size: 11px;
                font-weight: 500;
            }}
            QComboBox:hover {{
                border: 1px solid {combo_hover_border};
                color: {combo_hover_text};
            }}
            QComboBox::drop-down {{ border: none; width: 0px; }}
            QComboBox QAbstractItemView {{
                background-color: {popup_bg};
                color: {popup_text};
                selection-background-color: {sel_bg};
                selection-color: {sel_text};
                border: 1px solid {popup_border};
                border-radius: 5px;
                padding: 4px;
                outline: none;
            }}
        """)

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

        btn_action_style = f"""
            QPushButton {{
                background-color: {t.get("action_btn_bg", "#16161a")};
                color: {t.get("action_btn_text", "#ffffff")};
                border: 1px solid {t.get("action_btn_border", "#23232a")};
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
                height: 30px;
            }}
            QPushButton:hover {{
                background-color: {t.get("action_btn_hover_bg", "#202026")};
                border: 1px solid {t.get("action_btn_hover_border", "#32323d")};
            }}
            QPushButton:pressed {{
                background-color: {t.get("action_btn_pressed_bg", "#121216")};
            }}
            QPushButton:disabled {{
                background-color: {t.get("action_btn_disabled_bg", "rgba(22, 22, 26, 0.25)")};
                color: {t.get("action_btn_disabled_text", "rgba(255, 255, 255, 0.2)")};
                border: 1px solid {t.get("action_btn_disabled_border", "rgba(35, 35, 42, 0.25)")};
            }}
        """
        for btn in (self.btn_start, self.btn_pause, self.btn_end):
            btn.setStyleSheet(btn_action_style)

        self._update_info_card()

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

    def refresh_ports(self):
        self.output_combo.blockSignals(True)
        self.output_combo.clear()
        ports = []
        if rtmidi:
            try:
                midi_out = rtmidi.MidiOut()
                ports = midi_out.get_ports()
                del midi_out
            except Exception:
                ports = []

        if not ports:
            self.output_combo.addItem("No MIDI Outputs Found", None)
            self.selected_port_name = None
        else:
            self.output_combo.addItem("Select Output...", None)
            target_idx = 0
            for i, port_name in enumerate(ports, start=1):
                self.output_combo.addItem(port_name, port_name)
                if self.selected_port_name and port_name == self.selected_port_name:
                    target_idx = i
            self.output_combo.setCurrentIndex(target_idx)

        self.output_combo.blockSignals(False)
        self._update_info_card()

    def _on_port_selected(self, index: int):
        data = self.output_combo.itemData(index)
        self.selected_port_name = data
        self._update_info_card()
        self.state_changed.emit()

    def _update_info_card(self):
        t = self.theme_data
        val_color = t.get("info_value_text", "#18181b" if self.is_white else "#e1e1e6")
        conn_color = t.get("info_status_connected", "#10b981")
        disc_color = t.get("info_status_disconnected", "#ef4444")

        if self.selected_port_name:
            self.info_status.setText("Connected")
            self.info_status.setStyleSheet(f"color: {conn_color}; font-size: 12px; font-weight: 600;")
            self.info_device.setText(self.selected_port_name)
            self.info_device.setStyleSheet(f"color: {val_color}; font-size: 12px; font-weight: 500;")
        else:
            self.info_status.setText("Disconnected")
            self.info_status.setStyleSheet(f"color: {disc_color}; font-size: 12px; font-weight: 600;")
            self.info_device.setText("None")
            self.info_device.setStyleSheet(f"color: {val_color}; font-size: 12px; font-weight: 500;")

        if self.current_midi_data:
            notes_cnt = self.current_midi_data.get("notes_count", len(self.current_midi_data.get("notes", [])))
            dur = self.current_midi_data.get("duration", 0.0)
            self.info_notes.setText(f"{notes_cnt:,}")
            self.info_duration.setText(format_time(dur))
        else:
            self.info_notes.setText("—")
            self.info_duration.setText("—")

        self.info_notes.setStyleSheet(f"color: {val_color}; font-size: 12px; font-weight: 500;")
        self.info_duration.setStyleSheet(f"color: {val_color}; font-size: 12px; font-weight: 500;")

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

            self.btn_start.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_end.setEnabled(False)
            self.btn_pause.setText("Pause")

            self.recent_midis = [p for p in self.recent_midis if os.path.normcase(os.path.abspath(p)) != norm_target]
            self.recent_midis.insert(0, real_path)
            self._update_recent_combo()
            self._update_info_card()

            if not silent:
                self.state_changed.emit()
        except Exception as e:
            self.path_label.setText(f"Error: {str(e)}")
            self.path_label.setStyleSheet(
                f"color: {t.get('path_text_error', '#ff5f56')}; font-size: 12px;"
            )
            self._reset_to_idle()

    def _reset_to_idle(self):
        self.btn_start.setEnabled(True if self.current_midi_data else False)
        self.btn_pause.setEnabled(False)
        self.btn_end.setEnabled(False)
        self.btn_pause.setText("Pause")
        if self.current_midi_data:
            total_dur = self.current_midi_data.get("duration", 0.0)
            self.time_label.setText(f"0:00:00 / {format_time(total_dur)}")
        else:
            self.time_label.setText("0:00:00 / 0:00:00")
        self.progress_bar.setValue(0)

    def _show_error(self, text: str):
        self.status_label.setText(text)
        QTimer.singleShot(3000, lambda: self.status_label.setText("") if self.status_label.text() == text else None)

    def _on_start_clicked(self):
        SoundManager.play()
        if not self.current_midi_data:
            self._show_error("MIDI File not Loaded!")
            return
        if not self.selected_port_name:
            self._show_error("No MIDI Output Selected!")
            return

        self.player.stop_playback()
        self.player.set_data(
            self.current_midi_data,
            self.selected_port_name,
            self.transpose_slider.value()
        )
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_pause.setText("Pause")
        self.btn_end.setEnabled(True)
        self.player.start()

    def _on_pause_clicked(self):
        SoundManager.play()
        if not self.player.is_playing:
            return

        if self.player.is_paused:
            self.player.resume()
            self.btn_pause.setText("Pause")
        else:
            self.player.pause()
            self.btn_pause.setText("Continue")
        self.btn_start.setEnabled(False)
        self.btn_end.setEnabled(True)

    def _on_end_clicked(self):
        SoundManager.play()
        self.player.stop_playback()
        self._reset_to_idle()

    def _on_player_finished(self):
        self._reset_to_idle()

    def _on_progress_changed(self, current_sec: float):
        if not self.current_midi_data:
            return
        total_sec = float(self.current_midi_data.get("duration", 0.0))
        if total_sec > 0:
            ratio = min(1.0, current_sec / total_sec)
            self.progress_bar.setValue(int(ratio * 1000))
            self.time_label.setText(f"{format_time(current_sec)} / {format_time(total_sec)}")

    def trigger_action(self, action: str):
        if any(slot.button.is_listening for slot in (self.bind_start, self.bind_pause, self.bind_end)):
            return

        if action == "start":
            if self.btn_start.isEnabled():
                self._on_start_clicked()
            elif not self.current_midi_data:
                self._show_error("MIDI File not Loaded!")
            elif not self.selected_port_name:
                self._show_error("No MIDI Output Selected!")
        elif action == "pause":
            if self.btn_pause.isEnabled():
                self._on_pause_clicked()
        elif action == "end":
            if self.btn_end.isEnabled():
                self._on_end_clicked()

    def get_bindings(self) -> dict:
        return {
            "start": self.bind_start.button.key_value,
            "pause": self.bind_pause.button.key_value,
            "end": self.bind_end.button.key_value,
        }

    def get_save_data(self) -> dict:
        return {
            "recent_midis": self.recent_midis,
            "last_midi_path": self.current_midi_data["path"] if self.current_midi_data else None,
            "selected_port": self.selected_port_name,
            "transpose": self.transpose_slider.value(),
            "keybinds": self.get_bindings()
        }

    def load_save_data(self, data: dict):
        if not isinstance(data, dict):
            return
        self.recent_midis = data.get("recent_midis", [])
        self._clean_recent_list()

        port = data.get("selected_port")
        if port:
            self.selected_port_name = port
            self.refresh_ports()

        saved_transpose = data.get("transpose", 0)
        self._set_transpose_value(saved_transpose)

        binds = data.get("keybinds", {})
        if "start" in binds:
            self.bind_start.button.set_key_silently(binds["start"])
        if "pause" in binds:
            self.bind_pause.button.set_key_silently(binds["pause"])
        if "end" in binds:
            self.bind_end.button.set_key_silently(binds["end"])

        last_path = data.get("last_midi_path")
        if last_path and os.path.isfile(last_path):
            self._load_midi_file(last_path, silent=True)
        else:
            self._update_recent_combo()

    def stop_playback(self):
        self.player.stop_playback()