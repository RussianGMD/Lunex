import os
import sys
import time
import ctypes
from ctypes import wintypes
import winsound
from PyQt6.QtCore import QUrl, QThread, pyqtSignal, QtMsgType
from PyQt6.QtMultimedia import QSoundEffect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Note Names (C to B)
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Sound File Mapping
SOUND_FILE_MAP = {
    "Click": "click",
    "Tap": "tap",
    "Tick": "tick",
}

# Win32 API Setup
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


def pitch_to_note_name(pitch: int) -> str:
    octave = (pitch // 12) - 1
    return f"{NOTE_NAMES[pitch % 12]}{octave}"


def find_sound_file(sound_name: str = "Click") -> str | None:
    if not sound_name or sound_name == "None":
        return None
    base_name = SOUND_FILE_MAP.get(sound_name)
    if not base_name:
        return None

    candidates = [
        os.path.join(BASE_DIR, "sounds", f"{base_name}.WAV"),
        os.path.join(BASE_DIR, "sounds", f"{base_name}.wav"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def qt_message_handler(mode: QtMsgType, context, message: str):
    if "QFont::setPointSize" in message or "must be greater than 0" in message or "QWindowsWindow::setGeometry" in message:
        return
    try:
        if mode == QtMsgType.QtFatalMsg and sys.stderr is not None:
            sys.stderr.write(f"[Qt Fatal] {message}\n")
        elif mode == QtMsgType.QtCriticalMsg and sys.stderr is not None:
            sys.stderr.write(f"[Qt Critical] {message}\n")
        elif mode == QtMsgType.QtWarningMsg and sys.stderr is not None:
            sys.stderr.write(f"[Qt Warning] {message}\n")
        elif mode == QtMsgType.QtInfoMsg and sys.stdout is not None:
            sys.stdout.write(f"[Qt Info] {message}\n")
    except Exception:
        pass


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


def truncate_text(text: str, max_len: int = 50) -> str:
    if not text:
        return ""
    return text[:max_len] + "..." if len(text) > max_len else text


def get_icon_path(base_name: str, is_white: bool = False) -> str:
    if is_white:
        white_path = os.path.join(BASE_DIR, "icons", f"{base_name}_white.png")
        if os.path.exists(white_path):
            return white_path
    return os.path.join(BASE_DIR, "icons", f"{base_name}.png")


def key_to_vk(key_str: str) -> int:
    if not key_str:
        return 0
    key_str = key_str.strip().upper()
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
    sound_name = "Click"
    sound_path = None
    effect = None
    muted = False

    @classmethod
    def init(cls, sound_name: str = "Click"):
        cls.set_sound(sound_name)

    @classmethod
    def set_sound(cls, sound_name: str):
        cls.sound_name = sound_name
        if sound_name == "None":
            cls.sound_path = None
            cls.effect = None
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
            return
        cls.sound_path = find_sound_file(sound_name)
        if cls.sound_path:
            try:
                cls.effect = QSoundEffect()
                cls.effect.setSource(QUrl.fromLocalFile(cls.sound_path))
                cls.effect.setVolume(0.6)
            except Exception:
                cls.effect = None
        else:
            cls.effect = None

    @classmethod
    def play(cls):
        if cls.muted or cls.sound_name == "None" or not cls.sound_path:
            return
        try:
            winsound.PlaySound(cls.sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            if cls.effect:
                try:
                    cls.effect.play()
                except Exception:
                    pass