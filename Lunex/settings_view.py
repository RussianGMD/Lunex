from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsOpacityEffect, QFrame, QScrollArea
)

from themes import BLACK_THEME, WHITE_THEME
from core_utils import SoundManager
from settings_cards import (
    CURRENT_VERSION, UPDATE_URL, UpdateCheckerThread,
    SettingsSwitchRow as SwitchRow, ComboRow, FailDelayRow,
    FailNotesCountCard, FailSettingCard, SpeedLimitCard,
    SpeedChanceCard, StepSettingCard, TransposeSettingCard,
    TimerSettingRow, UpdateCard
)

DEFAULT_SETTINGS_BLACK = BLACK_THEME["settings"]
DEFAULT_SETTINGS_WHITE = WHITE_THEME["settings"]

# Alias for backward compatibility with main.py
ClickSound = SoundManager


class SettingsView(QWidget):
    state_changed = pyqtSignal()
    reset_recents_requested = pyqtSignal()
    open_debug_console_requested = pyqtSignal()
    close_debug_console_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_white = False
        self.theme_data = dict(DEFAULT_SETTINGS_BLACK)
        self._reset_btn_is_success = False
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

        # Category: MIDI Player Settings
        self.cat_player_header = QLabel("MIDI PLAYER SETTINGS")
        root_layout.addWidget(self.cat_player_header)

        self.toggle_human_fail = SwitchRow("Human Fail")
        self.toggle_human_fail.toggle.toggled.connect(self._on_toggle_human_fail)
        root_layout.addWidget(self.toggle_human_fail)

        self.toggle_perfectionist = SwitchRow("Perfectionist Mode")
        self.toggle_perfectionist.toggle.toggled.connect(lambda: self.state_changed.emit())
        root_layout.addWidget(self.toggle_perfectionist)

        
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

        self.fail_notes_count_card = FailNotesCountCard("How Many Fail Notes", default_val=1)
        self.fail_notes_count_card.value_changed.connect(lambda: self.state_changed.emit())
        fails_layout.addWidget(self.fail_notes_count_card)

        self.transpose_fail_mode_row = ComboRow("Transpose Fail Mode", ["Tick Fail", "Before Fail", "After Fail"])
        self.transpose_fail_mode_row.value_changed.connect(self._on_transpose_fail_mode_changed)
        fails_layout.addWidget(self.transpose_fail_mode_row)

        self.transpose_fail_delay_row = FailDelayRow("Fail Delay (ms)", default_val=500)
        self.transpose_fail_delay_row.value_changed.connect(lambda: self.state_changed.emit())
        fails_layout.addWidget(self.transpose_fail_delay_row)
        self.transpose_fail_delay_row.setVisible(False)

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

        
        self.toggle_timer_start = SwitchRow("Timer Start")
        self.toggle_timer_start.toggle.toggled.connect(self._on_toggle_timer_start)
        root_layout.addWidget(self.toggle_timer_start)

        self.timer_seconds_row = TimerSettingRow("Seconds", default_val=3)
        self.timer_seconds_row.value_changed.connect(lambda: self.state_changed.emit())
        root_layout.addWidget(self.timer_seconds_row)
        self.timer_seconds_row.setVisible(False)

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

        
        self.cat_debug_header = QLabel("DEBUG CONSOLE")
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

        
        self.cat_theme_header = QLabel("APP THEME")
        root_layout.addWidget(self.cat_theme_header)

        self.theme_row = ComboRow("Theme", ["Black (Standart)", "White"])
        self.theme_row.value_changed.connect(lambda: self.state_changed.emit())
        root_layout.addWidget(self.theme_row)

        self.click_sound_row = ComboRow("Click Sound", ["None", "Click", "Tap", "Tick"])
        self.click_sound_row.combo.blockSignals(True)
        self.click_sound_row.combo.setCurrentIndex(1)
        self.click_sound_row.combo.blockSignals(False)
        self.click_sound_row.value_changed.connect(self._on_click_sound_changed)
        root_layout.addWidget(self.click_sound_row)

        self.toggle_overlay = SwitchRow("Overlay Information")
        self.toggle_overlay.toggle.toggled.connect(lambda: self.state_changed.emit())
        root_layout.addWidget(self.toggle_overlay)

        # Category: Overlay Settings
        self.cat_overlay_header = QLabel("OVERLAY SETTINGS")
        root_layout.addWidget(self.cat_overlay_header)

        self.toggle_ov_speed = SwitchRow("Speed")
        self.toggle_ov_midi = SwitchRow("MIDI File")
        self.toggle_ov_notes = SwitchRow("How many notes up")
        self.toggle_ov_transpose = SwitchRow("Transpose")
        self.toggle_ov_human_fail = SwitchRow("Human Fail")
        self.toggle_ov_sustain = SwitchRow("Sustain")

        self._overlay_toggles = (
            self.toggle_ov_speed,
            self.toggle_ov_midi,
            self.toggle_ov_notes,
            self.toggle_ov_transpose,
            self.toggle_ov_human_fail,
            self.toggle_ov_sustain,
        )
        for row in self._overlay_toggles:
            row.toggle.setCheckedSilently(True)
            row.toggle.toggled.connect(lambda: self.state_changed.emit())
            root_layout.addWidget(row)

        
        self.cat_update_header = QLabel("APP UPDATE")
        root_layout.addWidget(self.cat_update_header)

        self.update_card = UpdateCard()
        root_layout.addWidget(self.update_card)

        root_layout.addStretch()

        self.scroll.setWidget(self.content_widget)
        outer_layout.addWidget(self.scroll)

        self._update_fails_availability(False)
        self.set_theme(DEFAULT_SETTINGS_BLACK)

    def set_theme(self, theme_or_is_white: dict | bool):
        if isinstance(theme_or_is_white, dict):
            self.is_white = bool(theme_or_is_white.get("is_white", False))
            base = DEFAULT_SETTINGS_WHITE if self.is_white else DEFAULT_SETTINGS_BLACK
            merged = dict(base)
            merged.update(theme_or_is_white)
            self.theme_data = merged
        else:
            self.is_white = bool(theme_or_is_white)
            self.theme_data = dict(DEFAULT_SETTINGS_WHITE if self.is_white else DEFAULT_SETTINGS_BLACK)

        t = self.theme_data
        color_header = t.get("section_header_text", "#7b7b8a")

        self.cat_player_header.setStyleSheet(f"color: {color_header}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        self.cat_debug_header.setStyleSheet(f"color: {color_header}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; margin-top: 4px;")
        self.cat_theme_header.setStyleSheet(f"color: {color_header}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; margin-top: 4px;")
        self.cat_overlay_header.setStyleSheet(f"color: {color_header}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; margin-top: 4px;")
        self.cat_update_header.setStyleSheet(f"color: {color_header}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; margin-top: 4px;")

        self.toggle_human_fail.set_theme(t)
        self.toggle_perfectionist.set_theme(t)
        self.speed_fail_card.set_theme(t)
        self.transpose_fail_card.set_theme(t)
        self.fail_notes_count_card.set_theme(t)
        self.transpose_fail_mode_row.set_theme(t)
        self.transpose_fail_delay_row.set_theme(t)
        self.slow_speed_card.set_theme(t)
        self.fast_speed_card.set_theme(t)
        self.slow_chance_card.set_theme(t)
        self.fast_chance_card.set_theme(t)
        self.toggle_timer_start.set_theme(t)
        self.timer_seconds_row.set_theme(t)
        self.toggle_loop_song.set_theme(t)
        self.speed_step_card.set_theme(t)
        self.macro_transpose_card.set_theme(t)
        self.toggle_console.set_theme(t)
        self.theme_row.set_theme(t)
        self.click_sound_row.set_theme(t)
        self.toggle_overlay.set_theme(t)
        for row in self._overlay_toggles:
            row.set_theme(t)
        self.update_card.set_theme(t)

        self._apply_reset_btn_style(is_success=self._reset_btn_is_success)

        self.content_widget.setStyleSheet("background: transparent;")
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{
                border: none;
                background: {t.get("scrollbar_bg", "#101014")};
                width: 6px;
                border-radius: 3px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {t.get("scrollbar_handle_bg", "#23232c")};
                min-height: 25px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {t.get("scrollbar_handle_hover_bg", "#3b82f6")};
            }}
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical {{ border: none; background: none; height: 0px; }}
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{ background: none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """)

        btn_debug_style = f"""
            QPushButton {{
                background-color: {t.get("button_bg", "#16161a")};
                color: {t.get("button_text", "#e1e1e6")};
                border: 1px solid {t.get("button_border", "#23232a")};
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background-color: {t.get("button_hover_bg", "#202026")};
                border: 1px solid {t.get("button_hover_border", "#3b82f6")};
                color: {t.get("button_hover_text", "#ffffff")};
            }}
            QPushButton:pressed {{
                background-color: {t.get("button_pressed_bg", "#121216")};
            }}
        """
        self.btn_open_debug.setStyleSheet(btn_debug_style)
        self.btn_close_debug.setStyleSheet(btn_debug_style)

    def _apply_reset_btn_style(self, is_success: bool = False):
        self._reset_btn_is_success = is_success
        t = self.theme_data
        if is_success:
            self.btn_reset_recents.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.get("reset_recents_success_bg", "#12241b")};
                    color: {t.get("reset_recents_success_text", "#10b981")};
                    border: 1px solid {t.get("reset_recents_success_border", "#059669")};
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 0 16px;
                }}
            """)
        else:
            self.btn_reset_recents.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.get("reset_recents_bg", "#16161a")};
                    color: {t.get("reset_recents_text", "#e1e1e6")};
                    border: 1px solid {t.get("reset_recents_border", "#23232a")};
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 0 16px;
                }}
                QPushButton:hover {{
                    background-color: {t.get("reset_recents_hover_bg", "#202026")};
                    border: 1px solid {t.get("reset_recents_hover_border", "#ef4444")};
                    color: {t.get("reset_recents_hover_text", "#ef4444")};
                }}
                QPushButton:pressed {{
                    background-color: {t.get("reset_recents_pressed_bg", "#121216")};
                }}
            """)

    def _on_open_debug_clicked(self):
        SoundManager.play()
        self.open_debug_console_requested.emit()

    def _on_close_debug_clicked(self):
        SoundManager.play()
        self.close_debug_console_requested.emit()

    def _on_reset_recents_clicked(self):
        SoundManager.play()
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

    def _on_transpose_fail_mode_changed(self):
        mode = self.transpose_fail_mode_row.combo.currentText()
        self.transpose_fail_delay_row.setVisible(mode in ("Before Fail", "After Fail"))
        self.state_changed.emit()

    def _on_click_sound_changed(self):
        sound_name = self.click_sound_row.combo.currentText()
        SoundManager.set_sound(sound_name)
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

    def is_overlay_enabled(self) -> bool:
        return self.toggle_overlay.toggle.isChecked()

    def get_overlay_row_settings(self) -> dict:
        return {
            "show_speed": self.toggle_ov_speed.toggle.isChecked(),
            "show_midi": self.toggle_ov_midi.toggle.isChecked(),
            "show_notes": self.toggle_ov_notes.toggle.isChecked(),
            "show_transpose": self.toggle_ov_transpose.toggle.isChecked(),
            "show_human_fail": self.toggle_ov_human_fail.toggle.isChecked(),
            "show_sustain": self.toggle_ov_sustain.toggle.isChecked(),
        }

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

    def get_click_sound(self) -> str:
        return self.click_sound_row.combo.currentText()

    def get_save_data(self) -> dict:
        return {
            "human_fail": self.toggle_human_fail.toggle.isChecked(),
            "perfectionist_mode": self.toggle_perfectionist.toggle.isChecked(),
            "speed_fail_pct": self.speed_fail_card.get_value(),
            "transpose_fail_pct": self.transpose_fail_card.get_value(),
            "fail_notes_count": self.fail_notes_count_card.get_value(),
            "transpose_fail_mode": self.transpose_fail_mode_row.combo.currentText(),
            "transpose_fail_delay_ms": self.transpose_fail_delay_row.get_value(),
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
            "app_theme": self.theme_row.combo.currentText(),
            "click_sound": self.click_sound_row.combo.currentText(),
            "overlay_info": self.toggle_overlay.toggle.isChecked(),
            "overlay_speed": self.toggle_ov_speed.toggle.isChecked(),
            "overlay_midi": self.toggle_ov_midi.toggle.isChecked(),
            "overlay_notes": self.toggle_ov_notes.toggle.isChecked(),
            "overlay_transpose": self.toggle_ov_transpose.toggle.isChecked(),
            "overlay_human_fail": self.toggle_ov_human_fail.toggle.isChecked(),
            "overlay_sustain": self.toggle_ov_sustain.toggle.isChecked(),
        }

    def load_save_data(self, data: dict):
        if not isinstance(data, dict):
            return

        is_hf = data.get("human_fail", False)
        self.toggle_human_fail.toggle.setCheckedSilently(is_hf)
        self._update_fails_availability(is_hf)

        is_perf = data.get("perfectionist_mode", False)
        self.toggle_perfectionist.toggle.setCheckedSilently(is_perf)

        self.speed_fail_card.set_value(data.get("speed_fail_pct", 1.0))
        self.transpose_fail_card.set_value(data.get("transpose_fail_pct", 5.0))
        self.fail_notes_count_card.set_value(data.get("fail_notes_count", 1))

        saved_tf_mode = data.get("transpose_fail_mode", "Tick Fail")
        tf_idx = self.transpose_fail_mode_row.combo.findText(saved_tf_mode)
        if tf_idx >= 0:
            self.transpose_fail_mode_row.combo.blockSignals(True)
            self.transpose_fail_mode_row.combo.setCurrentIndex(tf_idx)
            self.transpose_fail_mode_row.combo.blockSignals(False)
        self.transpose_fail_delay_row.setVisible(saved_tf_mode in ("Before Fail", "After Fail"))
        self.transpose_fail_delay_row.set_value(data.get("transpose_fail_delay_ms", 500))

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

        saved_sound = data.get("click_sound", "Click")
        s_idx = self.click_sound_row.combo.findText(saved_sound)
        if s_idx >= 0:
            self.click_sound_row.combo.blockSignals(True)
            self.click_sound_row.combo.setCurrentIndex(s_idx)
            self.click_sound_row.combo.blockSignals(False)
        SoundManager.set_sound(self.get_click_sound())

        is_overlay = data.get("overlay_info", False)
        self.toggle_overlay.toggle.setCheckedSilently(is_overlay)

        self.toggle_ov_speed.toggle.setCheckedSilently(data.get("overlay_speed", True))
        self.toggle_ov_midi.toggle.setCheckedSilently(data.get("overlay_midi", True))
        self.toggle_ov_notes.toggle.setCheckedSilently(data.get("overlay_notes", True))
        self.toggle_ov_transpose.toggle.setCheckedSilently(data.get("overlay_transpose", True))
        self.toggle_ov_human_fail.toggle.setCheckedSilently(data.get("overlay_human_fail", True))
        self.toggle_ov_sustain.toggle.setCheckedSilently(data.get("overlay_sustain", True))