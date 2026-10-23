import ctypes
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel

from themes import BLACK_THEME, WHITE_THEME
from core_utils import truncate_text


# Win32 Window Constants
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010

user32 = ctypes.windll.user32

DEFAULT_OVERLAY_BLACK = BLACK_THEME["overlay"]
DEFAULT_OVERLAY_WHITE = WHITE_THEME["overlay"]


class OverlayWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowOpacity(0.5)
        self.setMinimumWidth(240)

        self.speed_val = 100
        self.midi_name = "None"
        self.notes_up = 0
        self.transpose_val = 0
        self.human_fail = False
        self.sustain_enabled = False
        self.sustain_active = False

        self.show_speed = True
        self.show_midi = True
        self.show_notes = True
        self.show_transpose = True
        self.show_human_fail = True
        self.show_sustain = True

        self.is_white = False
        self.theme_data = dict(DEFAULT_OVERLAY_BLACK)

        self._displayed_speed = None
        self._displayed_midi = None
        self._displayed_notes = None
        self._displayed_transpose = None
        self._displayed_human_fail = None
        self._displayed_sustain = None

        self._styled_hwnd = None
        self._connected_screen = None

        self._setup_ui()
        self._bind_screen_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 14, 10)
        layout.setSpacing(2)

        font = QFont("Segoe UI", 11, QFont.Weight.Bold)

        self.lbl_status = QLabel("Overlay Information: ON")
        self.lbl_speed = QLabel("Speed: 100")
        self.lbl_midi = QLabel("MIDI File: None")
        self.lbl_notes = QLabel("How many notes up: 0")
        self.lbl_transpose = QLabel("Transpose: 0")
        self.lbl_human_fail = QLabel("Human Fail: OFF")
        self.lbl_sustain = QLabel("Sustain: N/A")

        self._displayed_speed = 100
        self._displayed_midi = "None"
        self._displayed_notes = 0
        self._displayed_transpose = 0
        self._displayed_human_fail = False
        self._displayed_sustain = "N/A"

        self._all_labels = (
            self.lbl_status,
            self.lbl_speed,
            self.lbl_midi,
            self.lbl_notes,
            self.lbl_transpose,
            self.lbl_human_fail,
            self.lbl_sustain,
        )

        for lbl in self._all_labels:
            lbl.setFont(font)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(lbl)

        self.set_theme(DEFAULT_OVERLAY_BLACK)

    def _bind_screen_signals(self):
        app = QApplication.instance()
        if app is not None:
            app.primaryScreenChanged.connect(self._on_primary_screen_changed)
        self._connect_screen(QApplication.primaryScreen())

    def _connect_screen(self, screen):
        if self._connected_screen is screen:
            return
        if self._connected_screen is not None:
            try:
                self._connected_screen.geometryChanged.disconnect(self._on_screen_geometry_changed)
            except Exception:
                pass
        self._connected_screen = screen
        if screen is not None:
            try:
                screen.geometryChanged.connect(self._on_screen_geometry_changed)
            except Exception:
                pass

    def _on_primary_screen_changed(self, screen):
        self._connect_screen(screen)
        if self.isVisible():
            self._reposition()

    def _on_screen_geometry_changed(self, _rect):
        if self.isVisible():
            self._reposition()

    def set_theme(self, theme_or_is_white: dict | bool):
        if isinstance(theme_or_is_white, dict):
            self.is_white = bool(theme_or_is_white.get("is_white", False))
            base = DEFAULT_OVERLAY_WHITE if self.is_white else DEFAULT_OVERLAY_BLACK
            merged = dict(base)
            merged.update(theme_or_is_white)
            self.theme_data = merged
        else:
            self.is_white = bool(theme_or_is_white)
            self.theme_data = dict(DEFAULT_OVERLAY_WHITE if self.is_white else DEFAULT_OVERLAY_BLACK)

        t = self.theme_data
        text_col = t.get("label_text", "#ffffff")
        bg_col = t.get("label_bg", "rgba(12, 12, 14, 160)")

        style = f"""
            QLabel {{
                color: {text_col};
                background-color: {bg_col};
                padding: 2px 6px;
                border-radius: 4px;
            }}
        """
        for lbl in self._all_labels:
            lbl.setStyleSheet(style)
        if self.isVisible():
            self.adjustSize()
            self._reposition()

    def update_info(
        self,
        speed: int = None,
        midi_name: str = None,
        notes_up: int = None,
        transpose: int = None,
        human_fail: bool = None,
        sustain_enabled: bool = None,
        sustain_active: bool = None,
        show_speed: bool = None,
        show_midi: bool = None,
        show_notes: bool = None,
        show_transpose: bool = None,
        show_human_fail: bool = None,
        show_sustain: bool = None,
    ):
        if speed is not None:
            self.speed_val = int(speed)
        if midi_name is not None:
            raw_name = midi_name if midi_name else "None"
            self.midi_name = truncate_text(raw_name, 50)
        if notes_up is not None:
            self.notes_up = max(0, int(notes_up))
        if transpose is not None:
            self.transpose_val = int(transpose)
        if human_fail is not None:
            self.human_fail = bool(human_fail)
        if sustain_enabled is not None:
            self.sustain_enabled = bool(sustain_enabled)
            if not self.sustain_enabled:
                self.sustain_active = False
        if sustain_active is not None:
            self.sustain_active = bool(sustain_active) if self.sustain_enabled else False

        if show_speed is not None:
            self.show_speed = bool(show_speed)
        if show_midi is not None:
            self.show_midi = bool(show_midi)
        if show_notes is not None:
            self.show_notes = bool(show_notes)
        if show_transpose is not None:
            self.show_transpose = bool(show_transpose)
        if show_human_fail is not None:
            self.show_human_fail = bool(show_human_fail)
        if show_sustain is not None:
            self.show_sustain = bool(show_sustain)

        self._sync_labels()

    def _sync_labels(self):
        layout_changed = False

        if self.speed_val != self._displayed_speed:
            self._displayed_speed = self.speed_val
            self.lbl_speed.setText(f"Speed: {self.speed_val}")

        if self.midi_name != self._displayed_midi:
            self._displayed_midi = self.midi_name
            self.lbl_midi.setText(f"MIDI File: {self.midi_name}")
            layout_changed = True

        if self.notes_up != self._displayed_notes:
            self._displayed_notes = self.notes_up
            self.lbl_notes.setText(f"How many notes up: {self.notes_up}")

        if self.transpose_val != self._displayed_transpose:
            self._displayed_transpose = self.transpose_val
            self.lbl_transpose.setText(f"Transpose: {self.transpose_val}")

        if self.human_fail != self._displayed_human_fail:
            self._displayed_human_fail = self.human_fail
            state_str = "ON" if self.human_fail else "OFF"
            self.lbl_human_fail.setText(f"Human Fail: {state_str}")

        if not self.sustain_enabled:
            sustain_str = "N/A"
        else:
            sustain_str = "ON" if self.sustain_active else "OFF"

        if sustain_str != self._displayed_sustain:
            self._displayed_sustain = sustain_str
            self.lbl_sustain.setText(f"Sustain: {sustain_str}")

        visibility_pairs = (
            (self.lbl_speed, self.show_speed),
            (self.lbl_midi, self.show_midi),
            (self.lbl_notes, self.show_notes),
            (self.lbl_transpose, self.show_transpose),
            (self.lbl_human_fail, self.show_human_fail),
            (self.lbl_sustain, self.show_sustain),
        )
        for lbl, should_show in visibility_pairs:
            if lbl.isHidden() == should_show:
                lbl.setVisible(should_show)
                layout_changed = True

        if layout_changed and self.isVisible():
            self.adjustSize()
            self._reposition()

    def _reposition(self):
        screen = self._connected_screen or QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.geometry()
        margin_top = 12
        margin_right = 12
        x = geo.x() + geo.width() - self.width() - margin_right
        y = geo.y() + margin_top
        if self.x() != x or self.y() != y:
            self.move(x, y)

    def _apply_win32_clickthrough(self, force: bool = False):
        try:
            hwnd = int(self.winId())
            if not force and self._styled_hwnd == hwnd:
                return
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            target_style = (
                ex_style
                | WS_EX_LAYERED
                | WS_EX_TRANSPARENT
                | WS_EX_TOOLWINDOW
                | WS_EX_NOACTIVATE
            )
            if ex_style != target_style:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, target_style)
            user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
            )
            self._styled_hwnd = hwnd
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._connect_screen(QApplication.primaryScreen())
        self._sync_labels()
        self.adjustSize()
        self._reposition()
        self._apply_win32_clickthrough(force=True)