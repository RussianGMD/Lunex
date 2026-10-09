import time
import random
import ctypes
from ctypes import wintypes
from PyQt6.QtCore import QThread, pyqtSignal

user32 = ctypes.windll.user32
winmm = ctypes.windll.winmm

INPUT_KEYBOARD = 1
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_KEYUP = 0x0002

SCAN_SHIFT = 0x2A
SCAN_CTRL = 0x1D
SCAN_ALT = 0x38
SCAN_SPACE = 0x39

ULONG_PTR = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_uint32


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", INPUT_UNION),
    ]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT


def _send_key(scancode: int, is_up: bool = False):
    flags = KEYEVENTF_SCANCODE
    if is_up:
        flags |= KEYEVENTF_KEYUP
    inp = INPUT(
        type=INPUT_KEYBOARD,
        u=INPUT_UNION(ki=KEYBDINPUT(wVk=0, wScan=scancode, dwFlags=flags, time=0, dwExtraInfo=0))
    )
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


VELOCITY_MAP = [
    0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B,  # 1-0
    0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19,  # q-p
    0x1E, 0x1F, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26,        # a-l
    0x2C, 0x2D, 0x2E                                              # z-c
]

MIDI_MAP = {
    # 88 Keys: Lower register (A0 to B1 via CTRL)
    21: (0x02, "ctrl"),   22: (0x03, "ctrl"),   23: (0x04, "ctrl"),
    24: (0x05, "ctrl"),   25: (0x06, "ctrl"),   26: (0x07, "ctrl"),
    27: (0x08, "ctrl"),   28: (0x09, "ctrl"),   29: (0x0A, "ctrl"),
    30: (0x0B, "ctrl"),   31: (0x10, "ctrl"),   32: (0x11, "ctrl"),
    33: (0x12, "ctrl"),   34: (0x13, "ctrl"),   35: (0x14, "ctrl"),

    # Standard 61 Keys (C2 to C7)
    36: (0x02, None),     37: (0x02, "shift"),  38: (0x03, None),
    39: (0x03, "shift"),  40: (0x04, None),     41: (0x05, None),
    42: (0x05, "shift"),  43: (0x06, None),     44: (0x06, "shift"),
    45: (0x07, None),     46: (0x07, "shift"),  47: (0x08, None),
    48: (0x09, None),     49: (0x09, "shift"),  50: (0x0A, None),
    51: (0x0A, "shift"),  52: (0x0B, None),     53: (0x10, None),
    54: (0x10, "shift"),  55: (0x11, None),     56: (0x11, "shift"),
    57: (0x12, None),     58: (0x12, "shift"),  59: (0x13, None),
    60: (0x14, None),     61: (0x14, "shift"),  62: (0x15, None),
    63: (0x15, "shift"),  64: (0x16, None),     65: (0x17, None),
    66: (0x17, "shift"),  67: (0x18, None),     68: (0x18, "shift"),
    69: (0x19, None),     70: (0x19, "shift"),  71: (0x1E, None),
    72: (0x1F, None),     73: (0x1F, "shift"),  74: (0x20, None),
    75: (0x20, "shift"),  76: (0x21, None),     77: (0x22, None),
    78: (0x22, "shift"),  79: (0x23, None),     80: (0x23, "shift"),
    81: (0x24, None),     82: (0x24, "shift"),  83: (0x25, None),
    84: (0x26, None),     85: (0x26, "shift"),  86: (0x2C, None),
    87: (0x2C, "shift"),  88: (0x2D, None),     89: (0x2E, None),
    90: (0x2E, "shift"),  91: (0x2F, None),     92: (0x2F, "shift"),
    93: (0x30, None),     94: (0x30, "shift"),  95: (0x31, None),
    96: (0x32, None),

    # 88 Keys: Higher register (C#7 to C8 via CTRL)
    97:  (0x15, "ctrl"),  98:  (0x16, "ctrl"),  99:  (0x17, "ctrl"),
    100: (0x18, "ctrl"),  101: (0x19, "ctrl"),  102: (0x1E, "ctrl"),
    103: (0x1F, "ctrl"),  104: (0x20, "ctrl"),  105: (0x21, "ctrl"),
    106: (0x22, "ctrl"),  107: (0x23, "ctrl"),  108: (0x24, "ctrl"),
}


class MacroPlayer(QThread):
    finished = pyqtSignal()
    progress_changed = pyqtSignal(float)
    notes_clicked = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.notes = []
        self.pedals = []
        self.duration = 0.0
        self.speed_percent = 100
        self.no_doubles = False
        self.velocity_enabled = False
        self.keys_88 = False
        self.sustain = False
        self.accurate_gate = True
        self.speed_protection = False

        # Human Fail
        self.human_fail = False
        self.speed_fail_pct = 1.0
        self.transpose_fail_pct = 5.0
        self.speed_fail_min = 0.8
        self.speed_fail_max = 1.2
        self.speed_fail_slow_pct = 50.0
        self.speed_fail_fast_pct = 50.0
        self.current_speed_jitter = 1.0
        self.neighbor_active_map = {}

        # Loop Song
        self.loop_song = False

        # Transposition Macro
        self.transposition = 0

        self.is_playing = False
        self.is_paused = False
        self._stop_requested = False
        self.is_pedal_down = False

        self.active_keys = {}
        self.current_velocity_idx = None

    def set_midi_data(self, data: dict):
        self.notes = data.get("notes", [])
        self.pedals = data.get("pedals", [])
        self.duration = float(data.get("duration", 0.0))

    def set_speed(self, speed_val: int):
        self.speed_percent = max(1, min(1000, speed_val))

    def set_settings(self, no_doubles: bool, velocity: bool, keys88: bool, sustain: bool, accurate_gate: bool, speed_protection: bool):
        self.no_doubles = no_doubles
        self.velocity_enabled = velocity
        self.keys_88 = keys88
        self.sustain = sustain
        self.accurate_gate = accurate_gate
        self.speed_protection = speed_protection

    def set_human_fail_settings(
        self, 
        enabled: bool, 
        speed_fail_pct: float, 
        transpose_fail_pct: float,
        speed_fail_min: float = 0.8,
        speed_fail_max: float = 1.2,
        speed_fail_slow_pct: float = 50.0,
        speed_fail_fast_pct: float = 50.0
    ):
        self.human_fail = enabled
        self.speed_fail_pct = max(0.0, float(speed_fail_pct))
        self.transpose_fail_pct = max(0.0, float(transpose_fail_pct))
        self.speed_fail_min = max(0.01, min(1.0, float(speed_fail_min)))
        self.speed_fail_max = max(1.0, float(speed_fail_max))
        self.speed_fail_slow_pct = max(0.0, float(speed_fail_slow_pct))
        self.speed_fail_fast_pct = max(0.0, float(speed_fail_fast_pct))

    def set_loop_song(self, enabled: bool):
        self.loop_song = bool(enabled)

    def set_transposition(self, transpose_val: int):
        self.transposition = max(-24, min(24, int(transpose_val)))

    def _prepare_events(self):
        if not self.notes:
            return []

        valid_notes = []
        for n in self.notes:
            p = int(n["pitch"]) + self.transposition
            if not self.keys_88 and (p < 36 or p > 96):
                continue
            if self.keys_88 and (p < 21 or p > 108):
                continue
            if p < 21 or p > 108 or p not in MIDI_MAP:
                continue
            note_copy = dict(n)
            note_copy["pitch"] = p
            valid_notes.append(note_copy)

        if not valid_notes:
            return []

        if self.no_doubles:
            filtered = []
            valid_notes.sort(key=lambda x: x["start"])
            last_starts = {}
            for n in valid_notes:
                p = n["pitch"]
                st = n["start"]
                if p in last_starts and abs(st - last_starts[p]) <= 0.005:
                    continue
                last_starts[p] = st
                filtered.append(n)
            valid_notes = filtered

        if self.accurate_gate:
            raw_actions = []
            for n in valid_notes:
                p = n["pitch"]
                st = n["start"]
                dur = max(0.02, n.get("duration", 0.05))
                vel = n.get("velocity", 64)
                end = st + dur
                raw_actions.append((st, 2, "note_on", (p, vel)))
                raw_actions.append((end, 1, "note_off", p))

            if self.sustain and self.pedals:
                for ped in self.pedals:
                    t = ped["time"]
                    is_down = ped["down"]
                    prio = 0 if is_down else 3
                    raw_actions.append((t, prio, "pedal", is_down))

            raw_actions.sort(key=lambda x: (x[0], x[1]))
            return [(item[0], item[2], item[3]) for item in raw_actions]
        else:
            chord_events = []
            for n in valid_notes:
                st = n["start"]
                p = n["pitch"]
                vel = n.get("velocity", 64)
                if not chord_events or (st - chord_events[-1][0] > 0.005):
                    chord_events.append((st, [p], vel))
                else:
                    chord_events[-1][1].append(p)

            unified = []
            for t, pitches, vel in chord_events:
                unified.append((t, "chord", (pitches, vel)))

            if self.sustain and self.pedals:
                for ped in self.pedals:
                    unified.append((ped["time"], "pedal", ped["down"]))

            def get_evt_prio(e):
                t, evt_t, d = e
                if evt_t == "pedal" and d is True:
                    return (t, 0)
                if evt_t == "chord":
                    return (t, 1)
                return (t, 2)

            unified.sort(key=get_evt_prio)
            return unified

    def _apply_velocity(self, vel: int):
        if not self.velocity_enabled:
            return

        idx = max(0, min(31, int((vel / 127.0) * 31)))
        if idx == self.current_velocity_idx:
            return
        self.current_velocity_idx = idx

        sc = VELOCITY_MAP[idx]
        _send_key(SCAN_ALT, False)
        time.sleep(0.002)
        _send_key(sc, False)
        time.sleep(0.005)
        _send_key(sc, True)
        time.sleep(0.002)
        _send_key(SCAN_ALT, True)
        time.sleep(0.002)

    def _play_chord_tap(self, pitches: list[int]):
        regular_keys = []
        shift_keys = []
        ctrl_keys = []

        for p in pitches:
            if p in MIDI_MAP:
                scancode, mod = MIDI_MAP[p]
                if mod == "shift":
                    shift_keys.append(scancode)
                elif mod == "ctrl":
                    ctrl_keys.append(scancode)
                else:
                    regular_keys.append(scancode)

        if regular_keys:
            for sc in regular_keys:
                _send_key(sc, False)
            time.sleep(0.010)
            for sc in regular_keys:
                _send_key(sc, True)

        if shift_keys:
            _send_key(SCAN_SHIFT, False)
            time.sleep(0.004)
            for sc in shift_keys:
                _send_key(sc, False)
            time.sleep(0.010)
            for sc in shift_keys:
                _send_key(sc, True)
            time.sleep(0.002)
            _send_key(SCAN_SHIFT, True)

        if ctrl_keys:
            _send_key(SCAN_CTRL, False)
            time.sleep(0.004)
            for sc in ctrl_keys:
                _send_key(sc, False)
            time.sleep(0.010)
            for sc in ctrl_keys:
                _send_key(sc, True)
            time.sleep(0.002)
            _send_key(SCAN_CTRL, True)

    def _raw_note_on(self, pitch: int):
        if pitch not in MIDI_MAP:
            return
        sc, mod = MIDI_MAP[pitch]
        if mod == "shift":
            _send_key(SCAN_SHIFT, False)
            _send_key(sc, False)
            _send_key(SCAN_SHIFT, True)
        elif mod == "ctrl":
            _send_key(SCAN_CTRL, False)
            _send_key(sc, False)
            _send_key(SCAN_CTRL, True)
        else:
            _send_key(sc, False)
        self.active_keys[sc] = self.active_keys.get(sc, 0) + 1

    def _raw_note_off(self, pitch: int):
        if pitch not in MIDI_MAP:
            return
        sc, _ = MIDI_MAP[pitch]
        if sc in self.active_keys:
            if self.active_keys[sc] <= 1:
                _send_key(sc, True)
                del self.active_keys[sc]
            else:
                self.active_keys[sc] -= 1

    def _handle_note_on(self, pitch: int):
        self._raw_note_on(pitch)
        if self.human_fail and (random.random() * 100.0 < self.transpose_fail_pct):
            neighbor = pitch + random.choice([-1, 1])
            min_p = 21 if self.keys_88 else 36
            max_p = 108 if self.keys_88 else 96
            if min_p <= neighbor <= max_p and neighbor in MIDI_MAP:
                self._raw_note_on(neighbor)
                self.neighbor_active_map.setdefault(pitch, []).append(neighbor)

    def _handle_note_off(self, pitch: int):
        self._raw_note_off(pitch)
        if pitch in self.neighbor_active_map:
            for nb in self.neighbor_active_map.pop(pitch):
                self._raw_note_off(nb)

    def _release_all_keys(self):
        for sc in list(self.active_keys.keys()):
            _send_key(sc, True)
        self.active_keys.clear()
        self.neighbor_active_map.clear()
        if self.is_pedal_down:
            _send_key(SCAN_SPACE, True)
            self.is_pedal_down = False
        _send_key(SCAN_SHIFT, True)
        _send_key(SCAN_CTRL, True)
        _send_key(SCAN_ALT, True)
        self.current_velocity_idx = None
        self.current_speed_jitter = 1.0

    def run(self):
        events = self._prepare_events()
        if not events:
            self.finished.emit()
            return

        self.is_playing = True
        self.is_paused = False
        self._stop_requested = False
        self.is_pedal_down = False
        self.active_keys.clear()
        self.neighbor_active_map.clear()
        self.current_velocity_idx = None
        self.current_speed_jitter = 1.0

        try:
            winmm.timeBeginPeriod(1)
        except Exception:
            pass

        total_events = len(events)
        try:
            while not self._stop_requested:
                current_virtual_time = 0.0
                last_real_time = time.perf_counter()
                event_idx = 0
                last_progress_emit = -1.0
                last_note_time = 0.0
                last_target_time = -1.0

                while event_idx < total_events and not self._stop_requested:
                    now_perf = time.perf_counter()
                    dt_real = now_perf - last_real_time
                    last_real_time = now_perf

                    if self.is_paused:
                        time.sleep(0.02)
                        last_real_time = time.perf_counter()
                        continue

                    speed_mult = max(0.01, (self.speed_percent / 100.0) * self.current_speed_jitter)
                    current_virtual_time += dt_real * speed_mult

                    if current_virtual_time - last_progress_emit >= 0.04 or last_progress_emit < 0:
                        self.progress_changed.emit(min(self.duration, current_virtual_time))
                        last_progress_emit = current_virtual_time

                    target_time = events[event_idx][0]
                    if current_virtual_time >= target_time:
                        played_tick_pitches = []
                        while event_idx < total_events and current_virtual_time >= events[event_idx][0]:
                            t_evt, evt_type, data = events[event_idx]

                            if evt_type in ("note_on", "chord"):
                                if self.human_fail:
                                    if random.random() * 100.0 < self.speed_fail_pct:
                                        total_w = self.speed_fail_slow_pct + self.speed_fail_fast_pct
                                        if total_w <= 0:
                                            pick_slow = (random.random() < 0.5)
                                        else:
                                            pick_slow = (random.random() * total_w < self.speed_fail_slow_pct)

                                        if pick_slow:
                                            low = min(self.speed_fail_min, 1.0)
                                            self.current_speed_jitter = random.uniform(low, 1.0)
                                        else:
                                            high = max(1.0, self.speed_fail_max)
                                            self.current_speed_jitter = random.uniform(1.0, high)
                                    else:
                                        self.current_speed_jitter = 1.0

                                if self.speed_protection:
                                    now = time.perf_counter()
                                    delta = now - last_note_time
                                    min_gap = 0.001 if abs(t_evt - last_target_time) < 0.002 else 0.004
                                    if delta < min_gap:
                                        wait_time = min_gap - delta
                                        time.sleep(wait_time)
                                        last_real_time = time.perf_counter()
                                    last_note_time = time.perf_counter()
                                    last_target_time = t_evt

                                if evt_type == "note_on":
                                    pitch, vel = data
                                    self._apply_velocity(vel)
                                    self._handle_note_on(pitch)
                                    played_tick_pitches.append(pitch)
                                elif evt_type == "chord":
                                    pitches, vel = data
                                    self._apply_velocity(vel)
                                    chord_to_play = list(pitches)
                                    if self.human_fail:
                                        for p in pitches:
                                            if random.random() * 100.0 < self.transpose_fail_pct:
                                                nb = p + random.choice([-1, 1])
                                                min_p = 21 if self.keys_88 else 36
                                                max_p = 108 if self.keys_88 else 96
                                                if min_p <= nb <= max_p and nb not in chord_to_play:
                                                    chord_to_play.append(nb)
                                    self._play_chord_tap(chord_to_play)
                                    played_tick_pitches.extend(pitches)
                            elif evt_type == "note_off":
                                self._handle_note_off(data)
                            elif evt_type == "pedal":
                                if data and not self.is_pedal_down:
                                    _send_key(SCAN_SPACE, False)
                                    self.is_pedal_down = True
                                elif not data and self.is_pedal_down:
                                    _send_key(SCAN_SPACE, True)
                                    self.is_pedal_down = False

                            event_idx += 1

                        if played_tick_pitches:
                            unique_pitches = sorted(set(played_tick_pitches))
                            self.notes_clicked.emit(unique_pitches)
                    else:
                        time_diff = (target_time - current_virtual_time) / speed_mult
                        if time_diff > 0.005:
                            time.sleep(min(0.01, time_diff - 0.002))
                        else:
                            time.sleep(0.0005)

                if not self._stop_requested and self.loop_song:
                    self._release_all_keys()
                    time.sleep(0.08)
                    continue
                else:
                    break
        finally:
            self._release_all_keys()
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
            self._release_all_keys()

    def resume(self):
        if self.is_playing and self.is_paused:
            self.is_paused = False

    def stop_playback(self):
        self._stop_requested = True
        self.is_playing = False
        self.is_paused = False
        self._release_all_keys()
        self.wait(300)