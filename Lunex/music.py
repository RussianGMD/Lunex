import os
import time
import ctypes
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QKeySequence, QIntValidator
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel, 
    QPushButton, QFileDialog, QProgressBar, QComboBox,
    QSlider, QLineEdit
)
from PyQt6.QtMultimedia import QSoundEffect

from load_midi import MidiLoader
from drag import MidiDropCard

try:
    import rtmidi
except ImportError:
    rtmidi = None

winmm = ctypes.windll.winmm


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


class AutoRefreshComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.refresh_callback = None

    def showPopup(self):
        if self.refresh_callback:
            self.refresh_callback()
        super().showPopup()


class KeybindButton(QPushButton):
    key_changed = pyqtSignal()

    def __init__(self, default_key: str, parent=None):
        super().__init__(parent)
        self.key_value = default_key
        self.is_listening = False
        self.is_white = False
        self.setFixedHeight(30)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_appearance()

    def set_theme(self, is_white: bool):
        self.is_white = is_white
        self._update_appearance()

    def set_key_silently(self, key_text: str):
        self.key_value = key_text.upper()
        self._update_appearance()

    def _update_appearance(self):
        if self.is_listening:
            self.setText("...")
            self.setStyleSheet("""
                QPushButton {
                    background-color: #182234;
                    color: #60a5fa;
                    border: 1px solid #3b82f6;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                }
            """)
        else:
            self.setText(self.key_value)
            if self.is_white:
                self.setStyleSheet("""
                    QPushButton {
                        background-color: #f4f4f7;
                        color: #18181b;
                        border: 1px solid #d4d4d8;
                        border-radius: 5px;
                        font-size: 12px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #e4e4e7;
                        border: 1px solid #3b82f6;
                    }
                """)
            else:
                self.setStyleSheet("""
                    QPushButton {
                        background-color: #202026;
                        color: #e1e1e6;
                        border: 1px solid #2c2c36;
                        border-radius: 5px;
                        font-size: 12px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #2b2b34;
                        border: 1px solid #3d3d4a;
                    }
                """)

    def mousePressEvent(self, event):
        ClickSound.play()
        self.is_listening = True
        self._update_appearance()
        self.setFocus()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if self.is_listening:
            key = event.key()
            if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
                event.accept()
                return

            key_text = QKeySequence(key).toString()
            if key_text:
                self.key_value = key_text.upper()
                self.key_changed.emit()

            self.is_listening = False
            self._update_appearance()
            self.clearFocus()
            ClickSound.play()
            event.accept()
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event):
        if self.is_listening:
            self.is_listening = False
            self._update_appearance()
        super().focusOutEvent(event)


class KeybindSlot(QWidget):
    def __init__(self, title: str, default_key: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.label = QLabel(title)
        self.label.setStyleSheet("color: #8f8f9d; font-size: 11px; font-weight: 500;")

        self.button = KeybindButton(default_key)

        layout.addWidget(self.label)
        layout.addWidget(self.button)


class MidiOutputPlayer(QThread):
    finished = pyqtSignal()
    progress_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.notes = []
        self.pedals = []
        self.duration = 0.0
        self.port_name = None
        self.transpose = 0
        self.is_playing = False
        self.is_paused = False
        self._stop_requested = False
        self.midi_out = None

    def set_data(self, midi_data: dict, port_name: str, transpose: int = 0):
        self.notes = midi_data.get("notes", [])
        self.pedals = midi_data.get("pedals", [])
        self.duration = float(midi_data.get("duration", 0.0))
        self.port_name = port_name
        self.transpose = max(-24, min(24, int(transpose)))

    def _prepare_events(self):
        raw = []
        for n in self.notes:
            st = n["start"]
            orig_pitch = int(n["pitch"])
            p = max(0, min(127, orig_pitch + self.transpose))
            dur = max(0.01, n.get("duration", 0.05))
            vel = max(1, min(127, n.get("velocity", 64)))
            raw.append((st, 2, [0x90, p, vel]))
            raw.append((st + dur, 1, [0x80, p, 0]))

        for ped in self.pedals:
            t = ped["time"]
            is_down = ped["down"]
            val = 127 if is_down else 0
            prio = 0 if is_down else 3
            raw.append((t, prio, [0xB0, 64, val]))

        raw.sort(key=lambda x: (x[0], x[1]))
        return [(x[0], x[2]) for x in raw]

    def _silence_all(self):
        if self.midi_out and self.midi_out.is_port_open():
            try:
                for ch in range(16):
                    self.midi_out.send_message([0xB0 | ch, 120, 0])
                    self.midi_out.send_message([0xB0 | ch, 123, 0])
                    self.midi_out.send_message([0xB0 | ch, 64, 0])
            except Exception:
                pass

    def run(self):
        if not rtmidi or not self.port_name:
            self.finished.emit()
            return

        events = self._prepare_events()
        if not events:
            self.finished.emit()
            return

        self.midi_out = rtmidi.MidiOut()
        ports = self.midi_out.get_ports()
        port_idx = -1
        for idx, p in enumerate(ports):
            if p == self.port_name:
                port_idx = idx
                break

        if port_idx == -1:
            del self.midi_out
            self.midi_out = None
            self.finished.emit()
            return

        try:
            self.midi_out.open_port(port_idx)
        except Exception:
            del self.midi_out
            self.midi_out = None
            self.finished.emit()
            return

        self.is_playing = True
        self.is_paused = False
        self._stop_requested = False

        try:
            winmm.timeBeginPeriod(1)
        except Exception:
            pass

        start_perf = time.perf_counter()
        elapsed_raw = 0.0
        event_idx = 0
        total_events = len(events)
        last_progress_emit = -1.0

        try:
            while event_idx < total_events and not self._stop_requested:
                if self.is_paused:
                    time.sleep(0.02)
                    start_perf = time.perf_counter() - elapsed_raw
                    continue

                current_time = time.perf_counter() - start_perf
                elapsed_raw = current_time

                if current_time - last_progress_emit >= 0.04 or last_progress_emit < 0:
                    self.progress_changed.emit(min(self.duration, current_time))
                    last_progress_emit = current_time

                target_time = events[event_idx][0]

                if current_time >= target_time:
                    while event_idx < total_events and current_time >= events[event_idx][0]:
                        _, msg = events[event_idx]
                        self.midi_out.send_message(msg)
                        event_idx += 1
                else:
                    diff = target_time - current_time
                    if diff > 0.005:
                        time.sleep(min(0.01, diff - 0.002))
                    else:
                        time.sleep(0.0005)

        finally:
            self._silence_all()
            if self.midi_out:
                try:
                    self.midi_out.close_port()
                except Exception:
                    pass
                del self.midi_out
                self.midi_out = None

            try:
                winmm.timeEndPeriod(1)
            except Exception:
                pass

        self.is_playing = False
        self.is_paused = False
        if not self._stop_requested:
            self.progress_changed.emit(self.duration)
            self.finished.emit()

    def pause(self):
        if self.is_playing and not self.is_paused:
            self.is_paused = True
            self._silence_all()

    def resume(self):
        if self.is_playing and self.is_paused:
            self.is_paused = False

    def stop_playback(self):
        self._stop_requested = True
        self.is_playing = False
        self.is_paused = False
        self._silence_all()
        self.wait(300)


class MusicView(QWidget):
    state_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        ClickSound.init()

        self.current_midi_data = None
        self.recent_midis = []
        self.selected_port_name = None
        self.is_white = False

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
        self.output_label.setStyleSheet("color: #636370; font-size: 10px; font-weight: bold;")
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
        self.path_title.setStyleSheet("color: #636370; font-size: 10px; font-weight: bold;")
        path_box.addWidget(self.path_title)

        self.path_label = QLabel("No file selected")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("color: #9d9da8; font-size: 12px;")
        path_box.addWidget(self.path_label)
        card_layout.addLayout(path_box)

        recent_box = QVBoxLayout()
        recent_box.setSpacing(4)

        self.recent_title = QLabel("RECENT FILES")
        self.recent_title.setStyleSheet("color: #636370; font-size: 10px; font-weight: bold;")
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

        self.bind_start = KeybindSlot("Start", "F1")
        self.bind_pause = KeybindSlot("Pause", "F2")
        self.bind_end = KeybindSlot("End", "F3")

        for slot in (self.bind_start, self.bind_pause, self.bind_end):
            slot.button.key_changed.connect(self.state_changed.emit)

        keybinds_grid.addWidget(self.bind_start, 0, 0)
        keybinds_grid.addWidget(self.bind_pause, 0, 1)
        keybinds_grid.addWidget(self.bind_end, 0, 2)

        left_layout.addWidget(self.keybinds_card)
        left_layout.addStretch()

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #ef4444; font-size: 12px; font-weight: 600;")
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
            t_lbl.setStyleSheet("color: #636370; font-size: 11px; font-weight: 600;")
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

        # Progress
        progress_box = QVBoxLayout()
        progress_box.setSpacing(4)

        time_row = QHBoxLayout()
        time_row.setContentsMargins(0, 0, 0, 0)

        self.time_title = QLabel("PROGRESS")
        self.time_label = QLabel("0:00:00 / 0:00:00")
        self.time_label.setStyleSheet("color: #8f8f9d; font-size: 11px; font-weight: 600;")

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
        self.set_theme(False)
        self._update_info_card()

    def set_theme(self, is_white: bool):
        self.is_white = is_white
        color_header = "#71717a" if is_white else "#7b7b8a"

        self.output_label.setStyleSheet("color: #636370; font-size: 10px; font-weight: bold;")
        self.midi_header.setStyleSheet(f"color: {color_header}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        self.path_title.setStyleSheet("color: #636370; font-size: 10px; font-weight: bold;")
        self.recent_title.setStyleSheet("color: #636370; font-size: 10px; font-weight: bold;")
        self.keybinds_header.setStyleSheet(f"color: {color_header}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        self.info_header.setStyleSheet(f"color: {color_header}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        self.transpose_title.setStyleSheet(f"color: {color_header}; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
        self.time_title.setStyleSheet(f"color: {color_header}; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")

        if hasattr(self.midi_card, "set_theme"):
            self.midi_card.set_theme(is_white)

        for slot in (self.bind_start, self.bind_pause, self.bind_end):
            slot.button.set_theme(is_white)

        if is_white:
            self.keybinds_card.setStyleSheet("""
                QWidget#musicKeybindsCard {
                    background-color: #ffffff;
                    border: 1px solid #e4e4e7;
                    border-radius: 7px;
                }
            """)
            self.info_card.setStyleSheet("""
                QWidget#infoCard {
                    background-color: #ffffff;
                    border: 1px solid #e4e4e7;
                    border-radius: 7px;
                }
            """)
            self.output_combo.setStyleSheet("""
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
            """)
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
                QProgressBar {
                    background-color: #e4e4e7;
                    border: 1px solid #d4d4d8;
                    border-radius: 2px;
                }
                QProgressBar::chunk {
                    background-color: #3b82f6;
                    border-radius: 2px;
                }
            """)
            btn_action_style = """
                QPushButton {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                    height: 30px;
                }
                QPushButton:hover { background-color: #f4f4f7; border: 1px solid #3b82f6; }
                QPushButton:pressed { background-color: #e4e4e7; }
                QPushButton:disabled {
                    background-color: rgba(228, 228, 231, 0.4);
                    color: rgba(24, 24, 27, 0.25);
                    border: 1px solid rgba(212, 212, 216, 0.4);
                }
            """
        else:
            self.keybinds_card.setStyleSheet("""
                QWidget#musicKeybindsCard {
                    background-color: #16161a;
                    border: 1px solid #23232a;
                    border-radius: 7px;
                }
            """)
            self.info_card.setStyleSheet("""
                QWidget#infoCard {
                    background-color: #16161a;
                    border: 1px solid #23232a;
                    border-radius: 7px;
                }
            """)
            self.output_combo.setStyleSheet("""
                QComboBox {
                    background-color: #16161a;
                    color: #c9c9d4;
                    border: 1px solid #23232a;
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
                QProgressBar {
                    background-color: #16161a;
                    border: 1px solid #23232a;
                    border-radius: 2px;
                }
                QProgressBar::chunk {
                    background-color: #3b82f6;
                    border-radius: 2px;
                }
            """)
            btn_action_style = """
                QPushButton {
                    background-color: #16161a;
                    color: #ffffff;
                    border: 1px solid #23232a;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                    height: 30px;
                }
                QPushButton:hover { background-color: #202026; border: 1px solid #32323d; }
                QPushButton:pressed { background-color: #121216; }
                QPushButton:disabled {
                    background-color: rgba(22, 22, 26, 0.25);
                    color: rgba(255, 255, 255, 0.2);
                    border: 1px solid rgba(35, 35, 42, 0.25);
                }
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
        val_color = "#18181b" if self.is_white else "#e1e1e6"

        if self.selected_port_name:
            self.info_status.setText("Connected")
            self.info_status.setStyleSheet("color: #10b981; font-size: 12px; font-weight: 600;")
            self.info_device.setText(self.selected_port_name)
            self.info_device.setStyleSheet(f"color: {val_color}; font-size: 12px; font-weight: 500;")
        else:
            self.info_status.setText("Disconnected")
            self.info_status.setStyleSheet("color: #ef4444; font-size: 12px; font-weight: 600;")
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
            self.path_label.setStyleSheet("color: #ff5f56; font-size: 12px;")
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
        ClickSound.play()
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
        ClickSound.play()
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
        ClickSound.play()
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