import os
import sys
import ctypes
from ctypes import wintypes
import pickle
import winsound
from PyQt6.QtCore import (
    Qt, QPoint, QRectF, QPropertyAnimation, QEasingCurve, 
    pyqtProperty, QUrl, QTimer, QThread, pyqtSignal,
    qInstallMessageHandler, QtMsgType
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QIcon, QPixmap, 
    QKeySequence, QIntValidator, QDesktopServices
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, 
    QVBoxLayout, QGridLayout, QLabel, QPushButton, QAbstractButton, 
    QFileDialog, QSlider, QLineEdit, QProgressBar, QComboBox, QStackedWidget,
    QPlainTextEdit, QDialog
)
from PyQt6.QtMultimedia import QSoundEffect
from load_midi import MidiLoader
from macro import MacroPlayer
from drag import MidiDropCard
from music import MusicView
from midihub import MidiHubView
from miditoqwerty import MidiToQwertyView
from settings_view import SettingsView, ClickSound, UpdateCheckerThread

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def pitch_to_note_name(pitch: int) -> str:
    octave = (pitch // 12) - 1
    return f"{NOTE_NAMES[pitch % 12]}{octave}"

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

def qt_message_handler(mode: QtMsgType, context, message: str):
    if "QFont::setPointSize" in message:
        return
    if "must be greater than 0" in message:
        return
    if "QWindowsWindow::setGeometry" in message:
        return
    if mode == QtMsgType.QtFatalMsg:
        sys.stderr.write(f"[Qt Fatal] {message}\n")
    elif mode == QtMsgType.QtCriticalMsg:
        sys.stderr.write(f"[Qt Critical] {message}\n")
    elif mode == QtMsgType.QtWarningMsg:
        sys.stderr.write(f"[Qt Warning] {message}\n")
    elif mode == QtMsgType.QtInfoMsg:
        sys.stdout.write(f"[Qt Info] {message}\n")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.GetAsyncKeyState.argtypes = [wintypes.INT]
user32.GetAsyncKeyState.restype = wintypes.SHORT
user32.VkKeyScanW.argtypes = [wintypes.WCHAR]
user32.VkKeyScanW.restype = wintypes.SHORT

FILE_ATTRIBUTE_HIDDEN = 0x02
FILE_ATTRIBUTE_NORMAL = 0x80
kernel32.SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
kernel32.SetFileAttributesW.restype = wintypes.BOOL

def set_hidden_attribute(file_path: str, hidden: bool):
    if os.name == "nt" and os.path.exists(file_path):
        attr = FILE_ATTRIBUTE_HIDDEN if hidden else FILE_ATTRIBUTE_NORMAL
        kernel32.SetFileAttributesW(file_path, attr)

def format_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}"

def get_icon_path(base_name: str, is_white: bool = False) -> str:
    if is_white:
        white_path = f"icons/{base_name}_white.png"
        if os.path.exists(white_path):
            return white_path
    return f"icons/{base_name}.png"

def key_to_vk(key_str: str) -> int:
    if not key_str:
        return 0
    key_str = key_str.strip().upper()

    # F1 - F24
    if key_str.startswith("F") and key_str[1:].isdigit():
        f_num = int(key_str[1:])
        if 1 <= f_num <= 24:
            return 0x70 + (f_num - 1)

    special = {
        
        "BACKSPACE": 0x08, "BACK": 0x08, "BKSP": 0x08,
        "TAB": 0x09,
        "CLEAR": 0x0C,
        "ENTER": 0x0D, "RETURN": 0x0D,
        "PAUSE": 0x13,
        "CAPSLOCK": 0x14, "CAPS LOCK": 0x14, "CAPS": 0x14,
        "ESC": 0x1B, "ESCAPE": 0x1B,
        "SPACE": 0x20, "SPACEBAR": 0x20,
        "PGUP": 0x21, "PAGEUP": 0x21, "PAGE UP": 0x21,
        "PGDN": 0x22, "PAGEDOWN": 0x22, "PAGE DOWN": 0x22,
        "END": 0x23,
        "HOME": 0x24,
        "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
        "SELECT": 0x29,
        "PRINT": 0x2A,
        "PRINTSCREEN": 0x2C, "PRINT SCREEN": 0x2C, "PRTSC": 0x2C, "SNAPSHOT": 0x2C,
        "INS": 0x2D, "INSERT": 0x2D,
        "DEL": 0x2E, "DELETE": 0x2E,
        "HELP": 0x2F,
        "SLEEP": 0x5F,
        # Numpad
        "NUMPAD0": 0x60, "NUMPAD 0": 0x60, "NUM 0": 0x60,
        "NUMPAD1": 0x61, "NUMPAD 1": 0x61, "NUM 1": 0x61,
        "NUMPAD2": 0x62, "NUMPAD 2": 0x62, "NUM 2": 0x62,
        "NUMPAD3": 0x63, "NUMPAD 3": 0x63, "NUM 3": 0x63,
        "NUMPAD4": 0x64, "NUMPAD 4": 0x64, "NUM 4": 0x64,
        "NUMPAD5": 0x65, "NUMPAD 5": 0x65, "NUM 5": 0x65,
        "NUMPAD6": 0x66, "NUMPAD 6": 0x66, "NUM 6": 0x66,
        "NUMPAD7": 0x67, "NUMPAD 7": 0x67, "NUM 7": 0x67,
        "NUMPAD8": 0x68, "NUMPAD 8": 0x68, "NUM 8": 0x68,
        "NUMPAD9": 0x69, "NUMPAD 9": 0x69, "NUM 9": 0x69,
        "MULTIPLY": 0x6A, "NUM*": 0x6A,
        "ADD": 0x6B, "NUM+": 0x6B,
        "SEPARATOR": 0x6C,
        "SUBTRACT": 0x6D, "NUM-": 0x6D,
        "DECIMAL": 0x6E, "NUM.": 0x6E,
        "DIVIDE": 0x6F, "NUM/": 0x6F,
        "NUMLOCK": 0x90, "NUM LOCK": 0x90,
        "SCROLLLOCK": 0x91, "SCROLL LOCK": 0x91,
        
        ";": 0xBA, ":": 0xBA,
        "=": 0xBB, "+": 0xBB,
        ",": 0xBC, "<": 0xBC,
        "-": 0xBD, "_": 0xBD,
        ".": 0xBE, ">": 0xBE,
        "/": 0xBF, "?": 0xBF,
        "`": 0xC0, "~": 0xC0,
        "[": 0xDB, "{": 0xDB,
        "\\": 0xDC, "|": 0xDC,
        "]": 0xDD, "}": 0xDD,
        "'": 0xDE, '"': 0xDE,
        
        "Х": 0xDB, "Ъ": 0xDD,
        "Ж": 0xBA, "Э": 0xDE,
        "Б": 0xBC, "Ю": 0xBE,
        "Ё": 0xC0,
    }

    if key_str in special:
        return special[key_str]

    if len(key_str) == 1:
        c = ord(key_str)
        if 0x30 <= c <= 0x39 or 0x41 <= c <= 0x5A:
            return c
        try:
            res = user32.VkKeyScanW(key_str)
            if res != -1 and res != 0xFFFF:
                return res & 0xFF
        except Exception:
            pass

    return 0

class GlobalHotkeyListener(QThread):
    action_triggered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.bindings = {}
        self._last_states = {}

    def update_bindings(self, bindings_dict: dict):
        new_map = {}
        for action, key_str in bindings_dict.items():
            vk = key_to_vk(key_str)
            if vk:
                new_map[action] = vk
                self._last_states[vk] = (user32.GetAsyncKeyState(vk) & 0x8000) != 0
        self.bindings = new_map

    def run(self):
        import time
        while self.running:
            for action, vk in list(self.bindings.items()):
                is_down = (user32.GetAsyncKeyState(vk) & 0x8000) != 0
                was_down = self._last_states.get(vk, False)
                if is_down and not was_down:
                    self.action_triggered.emit(action)
                self._last_states[vk] = is_down
            time.sleep(0.02)

    def stop(self):
        self.running = False
        self.wait(300)

class SoundManager:
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
        SoundManager.play()
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
        SoundManager.play()
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
            if not key_text and event.text():
                key_text = event.text()
            if key_text:
                self.key_value = key_text.upper()
                self.key_changed.emit()
            self.is_listening = False
            self._update_appearance()
            self.clearFocus()
            SoundManager.play()
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

class DebugConsoleWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lunex - Debug Console")
        self.resize(620, 400)
        self.setMinimumSize(420, 260)
        if os.path.exists("icon.ico"):
            self.setWindowIcon(QIcon("icon.ico"))
        self.is_white = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(8)

        self.title_label = QLabel("DEBUG CONSOLE")
        self.title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        top_bar.addWidget(self.title_label)
        top_bar.addStretch()

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setFixedHeight(28)
        self.btn_clear.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.clicked.connect(self.clear_logs)
        top_bar.addWidget(self.btn_clear)
        layout.addLayout(top_bar)

        self.text_box = QPlainTextEdit()
        self.text_box.setReadOnly(True)
        self.text_box.setMaximumBlockCount(5000)
        self.text_box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.text_box)

        self.set_theme(False)

    def append_log(self, text: str):
        self.text_box.appendPlainText(text)
        sb = self.text_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear_logs(self):
        SoundManager.play()
        self.text_box.clear()

    def set_theme(self, is_white: bool):
        self.is_white = is_white
        if is_white:
            self.setStyleSheet("background-color: #f4f4f7;")
            self.title_label.setStyleSheet("color: #18181b;")
            self.btn_clear.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0 12px;
                }
                QPushButton:hover {
                    background-color: #f4f4f7;
                    border: 1px solid #3b82f6;
                }
            """)
            self.text_box.setStyleSheet("""
                QPlainTextEdit {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #e4e4e7;
                    border-radius: 6px;
                    padding: 8px;
                    font-family: 'Consolas', 'Segoe UI', monospace;
                    font-size: 9.5pt;
                }
            """)
        else:
            self.setStyleSheet("background-color: #0c0c0e;")
            self.title_label.setStyleSheet("color: #ffffff;")
            self.btn_clear.setStyleSheet("""
                QPushButton {
                    background-color: #16161a;
                    color: #e1e1e6;
                    border: 1px solid #23232a;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0 12px;
                }
                QPushButton:hover {
                    background-color: #202026;
                    border: 1px solid #3b82f6;
                    color: #ffffff;
                }
            """)
            self.text_box.setStyleSheet("""
                QPlainTextEdit {
                    background-color: #16161a;
                    color: #e1e1e6;
                    border: 1px solid #23232a;
                    border-radius: 6px;
                    padding: 8px;
                    font-family: 'Consolas', 'Segoe UI', monospace;
                    font-size: 9.5pt;
                }
            """)

class UpdateDialog(QDialog):
    def __init__(self, parent=None, is_white: bool = False):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(380, 180)
        self.is_white = is_white
        self.old_pos = None
        self._setup_ui()

    def _setup_ui(self):
        container = QWidget(self)
        container.setObjectName("updateDialogContainer")
        container.setFixedSize(380, 180)

        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(16, 12, 16, 16)
        root_layout.setSpacing(10)

        header_bar = QHBoxLayout()
        header_bar.setContentsMargins(0, 0, 0, 0)
        title_lbl = QLabel("Update Available")
        title_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))

        btn_close = QPushButton()
        btn_close.setFixedSize(11, 11)
        btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #ff5f56;
                border: 1px solid #e0443e;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #ff7b73; }
        """)
        btn_close.clicked.connect(self.close)

        header_bar.addWidget(title_lbl)
        header_bar.addStretch()
        header_bar.addWidget(btn_close)
        root_layout.addLayout(header_bar)

        content_layout = QVBoxLayout()
        content_layout.setSpacing(6)
        msg_lbl = QLabel("Please, update the Lunex to new version.")
        msg_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        msg_lbl.setWordWrap(True)

        link_lbl = QLabel('Download here: <a href="https://lunexsoftworksllc.netlify.app" style="color: #3b82f6; text-decoration: none; font-weight: 600;">lunexsoftworksllc.netlify.app</a>')
        link_lbl.setFont(QFont("Segoe UI", 10))
        link_lbl.setOpenExternalLinks(True)

        content_layout.addWidget(msg_lbl)
        content_layout.addWidget(link_lbl)
        root_layout.addLayout(content_layout)

        root_layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_download = QPushButton("Open Link")
        btn_download.setFixedHeight(28)
        btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_download.clicked.connect(self._open_site)

        btn_ok = QPushButton("OK")
        btn_ok.setFixedHeight(28)
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.clicked.connect(self.close)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_download)
        btn_layout.addWidget(btn_ok)
        root_layout.addLayout(btn_layout)

        if self.is_white:
            container.setStyleSheet("""
                QWidget#updateDialogContainer {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 10px;
                }
            """)
            title_lbl.setStyleSheet("color: #71717a;")
            msg_lbl.setStyleSheet("color: #18181b;")
            link_lbl.setStyleSheet("color: #52525b;")
            btn_style = """
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
            btn_download.setStyleSheet(btn_style)
            btn_ok.setStyleSheet(btn_style)
        else:
            container.setStyleSheet("""
                QWidget#updateDialogContainer {
                    background-color: #16161a;
                    border: 1px solid #2c2c36;
                    border-radius: 10px;
                }
            """)
            title_lbl.setStyleSheet("color: #8f8f9d;")
            msg_lbl.setStyleSheet("color: #ffffff;")
            link_lbl.setStyleSheet("color: #a1a1aa;")
            btn_style = """
                QPushButton {
                    background-color: #202026;
                    color: #ffffff;
                    border: 1px solid #2c2c36;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0 14px;
                }
                QPushButton:hover { background-color: #2b2b34; border: 1px solid #3b82f6; }
            """
            btn_download.setStyleSheet(btn_style)
            btn_ok.setStyleSheet(btn_style)

    def _open_site(self):
        SoundManager.play()
        QDesktopServices.openUrl(QUrl("https://lunexsoftworksllc.netlify.app"))
        self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 36:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

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
        self.is_loading_state = True
        self._playback_stopped = True

        self.is_counting_down = False
        self.remaining_countdown = 0
        self.start_timer = QTimer(self)
        self.start_timer.setInterval(1000)
        self.start_timer.timeout.connect(self._on_countdown_tick)

        self.save_dir = os.path.abspath("saves")
        self.save_file = os.path.join(self.save_dir, "settings.bin")

        self.player = MacroPlayer(self)
        self.player.finished.connect(self._on_player_finished)
        self.player.progress_changed.connect(self._on_progress_changed)
        self.player.notes_clicked.connect(self._on_notes_clicked)

        self.hotkey_listener = GlobalHotkeyListener(self)
        self.hotkey_listener.action_triggered.connect(self._on_global_hotkey)

        if os.path.exists("icon.ico"):
            self.setWindowIcon(QIcon("icon.ico"))

        SoundManager.muted = True
        ClickSound.muted = True
        self._setup_ui()
        self._load_saved_state()
        self._sync_hotkeys()
        self.hotkey_listener.start()
        SoundManager.muted = False
        ClickSound.muted = False
        self.is_loading_state = False
        self._sync_console_visibility()

        self.startup_checker = UpdateCheckerThread(self)
        self.startup_checker.check_finished.connect(self._on_startup_update_checked)
        self.startup_checker.start()

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
        self.settings_view.toggle_timer_start.toggle.toggled.connect(
            lambda c: self._on_toggle_setting("Timer Start", c)
        )
        self.settings_view.toggle_loop_song.toggle.toggled.connect(
            lambda c: self._on_toggle_setting("Loop Song", c)
        )
        self.settings_view.toggle_console.toggle.toggled.connect(
            lambda c: self._on_toggle_setting("Console", c)
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
        if os.path.exists("icon.ico"):
            pixmap = QPixmap("icon.ico").scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
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

    def log_console(self, text: str):
        print(text, flush=True)
        if hasattr(self, "console_box"):
            self.console_box.appendPlainText(text)
            scrollbar = self.console_box.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        if hasattr(self, "debug_console") and self.debug_console:
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
        note_str = " + ".join(pitch_to_note_name(p) for p in pitches)
        self.log_console(f"Clicked {note_str} Note.")

    def _on_toggle_setting(self, title: str, checked: bool):
        if not self.is_loading_state:
            action = "Enabled" if checked else "Disabled"
            self.log_console(f"{action} {title}.")
        self._save_state()

    def apply_theme(self, theme_name: str):
        self.is_white_theme = (theme_name == "White")
        is_w = self.is_white_theme

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

        if is_w:
            self.central_widget.setStyleSheet("""
                #centralWidget {
                    background-color: #f4f4f7;
                    border: 1px solid #d4d4d8;
                    border-radius: 10px;
                }
            """)
            self.title_bar.setStyleSheet("background: transparent; border-bottom: 1px solid #e4e4e7;")
            self.title_label.setStyleSheet("color: #18181b; padding-left: 2px;")
            self.midi_card_header.setStyleSheet("color: #71717a; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
            self.keybinds_header.setStyleSheet("color: #71717a; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
            self.settings_header.setStyleSheet("color: #71717a; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; margin-bottom: 2px;")
            self.speed_title.setStyleSheet("color: #71717a; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
            self.time_title.setStyleSheet("color: #71717a; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
            self.keybinds_card.setStyleSheet("""
                QWidget#keybindsCard {
                    background-color: #ffffff;
                    border: 1px solid #e4e4e7;
                    border-radius: 7px;
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
            self.recent_combo.setStyleSheet("""
                QComboBox {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    padding-left: 10px;
                    font-size: 9pt;
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
                    font-size: 9pt;
                    outline: none;
                }
            """)
            self.speed_input.setStyleSheet("""
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
            self.speed_slider.setStyleSheet("""
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
            """)
            self.progress_bar.setStyleSheet("""
                QProgressBar { background-color: #e4e4e7; border: 1px solid #d4d4d8; border-radius: 2px; }
                QProgressBar::chunk { background-color: #3b82f6; border-radius: 2px; }
            """)
            self.console_header.setStyleSheet("color: #71717a; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
            self.console_box.setStyleSheet("""
                QPlainTextEdit {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #e4e4e7;
                    border-radius: 6px;
                    padding: 6px;
                    font-family: 'Consolas', 'Segoe UI', monospace;
                    font-size: 8.5pt;
                }
            """)
        else:
            self.central_widget.setStyleSheet("""
                #centralWidget {
                    background-color: #0c0c0e;
                    border: 1px solid #1f1f24;
                    border-radius: 10px;
                }
            """)
            self.title_bar.setStyleSheet("background: transparent; border-bottom: 1px solid #18181c;")
            self.title_label.setStyleSheet("color: #ffffff; padding-left: 2px;")
            self.midi_card_header.setStyleSheet("color: #7b7b8a; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
            self.keybinds_header.setStyleSheet("color: #7b7b8a; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
            self.settings_header.setStyleSheet("color: #7b7b8a; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; margin-bottom: 2px;")
            self.speed_title.setStyleSheet("color: #7b7b8a; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
            self.time_title.setStyleSheet("color: #7b7b8a; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
            self.keybinds_card.setStyleSheet("""
                QWidget#keybindsCard {
                    background-color: #16161a;
                    border: 1px solid #23232a;
                    border-radius: 7px;
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
            self.recent_combo.setStyleSheet("""
                QComboBox {
                    background-color: #1a1a20;
                    color: #c9c9d4;
                    border: 1px solid #282832;
                    border-radius: 5px;
                    padding-left: 10px;
                    font-size: 9pt;
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
                    font-size: 9pt;
                    outline: none;
                }
            """)
            self.speed_input.setStyleSheet("""
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
            self.speed_slider.setStyleSheet("""
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
            self.console_header.setStyleSheet("color: #7b7b8a; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
            self.console_box.setStyleSheet("""
                QPlainTextEdit {
                    background-color: #16161a;
                    color: #e1e1e6;
                    border: 1px solid #23232a;
                    border-radius: 6px;
                    padding: 6px;
                    font-family: 'Consolas', 'Segoe UI', monospace;
                    font-size: 8.5pt;
                }
            """)

        for row in (self.toggle_no_doubles, self.toggle_velocity, self.toggle_88_keys,
                    self.toggle_sustain, self.toggle_accurate_gate, self.toggle_speed_protection):
            row.set_theme(is_w)

        for slot in (self.bind_start, self.bind_pause, self.bind_end, self.bind_speed_down, self.bind_speed_up):
            slot.button.set_theme(is_w)

        self._update_tab_buttons_style(self.stack.currentIndex())
        self.settings_view.set_theme(is_w)
        self.music_view.set_theme(is_w)
        self.hub_view.set_theme(is_w)
        self.converter_view.set_theme(is_w)
        if hasattr(self, "debug_console") and self.debug_console:
            self.debug_console.set_theme(is_w)

    def _update_tab_buttons_style(self, current_index: int):
        if self.is_white_theme:
            active_style = """
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #3b82f6;
                    border-radius: 5px;
                    color: #18181b;
                    font-size: 13px;
                }
            """
            inactive_style = """
                QPushButton {
                    background-color: #e4e4e7;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    color: #71717a;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #d4d4d8;
                    color: #18181b;
                }
            """
        else:
            active_style = """
                QPushButton {
                    background-color: #202028;
                    border: 1px solid #3b82f6;
                    border-radius: 5px;
                    color: #ffffff;
                    font-size: 13px;
                }
            """
            inactive_style = """
                QPushButton {
                    background-color: #1a1a20;
                    border: 1px solid #2a2a34;
                    border-radius: 5px;
                    color: #8f8f9d;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #262630;
                    color: #ffffff;
                }
            """
        self.home_btn.setStyleSheet(active_style if current_index == 0 else inactive_style)
        self.music_btn.setStyleSheet(active_style if current_index == 1 else inactive_style)
        self.hub_btn.setStyleSheet(active_style if current_index == 2 else inactive_style)
        self.converter_btn.setStyleSheet(active_style if current_index == 3 else inactive_style)
        self.settings_btn.setStyleSheet(active_style if current_index == 4 else inactive_style)

    def _switch_tab(self, index: int):
        SoundManager.play()
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
        self._save_state()
        new_theme = self.settings_view.get_theme()
        self.apply_theme(new_theme)
        self._sync_console_visibility()

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
        path_title = QLabel("PATH")
        path_title.setStyleSheet("color: #636370; font-size: 10px; font-weight: bold;")
        path_box.addWidget(path_title)
        self.path_label = QLabel("No file selected")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("color: #9d9da8; font-size: 12px;")
        path_box.addWidget(self.path_label)
        card_layout.addLayout(path_box)

        recent_box = QVBoxLayout()
        recent_box.setSpacing(4)
        recent_title = QLabel("RECENT FILES")
        recent_title.setStyleSheet("color: #636370; font-size: 10px; font-weight: bold;")
        recent_box.addWidget(recent_title)
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
        self.status_label.setStyleSheet("color: #ef4444; font-size: 12px; font-weight: 600;")
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
                background-color: rgba(228, 228, 231, 0.25);
                color: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(35, 35, 42, 0.25);
            }
        """
        self.btn_start = QPushButton("Start")
        self.btn_pause = QPushButton("Pause")
        self.btn_end = QPushButton("End")

        for btn in (self.btn_start, self.btn_pause, self.btn_end):
            btn.setStyleSheet(btn_action_style)
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
        dlg = UpdateDialog(self, is_white=self.is_white_theme)
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
            self.recent_combo.addItem(os.path.basename(path), path)
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
            if not os.path.exists(self.save_dir):
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
                pickle.dump(data, f)
            set_hidden_attribute(self.save_file, hidden=True)
        except Exception:
            pass

    def _load_saved_state(self):
        if not os.path.isfile(self.save_file):
            self._update_recent_combo()
            return
        try:
            with open(self.save_file, "rb") as f:
                data = pickle.load(f)
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
                self.settings_view.load_save_data(data["settings_tab"])
                saved_theme = data["settings_tab"].get("app_theme", "Black (Standart)")
                self.apply_theme(saved_theme)
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
        self._save_state()

    def _on_slider_changed(self, val: int):
        self.speed_input.setText(str(val))
        self.player.set_speed(val)
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
            if not silent:
                self._save_state()
                self.log_console("Loaded MIDI File.")
        except Exception as e:
            self.path_label.setText(f"Error: {str(e)}")
            self.path_label.setStyleSheet("color: #ff5f56; font-size: 12px;")
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

    def _show_error(self, text: str):
        self.status_label.setText(text)
        QTimer.singleShot(3000, lambda: self.status_label.setText("") if self.status_label.text() == text else None)

    def _on_start_clicked(self):
        SoundManager.play()
        if not self.current_midi_data:
            self._show_error("MIDI File not Loaded!")
            return
        self.player.stop_playback()
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
        self.player.set_midi_data(self.current_midi_data)
        self.player.set_speed(self.speed_slider.value())
        self.player.set_settings(
            no_doubles=self.toggle_no_doubles.toggle.isChecked(),
            velocity=self.toggle_velocity.toggle.isChecked(),
            keys88=self.toggle_88_keys.toggle.isChecked(),
            sustain=self.toggle_sustain.toggle.isChecked(),
            accurate_gate=self.toggle_accurate_gate.toggle.isChecked(),
            speed_protection=self.toggle_speed_protection.toggle.isChecked()
        )
        settings_data = self.settings_view.get_save_data()
        self.player.set_human_fail_settings(
            enabled=settings_data.get("human_fail", False),
            speed_fail_pct=settings_data.get("speed_fail_pct", 1.0),
            transpose_fail_pct=settings_data.get("transpose_fail_pct", 5.0),
            speed_fail_min=settings_data.get("speed_fail_min", 0.8),
            speed_fail_max=settings_data.get("speed_fail_max", 1.2),
            speed_fail_slow_pct=settings_data.get("speed_fail_slow_pct", 50.0),
            speed_fail_fast_pct=settings_data.get("speed_fail_fast_pct", 50.0)
        )
        self.player.set_loop_song(settings_data.get("loop_song", False))
        self.player.set_transposition(settings_data.get("macro_transposition", 0))

        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_pause.setText("Pause")
        self.btn_end.setEnabled(True)
        self._playback_stopped = False
        self.log_console("Started Playback.")
        self.player.start()

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
        self.close()

    def closeEvent(self, event):
        self._save_state()
        if hasattr(self, "start_timer") and self.start_timer.isActive():
            self.start_timer.stop()
        self.music_view.stop_playback()
        if hasattr(self, "debug_console") and self.debug_console:
            self.debug_console.close()
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
    SoundManager.init()
    ClickSound.init()
    window = LunexWindow()
    window.show()
    sys.exit(app.exec())