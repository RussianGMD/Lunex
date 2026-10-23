import os
import sys
import copy
import orjson
import requests
from PyQt6.QtCore import (
    Qt, QPoint, QTimer, qInstallMessageHandler
)
from PyQt6.QtGui import (
    QFont, QIcon, QPixmap, QIntValidator
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout,
    QVBoxLayout, QGridLayout, QLabel, QPushButton,
    QFileDialog, QSlider, QLineEdit, QProgressBar, QComboBox,
    QStackedWidget, QPlainTextEdit
)
from themes import (
    BLACK_THEME,
    ensure_example_theme, get_available_themes, resolve_theme_data
)
from load_midi import MidiLoader
from macro import MacroPlayer
from drag import MidiDropCard
from music import MusicView, ClickSound as MusicClickSound
from midihub import MidiHubView, HubSound
from miditoqwerty import MidiToQwertyView, ClickSound as ConverterClickSound
from settings_view import SettingsView, ClickSound, UpdateCheckerThread
from overlay import OverlayWindow
from debug_console import DebugConsoleWindow, ClickSound as DebugClickSound
from core_utils import (
    pitch_to_note_name, qt_message_handler, set_hidden_attribute,
    format_time, get_icon_path, GlobalHotkeyListener, SoundManager,
    truncate_text
)
from ui_components import SwitchRow, KeybindSlot, UpdateDialog

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
icon_path = os.path.join(BASE_DIR, "icon.ico")


class LunexWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(840, 620)
        self.setMinimumSize(720, 520)
        self.current_midi_data = None
        self.old_pos = None
        self.recent_midis = []
        self.is_white_theme = False
        self.current_theme_name = "Black (Standart)"
        self.current_theme_data = copy.deepcopy(BLACK_THEME)
        self.is_loading_state = True
        self._playback_stopped = True
        self.notes_up_count = 0
        self.is_counting_down = False
        self.remaining_countdown = 0
        self.start_timer = QTimer(self)
        self.start_timer.setInterval(1000)
        self.start_timer.timeout.connect(self._on_countdown_tick)

        local_appdata = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
        self.lunex_appdata_dir = os.path.abspath(os.path.join(local_appdata, "Lunex"))
        self.midis_dir = os.path.join(self.lunex_appdata_dir, "midis")
        self.save_dir = os.path.join(self.lunex_appdata_dir, "saves")
        self.themes_dir = os.path.join(self.lunex_appdata_dir, "themes")

        os.makedirs(self.midis_dir, exist_ok=True)
        os.makedirs(self.save_dir, exist_ok=True)
        os.makedirs(self.themes_dir, exist_ok=True)

        self.save_file = os.path.join(self.save_dir, "settings.json")
        self.example_theme_file = os.path.join(self.themes_dir, "example.json")
        ensure_example_theme(self.themes_dir, self.example_theme_file)

        self.overlay = OverlayWindow()
        self.player = MacroPlayer(self)
        self.player.finished.connect(self._on_player_finished)
        self.player.progress_changed.connect(self._on_progress_changed)
        self.player.notes_clicked.connect(self._on_notes_clicked)
        self.player.auto_paused.connect(self._on_player_auto_paused)
        self.player.sustain_changed.connect(self._on_sustain_changed)

        self.hotkey_listener = GlobalHotkeyListener(self)
        self.hotkey_listener.action_triggered.connect(self._on_global_hotkey)

        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        HubSound.play = SoundManager.play
        MusicClickSound.play = SoundManager.play
        ConverterClickSound.play = SoundManager.play
        DebugClickSound.play = SoundManager.play

        SoundManager.muted = True
        ClickSound.muted = True

        self._setup_ui()
        self._populate_theme_combo()
        self._load_saved_state()
        self._check_and_apply_halloween_theme()
        self._sync_hotkeys()
        self.hotkey_listener.start()

        SoundManager.muted = False
        ClickSound.muted = False
        self.is_loading_state = False

        self._sync_console_visibility()
        self._sync_overlay()

        self.startup_checker = UpdateCheckerThread(self)
        self.startup_checker.check_finished.connect(self._on_startup_update_checked)
        self.startup_checker.start()

    def _populate_theme_combo(self):
        if not hasattr(self, "settings_view"):
            return
        combo = self.settings_view.theme_row.combo
        current = combo.currentText() or "Black (Standart)"
        available = get_available_themes(self.themes_dir)
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(available)
        idx = combo.findText(current)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _setup_ui(self):
        self.central_widget = QWidget()
        self.central_widget.setObjectName("centralWidget")
        self.setCentralWidget(self.central_widget)

        root_layout = QVBoxLayout(self.central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._build_title_bar(root_layout)

        self.stack = QStackedWidget()

        self.home_view = self._create_home_view()
        self.music_view = MusicView()
        self.hub_view = MidiHubView()
        self.converter_view = MidiToQwertyView()
        self.settings_view = SettingsView()
        self.debug_console = DebugConsoleWindow()

        HubSound.play = SoundManager.play
        MusicClickSound.play = SoundManager.play
        ConverterClickSound.play = SoundManager.play
        DebugClickSound.play = SoundManager.play

        self.music_view.state_changed.connect(self._save_state)
        self.hub_view.midi_loaded.connect(self._on_hub_midi_loaded)
        self.converter_view.state_changed.connect(self._save_state)
        self.settings_view.state_changed.connect(self._on_settings_changed)
        self.settings_view.reset_recents_requested.connect(self._on_reset_all_recents)
        self.settings_view.open_debug_console_requested.connect(self._open_debug_console)
        self.settings_view.close_debug_console_requested.connect(self._close_debug_console)

        self.settings_view.toggle_human_fail.toggle.toggled.connect(
            lambda c: self._on_toggle_setting("Human Fail", c)
        )
        self.settings_view.toggle_perfectionist.toggle.toggled.connect(
            lambda c: self._on_toggle_setting("Perfectionist Mode", c)
        )
        self.settings_view.toggle_timer_start.toggle.toggled.connect(
            lambda c: self._on_toggle_setting("Timer Start", c)
        )
        self.settings_view.toggle_loop_song.toggle.toggled.connect(
            lambda c: self._on_toggle_setting("Loop Song", c)
        )
        self.settings_view.toggle_console.toggle.toggled.connect(
            lambda c: self._on_toggle_setting("Console", c)
        )
        self.settings_view.toggle_overlay.toggle.toggled.connect(
            lambda c: self._on_toggle_setting("Overlay Information", c)
        )
        self.settings_view.toggle_ov_speed.toggle.toggled.connect(
            lambda c: self._on_toggle_setting("Overlay Speed", c)
        )
        self.settings_view.toggle_ov_midi.toggle.toggled.connect(
            lambda c: self._on_toggle_setting("Overlay MIDI File", c)
        )
        self.settings_view.toggle_ov_notes.toggle.toggled.connect(
            lambda c: self._on_toggle_setting("Overlay Notes Up", c)
        )
        self.settings_view.toggle_ov_transpose.toggle.toggled.connect(
            lambda c: self._on_toggle_setting("Overlay Transpose", c)
        )
        self.settings_view.toggle_ov_human_fail.toggle.toggled.connect(
            lambda c: self._on_toggle_setting("Overlay Human Fail", c)
        )
        self.settings_view.toggle_ov_sustain.toggle.toggled.connect(
            lambda c: self._on_toggle_setting("Overlay Sustain", c)
        )

        self.stack.addWidget(self.home_view)
        self.stack.addWidget(self.music_view)
        self.stack.addWidget(self.hub_view)
        self.stack.addWidget(self.converter_view)
        self.stack.addWidget(self.settings_view)

        root_layout.addWidget(self.stack)

        self.apply_theme("Black (Standart)")

    def _build_title_bar(self, parent_layout):
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(44)
        layout = QHBoxLayout(self.title_bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        self.app_icon = QLabel()
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(
                18, 18,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.app_icon.setPixmap(pixmap)
        else:
            self.app_icon.setText("L")
            self.app_icon.setStyleSheet("color: #ffffff; font-size: 15px;")

        self.title_label = QLabel("Lunex")
        self.title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))

        nav_container = QWidget()
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(6)

        self.home_btn = QPushButton()
        self.music_btn = QPushButton()
        self.hub_btn = QPushButton()
        self.converter_btn = QPushButton()
        self.settings_btn = QPushButton()

        for btn in (self.home_btn, self.music_btn, self.hub_btn, self.converter_btn, self.settings_btn):
            btn.setFixedSize(32, 28)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.home_btn.clicked.connect(lambda: self._switch_tab(0))
        self.music_btn.clicked.connect(lambda: self._switch_tab(1))
        self.hub_btn.clicked.connect(lambda: self._switch_tab(2))
        self.converter_btn.clicked.connect(lambda: self._switch_tab(3))
        self.settings_btn.clicked.connect(lambda: self._switch_tab(4))

        nav_layout.addWidget(self.home_btn)
        nav_layout.addWidget(self.music_btn)
        nav_layout.addWidget(self.hub_btn)
        nav_layout.addWidget(self.converter_btn)
        nav_layout.addWidget(self.settings_btn)

        traffic_lights = QWidget()
        traffic_layout = QHBoxLayout(traffic_lights)
        traffic_layout.setContentsMargins(0, 0, 0, 0)
        traffic_layout.setSpacing(7)

        self.btn_min = QPushButton()
        self.btn_close = QPushButton()
        self.btn_min.setFixedSize(11, 11)
        self.btn_close.setFixedSize(11, 11)
        self.btn_min.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_min.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_min.setStyleSheet("""
            QPushButton {
                background-color: #ffbd2e;
                border: 1px solid #dea123;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #ffc957; }
        """)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #ff5f56;
                border: 1px solid #e0443e;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #ff7b73; }
        """)

        self.btn_min.clicked.connect(self._action_minimize)
        self.btn_close.clicked.connect(self._action_close)

        traffic_layout.addWidget(self.btn_min)
        traffic_layout.addWidget(self.btn_close)

        layout.addWidget(self.app_icon)
        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(nav_container)
        layout.addStretch()
        layout.addWidget(traffic_lights)

        parent_layout.addWidget(self.title_bar)

    def _is_any_console_open(self) -> bool:
        inline_open = hasattr(self, "settings_view") and self.settings_view.is_console_enabled()
        debug_open = (
            hasattr(self, "debug_console")
            and self.debug_console is not None
            and self.debug_console.isVisible()
        )
        return inline_open or debug_open

    def log_console(self, text: str):
        inline_open = hasattr(self, "settings_view") and self.settings_view.is_console_enabled()
        debug_open = (
            hasattr(self, "debug_console")
            and self.debug_console is not None
            and self.debug_console.isVisible()
        )
        if not inline_open and not debug_open:
            return
        if inline_open and hasattr(self, "console_box"):
            self.console_box.appendPlainText(text)
            scrollbar = self.console_box.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        if debug_open:
            self.debug_console.append_log(text)

    def _open_debug_console(self):
        if hasattr(self, "debug_console") and self.debug_console:
            self.debug_console.show()
            self.debug_console.raise_()
            self.debug_console.activateWindow()

    def _close_debug_console(self):
        if hasattr(self, "debug_console") and self.debug_console:
            self.debug_console.close()

    def _on_notes_clicked(self, pitches: list[int]):
        if not pitches:
            return
        self.notes_up_count += len(pitches)
        if hasattr(self, "overlay") and self.overlay:
            if self.overlay.isVisible():
                self.overlay.update_info(notes_up=self.notes_up_count)
            else:
                self.overlay.notes_up = self.notes_up_count
        if self._is_any_console_open():
            unique_pitches = list(dict.fromkeys(pitches))
            note_str = " + ".join(pitch_to_note_name(p) for p in unique_pitches)
            self.log_console(f"Clicked {note_str} Note.")

    def _on_sustain_changed(self, is_down: bool):
        if hasattr(self, "overlay") and self.overlay:
            self.overlay.update_info(sustain_active=is_down)

    def _on_toggle_setting(self, title: str, checked: bool):
        if not self.is_loading_state:
            action = "Enabled" if checked else "Disabled"
            self.log_console(f"{action} {title}.")
        self._save_state()
        self._sync_overlay()

    def _sync_overlay(self):
        if not hasattr(self, "overlay") or not self.overlay:
            return
        midi_name = self.current_midi_data.get("name", "None") if self.current_midi_data else "None"
        speed_val = self.speed_slider.value() if hasattr(self, "speed_slider") else 100
        transpose_val = self.settings_view.get_macro_transposition() if hasattr(self, "settings_view") else 0
        human_fail_enabled = (
            self.settings_view.toggle_human_fail.toggle.isChecked()
            if hasattr(self, "settings_view")
            else False
        )
        sustain_enabled = (
            self.toggle_sustain.toggle.isChecked()
            if hasattr(self, "toggle_sustain")
            else False
        )
        sustain_active = (
            bool(self.player.is_pedal_down)
            if (sustain_enabled and hasattr(self, "player"))
            else False
        )
        row_vis = (
            self.settings_view.get_overlay_row_settings()
            if hasattr(self, "settings_view")
            else {}
        )
        self.overlay.update_info(
            speed=speed_val,
            midi_name=midi_name,
            notes_up=self.notes_up_count,
            transpose=transpose_val,
            human_fail=human_fail_enabled,
            sustain_enabled=sustain_enabled,
            sustain_active=sustain_active,
            **row_vis,
        )
        if hasattr(self, "settings_view") and self.settings_view.is_overlay_enabled():
            if not self.overlay.isVisible():
                self.overlay.show()
        else:
            if self.overlay.isVisible():
                self.overlay.hide()

    def apply_click_sound(self, sound_name: str):
        SoundManager.set_sound(sound_name)

    def apply_theme(self, theme_name: str):
        self.current_theme_name = theme_name
        self.current_theme_data = resolve_theme_data(self.themes_dir, theme_name)
        self.is_white_theme = bool(self.current_theme_data.get("is_white", False))
        is_w = self.is_white_theme

        win_t = self.current_theme_data.get("window", BLACK_THEME["window"])
        tb_t = self.current_theme_data.get("title_bar", BLACK_THEME["title_bar"])
        mp_t = dict(self.current_theme_data.get("midi_player", BLACK_THEME["midi_player"]))
        mp_t["is_white"] = is_w
        music_t = dict(self.current_theme_data.get("music", BLACK_THEME["music"]))
        music_t["is_white"] = is_w
        hub_t = dict(self.current_theme_data.get("midihub", BLACK_THEME["midihub"]))
        hub_t["is_white"] = is_w
        converter_t = dict(self.current_theme_data.get("converter", BLACK_THEME["converter"]))
        converter_t["is_white"] = is_w
        settings_t = dict(self.current_theme_data.get("settings", BLACK_THEME["settings"]))
        settings_t["is_white"] = is_w
        debug_t = dict(self.current_theme_data.get("debug_console", BLACK_THEME["debug_console"]))
        debug_t["is_white"] = is_w
        overlay_t = dict(self.current_theme_data.get("overlay", BLACK_THEME["overlay"]))
        overlay_t["is_white"] = is_w

        btn_configs = [
            (self.home_btn, "home", 0.5),
            (self.music_btn, "music", 0.55),
            (self.hub_btn, "hub", 0.55),
            (self.converter_btn, "converter", 0.55),
            (self.settings_btn, "settings", 0.55),
        ]
        for btn, base_icon, scale in btn_configs:
            path = get_icon_path(base_icon, is_white=is_w)
            if os.path.exists(path):
                btn.setIcon(QIcon(path))
                btn.setIconSize(btn.size() * scale)
                btn.setText("")
            else:
                fallbacks = {"home": "H", "music": "M", "hub": "U", "converter": "C", "settings": "S"}
                btn.setText(fallbacks.get(base_icon, ""))

        self.central_widget.setStyleSheet(f"""
            #centralWidget {{
                background-color: {win_t.get("bg", "#0c0c0e")};
                border: 1px solid {win_t.get("border", "#1f1f24")};
                border-radius: 10px;
            }}
        """)
        self.title_bar.setStyleSheet(
            f"background: transparent; border-bottom: 1px solid {tb_t.get('border_bottom', '#18181c')};"
        )
        self.title_label.setStyleSheet(f"color: {tb_t.get('title_text', '#ffffff')}; padding-left: 2px;")

        sec_col = mp_t.get("section_header_text", "#7b7b8a")
        sub_col = mp_t.get("sub_header_text", "#636370")
        self.midi_card_header.setStyleSheet(f"color: {sec_col}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        self.keybinds_header.setStyleSheet(f"color: {sec_col}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        self.settings_header.setStyleSheet(f"color: {sec_col}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; margin-bottom: 2px;")
        self.speed_title.setStyleSheet(f"color: {sec_col}; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
        self.time_title.setStyleSheet(f"color: {sec_col}; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
        self.console_header.setStyleSheet(f"color: {sec_col}; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
        self.path_title.setStyleSheet(f"color: {sub_col}; font-size: 10px; font-weight: bold;")
        self.recent_title.setStyleSheet(f"color: {sub_col}; font-size: 10px; font-weight: bold;")

        if self.current_midi_data:
            self.path_label.setStyleSheet(
                f"color: {mp_t.get('path_text_loaded', '#3b82f6')}; font-size: 12px; font-weight: 500;"
            )
        else:
            self.path_label.setStyleSheet(
                f"color: {mp_t.get('path_text_idle', '#9d9da8')}; font-size: 12px;"
            )
        self.status_label.setStyleSheet(
            f"color: {mp_t.get('status_error_text', '#ef4444')}; font-size: 12px; font-weight: 600;"
        )

        self.midi_card.set_theme(mp_t)
        self.keybinds_card.setStyleSheet(f"""
            QWidget#keybindsCard {{
                background-color: {mp_t.get("card_bg", "#16161a")};
                border: 1px solid {mp_t.get("card_border", "#23232a")};
                border-radius: 7px;
            }}
        """)
        self.select_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {mp_t.get("select_btn_bg", "#202026")};
                color: {mp_t.get("select_btn_text", "#ffffff")};
                border: 1px solid {mp_t.get("select_btn_border", "#2c2c36")};
                border-radius: 5px;
                font-size: 12px;
                font-weight: 500;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background-color: {mp_t.get("select_btn_hover_bg", "#2b2b34")};
                border: 1px solid {mp_t.get("select_btn_hover_border", "#3d3d4a")};
            }}
            QPushButton:pressed {{
                background-color: {mp_t.get("select_btn_pressed_bg", "#1a1a20")};
            }}
        """)
        self.recent_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {mp_t.get("combo_bg", "#1a1a20")};
                color: {mp_t.get("combo_text", "#c9c9d4")};
                border: 1px solid {mp_t.get("combo_border", "#282832")};
                border-radius: 5px;
                padding-left: 10px;
                font-size: 9pt;
                font-weight: 500;
            }}
            QComboBox:hover {{
                border: 1px solid {mp_t.get("combo_hover_border", "#3b82f6")};
                color: {mp_t.get("combo_hover_text", "#ffffff")};
            }}
            QComboBox::drop-down {{ border: none; width: 0px; }}
            QComboBox QAbstractItemView {{
                background-color: {mp_t.get("combo_popup_bg", "#16161a")};
                color: {mp_t.get("combo_popup_text", "#e1e1e6")};
                selection-background-color: {mp_t.get("combo_selection_bg", "#26334d")};
                selection-color: {mp_t.get("combo_selection_text", "#60a5fa")};
                border: 1px solid {mp_t.get("combo_popup_border", "#2c2c38")};
                border-radius: 5px;
                padding: 4px;
                font-size: 9pt;
                outline: none;
            }}
        """)
        self.speed_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {mp_t.get("input_bg", "#16161a")};
                color: {mp_t.get("input_text", "#ffffff")};
                border: 1px solid {mp_t.get("input_border", "#23232a")};
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
            }}
            QLineEdit:focus {{
                border: 1px solid {mp_t.get("input_focus_border", "#3b82f6")};
            }}
        """)
        self.speed_slider.setStyleSheet(f"""
            QSlider {{ height: 26px; }}
            QSlider::groove:horizontal {{
                height: 5px;
                background-color: {mp_t.get("slider_groove_bg", "#16161a")};
                border: 1px solid {mp_t.get("slider_groove_border", "#23232a")};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background-color: {mp_t.get("slider_subpage_bg", "#3b82f6")};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background-color: {mp_t.get("slider_handle_bg", "#ffffff")};
                border: {mp_t.get("slider_handle_border", "none")};
                width: 12px; height: 12px; margin: -3px 0; border-radius: 6px;
            }}
            QSlider::handle:horizontal:hover {{
                background-color: {mp_t.get("slider_handle_hover_bg", "#e2e8f0")};
            }}
        """)
        self.time_label.setStyleSheet(
            f"color: {mp_t.get('time_label_text', '#8f8f9d')}; font-size: 11px; font-weight: 600;"
        )
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {mp_t.get("progress_bg", "#16161a")};
                border: 1px solid {mp_t.get("progress_border", "#23232a")};
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {mp_t.get("progress_chunk", "#3b82f6")};
                border-radius: 2px;
            }}
        """)
        self.console_box.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {mp_t.get("console_bg", "#16161a")};
                color: {mp_t.get("console_text", "#e1e1e6")};
                border: 1px solid {mp_t.get("console_border", "#23232a")};
                border-radius: 6px;
                padding: 6px;
                font-family: 'Consolas', 'Segoe UI', monospace;
                font-size: 8.5pt;
            }}
        """)

        btn_action_style = f"""
            QPushButton {{
                background-color: {mp_t.get("action_btn_bg", "#16161a")};
                color: {mp_t.get("action_btn_text", "#ffffff")};
                border: 1px solid {mp_t.get("action_btn_border", "#23232a")};
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
                height: 30px;
            }}
            QPushButton:hover {{
                background-color: {mp_t.get("action_btn_hover_bg", "#202026")};
                border: 1px solid {mp_t.get("action_btn_hover_border", "#32323d")};
            }}
            QPushButton:pressed {{
                background-color: {mp_t.get("action_btn_pressed_bg", "#121216")};
            }}
            QPushButton:disabled {{
                background-color: {mp_t.get("action_btn_disabled_bg", "rgba(228, 228, 231, 0.25)")};
                color: {mp_t.get("action_btn_disabled_text", "rgba(255, 255, 255, 0.2)")};
                border: 1px solid {mp_t.get("action_btn_disabled_border", "rgba(35, 35, 42, 0.25)")};
            }}
        """
        for btn in (self.btn_start, self.btn_pause, self.btn_end):
            btn.setStyleSheet(btn_action_style)

        for row in (
            self.toggle_no_doubles, self.toggle_velocity, self.toggle_88_keys,
            self.toggle_sustain, self.toggle_accurate_gate, self.toggle_speed_protection
        ):
            row.set_theme(mp_t)

        for slot in (self.bind_start, self.bind_pause, self.bind_end, self.bind_speed_down, self.bind_speed_up):
            slot.set_theme(mp_t)

        self._update_tab_buttons_style(self.stack.currentIndex())
        self.music_view.set_theme(music_t)
        self.hub_view.set_theme(hub_t)
        self.converter_view.set_theme(converter_t)
        self.settings_view.set_theme(settings_t)
        if hasattr(self, "debug_console") and self.debug_console:
            self.debug_console.set_theme(debug_t)
        if hasattr(self, "overlay") and self.overlay:
            self.overlay.set_theme(overlay_t)

    def _update_tab_buttons_style(self, current_index: int):
        tb_t = self.current_theme_data.get("title_bar", BLACK_THEME["title_bar"])
        active_style = f"""
            QPushButton {{
                background-color: {tb_t.get("tab_active_bg", "#202028")};
                border: 1px solid {tb_t.get("tab_active_border", "#3b82f6")};
                border-radius: 5px;
                color: {tb_t.get("tab_active_text", "#ffffff")};
                font-size: 13px;
            }}
        """
        inactive_style = f"""
            QPushButton {{
                background-color: {tb_t.get("tab_inactive_bg", "#1a1a20")};
                border: 1px solid {tb_t.get("tab_inactive_border", "#2a2a34")};
                border-radius: 5px;
                color: {tb_t.get("tab_inactive_text", "#8f8f9d")};
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {tb_t.get("tab_inactive_hover_bg", "#262630")};
                color: {tb_t.get("tab_inactive_hover_text", "#ffffff")};
            }}
        """
        self.home_btn.setStyleSheet(active_style if current_index == 0 else inactive_style)
        self.music_btn.setStyleSheet(active_style if current_index == 1 else inactive_style)
        self.hub_btn.setStyleSheet(active_style if current_index == 2 else inactive_style)
        self.converter_btn.setStyleSheet(active_style if current_index == 3 else inactive_style)
        self.settings_btn.setStyleSheet(active_style if current_index == 4 else inactive_style)

    def _switch_tab(self, index: int):
        SoundManager.play()
        if index == 4:
            self._populate_theme_combo()
        self.stack.setCurrentIndex(index)
        self._update_tab_buttons_style(index)
        self._sync_hotkeys()

    def _on_hub_midi_loaded(self, local_midi_path: str):
        self._load_midi_file(local_midi_path)
        self._switch_tab(0)

    def _sync_console_visibility(self):
        if hasattr(self, "console_container") and hasattr(self, "settings_view"):
            self.console_container.setVisible(self.settings_view.is_console_enabled())

    def _on_settings_changed(self):
        self.apply_click_sound(self.settings_view.get_click_sound())
        self._save_state()
        new_theme = self.settings_view.get_theme()
        self.apply_theme(new_theme)
        self._sync_console_visibility()
        self._sync_overlay()

    def _on_reset_all_recents(self):
        self.recent_midis = []
        self._update_recent_combo()
        self.music_view.recent_midis = []
        self.music_view._update_recent_combo()
        self.converter_view.recent_midis = []
        self.converter_view._update_recent_combo()
        self._save_state()

    def _create_home_view(self) -> QWidget:
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(18, 16, 18, 16)
        content_layout.setSpacing(18)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        self.midi_card_header = QLabel("MIDI")
        left_layout.addWidget(self.midi_card_header)

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
        self.keybinds_card.setObjectName("keybindsCard")
        keybinds_grid = QGridLayout(self.keybinds_card)
        keybinds_grid.setContentsMargins(12, 12, 12, 12)
        keybinds_grid.setHorizontalSpacing(10)
        keybinds_grid.setVerticalSpacing(10)

        self.bind_start = KeybindSlot("Start", "F1")
        self.bind_pause = KeybindSlot("Pause", "F2")
        self.bind_end = KeybindSlot("End", "F3")
        self.bind_speed_down = KeybindSlot("Speed Down", "F4")
        self.bind_speed_up = KeybindSlot("Speed Up", "F5")

        for slot in (self.bind_start, self.bind_pause, self.bind_end, self.bind_speed_down, self.bind_speed_up):
            slot.button.key_changed.connect(self._on_keybind_changed)

        keybinds_grid.addWidget(self.bind_start, 0, 0)
        keybinds_grid.addWidget(self.bind_pause, 0, 1)
        keybinds_grid.addWidget(self.bind_end, 0, 2)
        keybinds_grid.addWidget(self.bind_speed_down, 1, 0)
        keybinds_grid.addWidget(self.bind_speed_up, 1, 1)

        left_layout.addWidget(self.keybinds_card)
        left_layout.addStretch()

        self.status_label = QLabel("")
        left_layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignLeft)

        content_layout.addWidget(left_panel, stretch=3)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.settings_header = QLabel("PLAYBACK SETTINGS")
        right_layout.addWidget(self.settings_header)

        self.toggle_no_doubles = SwitchRow("No Doubles")
        self.toggle_velocity = SwitchRow("Velocity")
        self.toggle_88_keys = SwitchRow("88 Keys")
        self.toggle_sustain = SwitchRow("Sustain")
        self.toggle_accurate_gate = SwitchRow("Accurate Gate")
        self.toggle_accurate_gate.toggle.setCheckedSilently(True)
        self.toggle_speed_protection = SwitchRow("Speed Protection")

        self.toggle_no_doubles.toggle.toggled.connect(lambda c: self._on_toggle_setting("No Doubles", c))
        self.toggle_velocity.toggle.toggled.connect(lambda c: self._on_toggle_setting("Velocity", c))
        self.toggle_88_keys.toggle.toggled.connect(lambda c: self._on_toggle_setting("88 Keys", c))
        self.toggle_sustain.toggle.toggled.connect(lambda c: self._on_toggle_setting("Sustain", c))
        self.toggle_accurate_gate.toggle.toggled.connect(lambda c: self._on_toggle_setting("Accurate Gate", c))
        self.toggle_speed_protection.toggle.toggled.connect(lambda c: self._on_toggle_setting("Speed Protection", c))

        right_layout.addWidget(self.toggle_no_doubles)
        right_layout.addWidget(self.toggle_velocity)
        right_layout.addWidget(self.toggle_88_keys)
        right_layout.addWidget(self.toggle_sustain)
        right_layout.addWidget(self.toggle_accurate_gate)
        right_layout.addWidget(self.toggle_speed_protection)

        self.console_container = QWidget()
        self.console_container.setObjectName("consoleContainer")
        console_layout = QVBoxLayout(self.console_container)
        console_layout.setContentsMargins(0, 4, 0, 0)
        console_layout.setSpacing(4)

        self.console_header = QLabel("CONSOLE")
        console_layout.addWidget(self.console_header)

        self.console_box = QPlainTextEdit()
        self.console_box.setReadOnly(True)
        self.console_box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.console_box.setMaximumBlockCount(1000)
        self.console_box.setFixedHeight(120)
        console_layout.addWidget(self.console_box)

        right_layout.addWidget(self.console_container)
        self.console_container.setVisible(False)

        right_layout.addStretch()

        speed_box = QVBoxLayout()
        speed_box.setSpacing(4)
        self.speed_title = QLabel("SPEED")
        speed_box.addWidget(self.speed_title)

        speed_row = QHBoxLayout()
        speed_row.setSpacing(8)

        self.speed_input = QLineEdit("100")
        self.speed_input.setFixedSize(48, 26)
        self.speed_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.speed_input.setValidator(QIntValidator(0, 1000, self))

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(0, 1000)
        self.speed_slider.setValue(100)
        self.speed_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.speed_slider.setCursor(Qt.CursorShape.PointingHandCursor)

        self.speed_slider.valueChanged.connect(self._on_slider_changed)
        self.speed_input.editingFinished.connect(self._on_input_changed)

        speed_row.addWidget(self.speed_input)
        speed_row.addWidget(self.speed_slider)
        speed_box.addLayout(speed_row)
        right_layout.addLayout(speed_box)

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

        return content

    def _on_startup_update_checked(self, is_latest: bool, remote_ver: str):
        if not is_latest and remote_ver:
            self._show_update_dialog()

    def _show_update_dialog(self):
        dlg_theme = self.current_theme_data.get("update_dialog", BLACK_THEME["update_dialog"])
        dlg = UpdateDialog(self, theme_data=dlg_theme)
        geo = self.geometry()
        x = geo.x() + (geo.width() - dlg.width()) // 2
        y = geo.y() + (geo.height() - dlg.height()) // 2
        dlg.move(x, y)
        dlg.exec()

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
            display_name = truncate_text(os.path.basename(path), 50)
            self.recent_combo.addItem(display_name, path)

        if self.current_midi_data:
            current_path = os.path.normcase(os.path.abspath(self.current_midi_data["path"]))
            for i in range(1, self.recent_combo.count()):
                stored_path = self.recent_combo.itemData(i)
                if stored_path and os.path.normcase(os.path.abspath(stored_path)) == current_path:
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
            self._save_state()
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

    def _save_state(self):
        try:
            os.makedirs(self.save_dir, exist_ok=True)
            self._clean_recent_list()
            data = {
                "recent_midis": self.recent_midis,
                "last_midi_path": self.current_midi_data["path"] if self.current_midi_data else None,
                "toggles": {
                    "no_doubles": self.toggle_no_doubles.toggle.isChecked(),
                    "velocity": self.toggle_velocity.toggle.isChecked(),
                    "keys_88": self.toggle_88_keys.toggle.isChecked(),
                    "sustain": self.toggle_sustain.toggle.isChecked(),
                    "accurate_gate": self.toggle_accurate_gate.toggle.isChecked(),
                    "speed_protection": self.toggle_speed_protection.toggle.isChecked(),
                },
                "speed": self.speed_slider.value(),
                "keybinds": {
                    "start": self.bind_start.button.key_value,
                    "pause": self.bind_pause.button.key_value,
                    "end": self.bind_end.button.key_value,
                    "speed_down": self.bind_speed_down.button.key_value,
                    "speed_up": self.bind_speed_up.button.key_value,
                },
                "music_tab": self.music_view.get_save_data(),
                "converter_tab": self.converter_view.get_save_data(),
                "settings_tab": self.settings_view.get_save_data()
            }
            set_hidden_attribute(self.save_file, hidden=False)
            with open(self.save_file, "wb") as f:
                f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))
            set_hidden_attribute(self.save_file, hidden=True)
        except Exception:
            pass

    def _check_and_apply_halloween_theme(self):
        marker_file = os.path.join(self.save_dir, ".halloween_applied")
        if os.path.isfile(marker_file):
            return
        url = "https://raw.githubusercontent.com/RussianGMD/iuerfh/refs/heads/main/halloween.json"
        halloween_file = os.path.join(self.themes_dir, "halloween.json")
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                with open(halloween_file, "wb") as f:
                    f.write(resp.content)
                with open(marker_file, "w", encoding="utf-8") as f:
                    f.write("applied")
                set_hidden_attribute(marker_file, hidden=True)
                self._populate_theme_combo()
                combo = self.settings_view.theme_row.combo
                idx = combo.findText("halloween.json")
                if idx >= 0:
                    combo.blockSignals(True)
                    combo.setCurrentIndex(idx)
                    combo.blockSignals(False)
                self.apply_theme("halloween.json")
                self._save_state()
                self.log_console("Happy Halloween! Applied Halloween Theme.")
        except Exception:
            pass

    def _load_saved_state(self):
        if not os.path.isfile(self.save_file):
            self._update_recent_combo()
            return
        try:
            with open(self.save_file, "rb") as f:
                data = orjson.loads(f.read())
            if not isinstance(data, dict):
                self._update_recent_combo()
                return

            self.recent_midis = data.get("recent_midis", [])
            self._clean_recent_list()

            toggles = data.get("toggles", {})
            if "no_doubles" in toggles:
                self.toggle_no_doubles.toggle.setCheckedSilently(toggles["no_doubles"])
            if "velocity" in toggles:
                self.toggle_velocity.toggle.setCheckedSilently(toggles["velocity"])
            if "keys_88" in toggles:
                self.toggle_88_keys.toggle.setCheckedSilently(toggles["keys_88"])
            if "sustain" in toggles:
                self.toggle_sustain.toggle.setCheckedSilently(toggles["sustain"])
            if "accurate_gate" in toggles:
                self.toggle_accurate_gate.toggle.setCheckedSilently(toggles["accurate_gate"])
            if "speed_protection" in toggles:
                self.toggle_speed_protection.toggle.setCheckedSilently(toggles["speed_protection"])

            saved_speed = data.get("speed", 100)
            self._set_speed_value(saved_speed)

            binds = data.get("keybinds", {})
            if "start" in binds:
                self.bind_start.button.set_key_silently(binds["start"])
            if "pause" in binds:
                self.bind_pause.button.set_key_silently(binds["pause"])
            if "end" in binds:
                self.bind_end.button.set_key_silently(binds["end"])
            if "speed_down" in binds:
                self.bind_speed_down.button.set_key_silently(binds["speed_down"])
            if "speed_up" in binds:
                self.bind_speed_up.button.set_key_silently(binds["speed_up"])

            last_path = data.get("last_midi_path")
            if last_path and os.path.isfile(last_path):
                self._load_midi_file(last_path, silent=True)
            else:
                self._update_recent_combo()

            if "music_tab" in data:
                self.music_view.load_save_data(data["music_tab"])
            if "converter_tab" in data:
                self.converter_view.load_save_data(data["converter_tab"])
            if "settings_tab" in data:
                self._populate_theme_combo()
                self.settings_view.load_save_data(data["settings_tab"])
                saved_theme = data["settings_tab"].get("app_theme", "Black (Standart)")
                if self.settings_view.theme_row.combo.findText(saved_theme) < 0:
                    saved_theme = "Black (Standart)"
                    self.settings_view.theme_row.combo.blockSignals(True)
                    self.settings_view.theme_row.combo.setCurrentIndex(0)
                    self.settings_view.theme_row.combo.blockSignals(False)
                self.apply_theme(saved_theme)
                saved_sound = data["settings_tab"].get("click_sound", "Click")
                self.apply_click_sound(saved_sound)
        except Exception:
            self._update_recent_combo()

    def _on_keybind_changed(self):
        self._sync_hotkeys()
        self._save_state()

    def _sync_hotkeys(self):
        if self.stack.currentIndex() == 0:
            self.hotkey_listener.update_bindings({
                "start": self.bind_start.button.key_value,
                "pause": self.bind_pause.button.key_value,
                "end": self.bind_end.button.key_value,
                "speed_down": self.bind_speed_down.button.key_value,
                "speed_up": self.bind_speed_up.button.key_value,
            })
        elif self.stack.currentIndex() == 1:
            self.hotkey_listener.update_bindings(self.music_view.get_bindings())
        else:
            self.hotkey_listener.update_bindings({})

    def _on_global_hotkey(self, action: str):
        if self.stack.currentIndex() == 1:
            self.music_view.trigger_action(action)
            return
        if self.stack.currentIndex() in (2, 3, 4):
            return
        if any(slot.button.is_listening for slot in (
            self.bind_start, self.bind_pause, self.bind_end,
            self.bind_speed_down, self.bind_speed_up
        )):
            return

        if action == "start":
            if not self.current_midi_data:
                self._show_error("MIDI File not Loaded!")
            elif self.btn_start.isEnabled():
                self._on_start_clicked()
        elif action == "pause":
            if not self.current_midi_data:
                self._show_error("MIDI File not Loaded!")
            elif self.btn_pause.isEnabled():
                self._on_pause_clicked()
        elif action == "end":
            if not self.current_midi_data:
                self._show_error("MIDI File not Loaded!")
            elif self.btn_end.isEnabled():
                self._on_end_clicked()
        elif action == "speed_down":
            SoundManager.play()
            step = self.settings_view.get_speed_hotkey_step()
            self._set_speed_value(self.speed_slider.value() - step)
        elif action == "speed_up":
            SoundManager.play()
            step = self.settings_view.get_speed_hotkey_step()
            self._set_speed_value(self.speed_slider.value() + step)

    def _set_speed_value(self, val: int):
        val = max(0, min(1000, val))
        self.speed_slider.blockSignals(True)
        self.speed_slider.setValue(val)
        self.speed_slider.blockSignals(False)
        self.speed_input.setText(str(val))
        self.player.set_speed(val)
        if hasattr(self, "overlay") and self.overlay:
            self.overlay.update_info(speed=val)
        self._save_state()

    def _on_slider_changed(self, val: int):
        self.speed_input.setText(str(val))
        self.player.set_speed(val)
        if hasattr(self, "overlay") and self.overlay:
            self.overlay.update_info(speed=val)
        self._save_state()

    def _on_input_changed(self):
        text = self.speed_input.text()
        val = int(text) if text.isdigit() else 100
        self._set_speed_value(val)

    def _on_progress_changed(self, current_sec: float):
        if not self.current_midi_data:
            return
        total_sec = float(self.current_midi_data.get("duration", 0.0))
        if total_sec > 0:
            ratio = min(1.0, current_sec / total_sec)
            self.progress_bar.setValue(int(ratio * 1000))
            self.time_label.setText(f"{format_time(current_sec)} / {format_time(total_sec)}")

    def _load_midi_file(self, file_path: str, silent: bool = False):
        mp_t = self.current_theme_data.get("midi_player", BLACK_THEME["midi_player"])
        try:
            real_path = os.path.abspath(file_path)
            norm_target = os.path.normcase(real_path)
            self.current_midi_data = MidiLoader.load(real_path)
            self.path_label.setText(truncate_text(self.current_midi_data["path"], 50))
            self.path_label.setToolTip(self.current_midi_data["path"])
            self.path_label.setStyleSheet(
                f"color: {mp_t.get('path_text_loaded', '#3b82f6')}; font-size: 12px; font-weight: 500;"
            )
            self.status_label.setText("")
            total_dur = self.current_midi_data.get("duration", 0.0)
            self.time_label.setText(f"0:00:00 / {format_time(total_dur)}")
            self.progress_bar.setValue(0)
            self.btn_start.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_end.setEnabled(False)
            self.btn_pause.setText("Pause")
            self.notes_up_count = 0
            if hasattr(self, "overlay") and self.overlay:
                self.overlay.update_info(
                    midi_name=self.current_midi_data.get("name", "None"),
                    notes_up=0,
                    sustain_active=False,
                )
            self.recent_midis = [p for p in self.recent_midis if os.path.normcase(os.path.abspath(p)) != norm_target]
            self.recent_midis.insert(0, real_path)
            self._update_recent_combo()
            if not silent:
                self._save_state()
                self.log_console("Loaded MIDI File.")
        except Exception as e:
            self.path_label.setText(f"Error: {str(e)}")
            self.path_label.setStyleSheet(
                f"color: {mp_t.get('path_text_error', '#ff5f56')}; font-size: 12px;"
            )
            self._reset_to_idle()
            self.log_console("Failed Loading MIDI File.")

    def _select_file(self):
        SoundManager.play()
        file_path, _ = QFileDialog.getOpenFileName(self, "Select MIDI File", "", "MIDI Files (*.mid)")
        if file_path:
            self._load_midi_file(file_path)

    def _reset_to_idle(self):
        if self.is_counting_down:
            self.is_counting_down = False
            if hasattr(self, "start_timer") and self.start_timer.isActive():
                self.start_timer.stop()
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
        self.notes_up_count = 0
        if hasattr(self, "overlay") and self.overlay:
            midi_name = self.current_midi_data.get("name", "None") if self.current_midi_data else "None"
            self.overlay.update_info(midi_name=midi_name, notes_up=0, sustain_active=False)

    def _show_error(self, text: str):
        self.status_label.setText(text)
        QTimer.singleShot(3000, lambda: self.status_label.setText("") if self.status_label.text() == text else None)

    def _on_start_clicked(self):
        SoundManager.play()
        if not self.current_midi_data:
            self._show_error("MIDI File not Loaded!")
            return
        self.player.stop_playback()
        self.notes_up_count = 0
        if hasattr(self, "overlay") and self.overlay:
            self.overlay.update_info(notes_up=0, sustain_active=False)
        if self.settings_view.is_timer_start_enabled():
            timer_sec = self.settings_view.get_timer_seconds()
            if timer_sec > 0:
                self.is_counting_down = True
                self.remaining_countdown = timer_sec
                self.btn_start.setEnabled(False)
                self.btn_pause.setEnabled(False)
                self.btn_end.setEnabled(True)
                self._playback_stopped = False
                if self.remaining_countdown == 1:
                    self.log_console("Starting in 1..")
                else:
                    self.log_console(f"Starting in {self.remaining_countdown}")
                self.start_timer.start()
                return
        self._execute_start_playback()

    def _on_countdown_tick(self):
        if not self.is_counting_down:
            self.start_timer.stop()
            return
        self.remaining_countdown -= 1
        if self.remaining_countdown > 1:
            self.log_console(f"Starting in {self.remaining_countdown}")
        elif self.remaining_countdown == 1:
            self.log_console("Starting in 1..")
        else:
            self.start_timer.stop()
            self.is_counting_down = False
            self._execute_start_playback()

    def _execute_start_playback(self):
        self.notes_up_count = 0
        sustain_enabled = self.toggle_sustain.toggle.isChecked()
        settings_data = self.settings_view.get_save_data()
        transpose_val = settings_data.get("macro_transposition", 0)
        human_fail_enabled = settings_data.get("human_fail", False)
        if hasattr(self, "overlay") and self.overlay:
            self.overlay.update_info(
                notes_up=0,
                transpose=transpose_val,
                human_fail=human_fail_enabled,
                sustain_enabled=sustain_enabled,
                sustain_active=False,
            )
        self.player.set_midi_data(self.current_midi_data)
        self.player.set_speed(self.speed_slider.value())
        self.player.set_settings(
            no_doubles=self.toggle_no_doubles.toggle.isChecked(),
            velocity=self.toggle_velocity.toggle.isChecked(),
            keys88=self.toggle_88_keys.toggle.isChecked(),
            sustain=sustain_enabled,
            accurate_gate=self.toggle_accurate_gate.toggle.isChecked(),
            speed_protection=self.toggle_speed_protection.toggle.isChecked()
        )
        self.player.set_human_fail_settings(
            enabled=human_fail_enabled,
            speed_fail_pct=settings_data.get("speed_fail_pct", 1.0),
            transpose_fail_pct=settings_data.get("transpose_fail_pct", 5.0),
            speed_fail_min=settings_data.get("speed_fail_min", 0.8),
            speed_fail_max=settings_data.get("speed_fail_max", 1.2),
            speed_fail_slow_pct=settings_data.get("speed_fail_slow_pct", 50.0),
            speed_fail_fast_pct=settings_data.get("speed_fail_fast_pct", 50.0),
            perfectionist_mode=settings_data.get("perfectionist_mode", False),
            transpose_fail_mode=settings_data.get("transpose_fail_mode", "Tick Fail"),
            transpose_fail_delay_ms=settings_data.get("transpose_fail_delay_ms", 500),
            fail_notes_count=settings_data.get("fail_notes_count", 1)
        )
        self.player.set_loop_song(settings_data.get("loop_song", False))
        self.player.set_transposition(transpose_val)
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_pause.setText("Pause")
        self.btn_end.setEnabled(True)
        self._playback_stopped = False
        self.log_console("Started Playback.")
        self.player.start()

    def _on_player_auto_paused(self):
        self.btn_pause.setText("Continue")
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_end.setEnabled(True)
        if hasattr(self, "overlay") and self.overlay:
            self.overlay.update_info(sustain_active=False)
        self.log_console("Paused Playback.")

    def _on_pause_clicked(self):
        SoundManager.play()
        if not self.current_midi_data:
            self._show_error("MIDI File not Loaded!")
            return
        if not self.player.is_playing:
            return
        if self.player.is_paused:
            self.player.resume()
            self.btn_pause.setText("Pause")
            self.log_console("Resumed Playback.")
        else:
            self.player.pause()
            self.btn_pause.setText("Continue")
            if hasattr(self, "overlay") and self.overlay:
                self.overlay.update_info(sustain_active=False)
            self.log_console("Paused Playback.")
        self.btn_start.setEnabled(False)
        self.btn_end.setEnabled(True)

    def _on_end_clicked(self):
        SoundManager.play()
        if not self.current_midi_data:
            self._show_error("MIDI File not Loaded!")
            return
        if self.is_counting_down:
            self.is_counting_down = False
            if hasattr(self, "start_timer") and self.start_timer.isActive():
                self.start_timer.stop()
            if not self._playback_stopped:
                self._playback_stopped = True
                self.log_console("Stopped Playback.")
            self._reset_to_idle()
            return
        if not self._playback_stopped:
            self._playback_stopped = True
            self.log_console("Stopped Playback.")
        self.player.stop_playback()
        self._reset_to_idle()

    def _on_player_finished(self):
        if not self._playback_stopped:
            self._playback_stopped = True
            self.log_console("Stopped Playback.")
        self._reset_to_idle()

    def _action_minimize(self):
        SoundManager.play()
        self.showMinimized()

    def _action_close(self):
        SoundManager.play()
        self._save_state()
        self.hotkey_listener.stop()
        if hasattr(self, "start_timer") and self.start_timer.isActive():
            self.start_timer.stop()
        self.player.stop_playback()
        self.music_view.stop_playback()
        if hasattr(self, "debug_console") and self.debug_console:
            self.debug_console.close()
        if hasattr(self, "overlay") and self.overlay:
            self.overlay.close()
        self.close()

    def closeEvent(self, event):
        self._save_state()
        if hasattr(self, "start_timer") and self.start_timer.isActive():
            self.start_timer.stop()
        self.music_view.stop_playback()
        if hasattr(self, "debug_console") and self.debug_console:
            self.debug_console.close()
        if hasattr(self, "overlay") and self.overlay:
            self.overlay.close()
        super().closeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 44:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None


if __name__ == "__main__":
    qInstallMessageHandler(qt_message_handler)
    app = QApplication(sys.argv)
    SoundManager.init("Click")
    ClickSound.init("Click")
    window = LunexWindow()
    window.show()
    sys.exit(app.exec())
