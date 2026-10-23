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

TAP_DURATION_SEC = 0.010
NOTES_UI_EMIT_INTERVAL = 0.10

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
INPUT_SIZE = ctypes.sizeof(INPUT)

_INPUT_CACHE: dict[tuple[int, bool], INPUT] = {}
_ARRAY_TYPE_CACHE: dict[int, type] = {}


def _make_input(scancode: int, is_up: bool = False) -> INPUT:
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if is_up else 0)
    return INPUT(
        type=INPUT_KEYBOARD,
        u=INPUT_UNION(
            ki=KEYBDINPUT(
                wVk=0,
                wScan=scancode,
                dwFlags=flags,
                time=0,
                dwExtraInfo=0,
            )
        ),
    )


def _get_cached_input(scancode: int, is_up: bool = False) -> INPUT:
    key = (scancode, is_up)
    inp = _INPUT_CACHE.get(key)
    if inp is None:
        inp = _make_input(scancode, is_up)
        _INPUT_CACHE[key] = inp
    return inp


def _send_key(scancode: int, is_up: bool = False):
    inp = _get_cached_input(scancode, is_up)
    user32.SendInput(1, ctypes.byref(inp), INPUT_SIZE)


def _send_keys_batch(events: list[tuple[int, bool]]):
    n = len(events)
    if n == 0:
        return
    if n == 1:
        sc, is_up = events[0]
        inp = _get_cached_input(sc, is_up)
        user32.SendInput(1, ctypes.byref(inp), INPUT_SIZE)
        return

    arr_type = _ARRAY_TYPE_CACHE.get(n)
    if arr_type is None:
        arr_type = INPUT * n
        _ARRAY_TYPE_CACHE[n] = arr_type

    arr = arr_type(*(_get_cached_input(sc, is_up) for sc, is_up in events))
    user32.SendInput(n, arr, INPUT_SIZE)


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


def _init_input_cache():
    all_scancodes = {SCAN_SHIFT, SCAN_CTRL, SCAN_ALT, SCAN_SPACE}
    all_scancodes.update(VELOCITY_MAP)
    for sc, _ in MIDI_MAP.values():
        all_scancodes.add(sc)
    for sc in all_scancodes:
        _INPUT_CACHE[(sc, False)] = _make_input(sc, False)
        _INPUT_CACHE[(sc, True)] = _make_input(sc, True)
    for size in range(1, 129):
        _ARRAY_TYPE_CACHE[size] = INPUT * size


_init_input_cache()


class MacroPlayer(QThread):
    finished = pyqtSignal()
    progress_changed = pyqtSignal(float)
    notes_clicked = pyqtSignal(list)
    auto_paused = pyqtSignal()
    sustain_changed = pyqtSignal(bool)

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

        # Human Fail & Perfectionist Mode
        self.human_fail = False
        self.perfectionist_mode = False
        self.speed_fail_pct = 1.0
        self.transpose_fail_pct = 5.0
        self.fail_notes_count = 1
        self.transpose_fail_mode = "Tick Fail"
        self.transpose_fail_delay_ms = 500
        self.speed_fail_min = 0.8
        self.speed_fail_max = 1.2
        self.speed_fail_slow_pct = 50.0
        self.speed_fail_fast_pct = 50.0
        self.current_speed_jitter = 1.0

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

        # batching and event caching
        self._batch_mode = False
        self._tick_input_buffer: list[tuple[int, bool]] = []
        self._cached_events: list | None = None
        self._events_dirty = True

    def invalidate_cache(self):
        self._cached_events = None
        self._events_dirty = True

    def set_midi_data(self, data: dict):
        new_notes = data.get("notes", [])
        new_pedals = data.get("pedals", [])
        new_duration = float(data.get("duration", 0.0))
        if (
            self.notes is not new_notes
            or self.pedals is not new_pedals
            or self.duration != new_duration
        ):
            self.notes = new_notes
            self.pedals = new_pedals
            self.duration = new_duration
            self.invalidate_cache()

    def set_speed(self, speed_val: int):
        self.speed_percent = max(1, min(1000, speed_val))

    def set_settings(
        self,
        no_doubles: bool,
        velocity: bool,
        keys88: bool,
        sustain: bool,
        accurate_gate: bool,
        speed_protection: bool,
    ):
        if (
            self.no_doubles != no_doubles
            or self.keys_88 != keys88
            or self.sustain != sustain
            or self.accurate_gate != accurate_gate
        ):
            self.invalidate_cache()

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
        speed_fail_fast_pct: float = 50.0,
        perfectionist_mode: bool = False,
        transpose_fail_mode: str = "Tick Fail",
        transpose_fail_delay_ms: int = 500,
        fail_notes_count: int = 1,
    ):
        new_enabled = bool(enabled)
        new_perf = bool(perfectionist_mode)
        new_speed_pct = max(0.0, float(speed_fail_pct))
        new_trans_pct = max(0.0, float(transpose_fail_pct))
        new_fail_cnt = max(1, int(fail_notes_count))
        new_mode = (
            transpose_fail_mode
            if transpose_fail_mode in ("Tick Fail", "Before Fail", "After Fail")
            else "Tick Fail"
        )
        new_delay = max(1, int(transpose_fail_delay_ms))

        if (
            self.human_fail != new_enabled
            or self.transpose_fail_pct != new_trans_pct
            or self.fail_notes_count != new_fail_cnt
            or self.transpose_fail_mode != new_mode
            or self.transpose_fail_delay_ms != new_delay
        ):
            self.invalidate_cache()

        self.human_fail = new_enabled
        self.perfectionist_mode = new_perf
        self.speed_fail_pct = new_speed_pct
        self.transpose_fail_pct = new_trans_pct
        self.fail_notes_count = new_fail_cnt
        self.transpose_fail_mode = new_mode
        self.transpose_fail_delay_ms = new_delay
        self.speed_fail_min = max(0.01, min(1.0, float(speed_fail_min)))
        self.speed_fail_max = max(1.0, float(speed_fail_max))
        self.speed_fail_slow_pct = max(0.0, float(speed_fail_slow_pct))
        self.speed_fail_fast_pct = max(0.0, float(speed_fail_fast_pct))

    def set_loop_song(self, enabled: bool):
        self.loop_song = bool(enabled)

    def set_transposition(self, transpose_val: int):
        new_val = max(-24, min(24, int(transpose_val)))
        if self.transposition != new_val:
            self.transposition = new_val
            self.invalidate_cache()

    def _emit_keys(self, events: list[tuple[int, bool]]):
        if not events:
            return
        if self._batch_mode:
            buf = self._tick_input_buffer
            for sc, is_up in events:
                if (
                    buf
                    and not is_up
                    and sc in (SCAN_SHIFT, SCAN_CTRL)
                    and buf[-1] == (sc, True)
                ):
                    buf.pop()
                else:
                    buf.append((sc, is_up))
        else:
            _send_keys_batch(events)

    def _flush_input_buffer(self):
        if self._tick_input_buffer:
            _send_keys_batch(self._tick_input_buffer)
            self._tick_input_buffer.clear()

    def _pick_fail_pitches(
        self, base_pitch: int, count: int, existing_pitches: set[int]
    ) -> list[int]:
        count = max(1, int(count))
        min_p = 21 if self.keys_88 else 36
        max_p = 108 if self.keys_88 else 96

        result = []
        used = set(existing_pitches)
        used.add(base_pitch)

        low = base_pitch
        high = base_pitch

        while len(result) < count:
            candidates = []
            if low - 1 >= min_p:
                candidates.append(("low", low - 1))
            if high + 1 <= max_p:
                candidates.append(("high", high + 1))

            if not candidates:
                break

            unused_candidates = [
                c for c in candidates if c[1] not in used and c[1] in MIDI_MAP
            ]
            if unused_candidates:
                side, chosen_p = random.choice(unused_candidates)
            else:
                valid_candidates = [c for c in candidates if c[1] in MIDI_MAP]
                if not valid_candidates:
                    break
                side, chosen_p = random.choice(valid_candidates)

            if side == "low":
                low -= 1
            else:
                high += 1

            if chosen_p not in result and chosen_p in MIDI_MAP:
                result.append(chosen_p)
                used.add(chosen_p)

        return result

    def _prepare_events(self):
        if not self.human_fail and not self._events_dirty and self._cached_events is not None:
            return self._cached_events

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

        valid_notes.sort(key=lambda x: x["start"])

        if self.no_doubles:
            filtered = []
            last_starts = {}
            for n in valid_notes:
                p = n["pitch"]
                st = n["start"]
                if p in last_starts and abs(st - last_starts[p]) <= 0.005:
                    continue
                last_starts[p] = st
                filtered.append(n)
            valid_notes = filtered

        if not valid_notes:
            return []

        
        ticks = []
        for n in valid_notes:
            st = float(n["start"])
            if not ticks or (st - ticks[-1]["start"] > 0.005):
                ticks.append({"start": st, "notes": [n]})
            else:
                ticks[-1]["notes"].append(n)

        delay_sec = self.transpose_fail_delay_ms / 1000.0
        mode = self.transpose_fail_mode
        fail_count = max(1, self.fail_notes_count)

        prepared_notes = []
        min_event_time = 0.0

        for tick in ticks:
            t_start = tick["start"]
            t_notes = tick["notes"]
            existing_pitches = {int(x["pitch"]) for x in t_notes}

            mistake_triggered = (
                self.human_fail
                and self.transpose_fail_pct > 0.0
                and (random.random() * 100.0 < self.transpose_fail_pct)
            )

            fail_pitches = []
            base_note = None
            if mistake_triggered:
                base_note = random.choice(t_notes)
                fail_pitches = self._pick_fail_pitches(
                    int(base_note["pitch"]),
                    fail_count,
                    existing_pitches,
                )
                if not fail_pitches:
                    mistake_triggered = False

            for n in t_notes:
                prepared_notes.append({
                    "start": float(n["start"]),
                    "pitch": int(n["pitch"]),
                    "duration": max(0.02, float(n.get("duration", 0.05))),
                    "velocity": int(n.get("velocity", 64)),
                    "is_mistake": False,
                })

            if mistake_triggered and fail_pitches:
                base_dur = max(0.02, float(base_note.get("duration", 0.05)))
                base_vel = int(base_note.get("velocity", 64))

                for nb_pitch in fail_pitches:
                    if mode == "Tick Fail":
                        prepared_notes.append({
                            "start": t_start,
                            "pitch": nb_pitch,
                            "duration": base_dur,
                            "velocity": base_vel,
                            "is_mistake": True,
                        })
                    elif mode == "Before Fail":
                        m_start = t_start - delay_sec
                        if m_start < min_event_time:
                            min_event_time = m_start
                        m_dur = min(base_dur, max(0.02, delay_sec * 0.85))
                        prepared_notes.append({
                            "start": m_start,
                            "pitch": nb_pitch,
                            "duration": m_dur,
                            "velocity": base_vel,
                            "is_mistake": True,
                        })
                    elif mode == "After Fail":
                        m_start = t_start + delay_sec
                        m_dur = min(base_dur, 0.15)
                        prepared_notes.append({
                            "start": m_start,
                            "pitch": nb_pitch,
                            "duration": m_dur,
                            "velocity": base_vel,
                            "is_mistake": True,
                        })

        # Сдвиг времени при уходе Before Fail в минус
        time_shift = -min_event_time if min_event_time < 0.0 else 0.0
        if time_shift > 0.0:
            for pn in prepared_notes:
                pn["start"] += time_shift

        if self.accurate_gate:
            raw_actions = []
            for pn in prepared_notes:
                p = pn["pitch"]
                st = pn["start"]
                dur = pn["duration"]
                vel = pn["velocity"]
                is_m = pn["is_mistake"]
                end = st + dur
                raw_actions.append((st, 2, "note_on", (p, vel, is_m)))
                raw_actions.append((end, 1, "note_off", p))

            if self.sustain and self.pedals:
                for ped in self.pedals:
                    t = float(ped["time"]) + time_shift
                    is_down = ped["down"]
                    prio = 0 if is_down else 3
                    raw_actions.append((t, prio, "pedal", is_down))

            raw_actions.sort(key=lambda x: (x[0], x[1]))
            result = [(item[0], item[2], item[3]) for item in raw_actions]
        else:
            prepared_notes.sort(key=lambda x: (x["start"], 0 if not x["is_mistake"] else 1))
            chord_events = []
            for pn in prepared_notes:
                st = pn["start"]
                p = pn["pitch"]
                vel = pn["velocity"]
                is_m = pn["is_mistake"]
                if not chord_events or (st - chord_events[-1][0] > 0.005):
                    chord_events.append([st, [p], vel, is_m])
                else:
                    if p not in chord_events[-1][1]:
                        chord_events[-1][1].append(p)
                    if is_m:
                        chord_events[-1][3] = True

            raw_actions = []
            for t, pitches, vel, is_m in chord_events:
                raw_actions.append((t, 2, "chord", (pitches, vel, is_m)))
                raw_actions.append((t + TAP_DURATION_SEC, 1, "chord_off", pitches))

            if self.sustain and self.pedals:
                for ped in self.pedals:
                    t = float(ped["time"]) + time_shift
                    is_down = ped["down"]
                    prio = 0 if is_down else 3
                    raw_actions.append((t, prio, "pedal", is_down))

            raw_actions.sort(key=lambda x: (x[0], x[1]))
            result = [(item[0], item[2], item[3]) for item in raw_actions]

        if not self.human_fail:
            self._cached_events = result
            self._events_dirty = False

        return result

    def _apply_velocity(self, vel: int):
        if not self.velocity_enabled:
            return
        idx = max(0, min(31, int((vel / 127.0) * 31)))
        if idx == self.current_velocity_idx:
            return
        self.current_velocity_idx = idx
        sc = VELOCITY_MAP[idx]
        self._emit_keys([
            (SCAN_ALT, False),
            (sc, False),
            (sc, True),
            (SCAN_ALT, True),
        ])

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

        batch = []
        if regular_keys:
            for sc in regular_keys:
                batch.append((sc, False))
                self.active_keys[sc] = self.active_keys.get(sc, 0) + 1

        if shift_keys:
            batch.append((SCAN_SHIFT, False))
            for sc in shift_keys:
                batch.append((sc, False))
                self.active_keys[sc] = self.active_keys.get(sc, 0) + 1
            batch.append((SCAN_SHIFT, True))

        if ctrl_keys:
            batch.append((SCAN_CTRL, False))
            for sc in ctrl_keys:
                batch.append((sc, False))
                self.active_keys[sc] = self.active_keys.get(sc, 0) + 1
            batch.append((SCAN_CTRL, True))

        if batch:
            self._emit_keys(batch)

    def _release_chord_tap(self, pitches: list[int]):
        batch = []
        for p in pitches:
            if p in MIDI_MAP:
                sc, _ = MIDI_MAP[p]
                if sc in self.active_keys:
                    if self.active_keys[sc] <= 1:
                        batch.append((sc, True))
                        del self.active_keys[sc]
                    else:
                        self.active_keys[sc] -= 1
        if batch:
            self._emit_keys(batch)

    def _raw_note_on(self, pitch: int):
        if pitch not in MIDI_MAP:
            return
        sc, mod = MIDI_MAP[pitch]
        if mod == "shift":
            self._emit_keys([(SCAN_SHIFT, False), (sc, False), (SCAN_SHIFT, True)])
        elif mod == "ctrl":
            self._emit_keys([(SCAN_CTRL, False), (sc, False), (SCAN_CTRL, True)])
        else:
            self._emit_keys([(sc, False)])
        self.active_keys[sc] = self.active_keys.get(sc, 0) + 1

    def _raw_note_off(self, pitch: int):
        if pitch not in MIDI_MAP:
            return
        sc, _ = MIDI_MAP[pitch]
        if sc in self.active_keys:
            if self.active_keys[sc] <= 1:
                self._emit_keys([(sc, True)])
                del self.active_keys[sc]
            else:
                self.active_keys[sc] -= 1

    def _release_all_keys(self):
        self._tick_input_buffer.clear()
        batch = [(sc, True) for sc in list(self.active_keys.keys())]
        self.active_keys.clear()
        if self.is_pedal_down:
            batch.append((SCAN_SPACE, True))
            self.is_pedal_down = False
            self.sustain_changed.emit(False)
        batch.extend([
            (SCAN_SHIFT, True),
            (SCAN_CTRL, True),
            (SCAN_ALT, True),
        ])
        _send_keys_batch(batch)
        self.current_velocity_idx = None
        self.current_speed_jitter = 1.0

    def run(self):
        if not self.notes:
            self.finished.emit()
            return

        self.is_playing = True
        self.is_paused = False
        self._stop_requested = False
        self.is_pedal_down = False
        self.sustain_changed.emit(False)
        self.active_keys.clear()
        self._tick_input_buffer.clear()
        self.current_velocity_idx = None
        self.current_speed_jitter = 1.0

        try:
            winmm.timeBeginPeriod(1)
        except Exception:
            pass

        pending_ui_pitches: list[int] = []
        last_notes_emit = time.perf_counter()

        def flush_ui_notes():
            nonlocal pending_ui_pitches, last_notes_emit
            if pending_ui_pitches:
                self.notes_clicked.emit(pending_ui_pitches)
                pending_ui_pitches = []
                last_notes_emit = time.perf_counter()

        try:
            events = None
            while not self._stop_requested:
                if self.human_fail or events is None or self._events_dirty:
                    events = self._prepare_events()
                if not events:
                    break

                total_events = len(events)
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
                        flush_ui_notes()
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
                        tick_mistake_made = False
                        self._batch_mode = True

                        while event_idx < total_events and current_virtual_time >= events[event_idx][0]:
                            t_evt, evt_type, data = events[event_idx]

                            if evt_type in ("note_on", "chord"):
                                if self.human_fail:
                                    if random.random() * 100.0 < self.speed_fail_pct:
                                        total_w = self.speed_fail_slow_pct + self.speed_fail_fast_pct
                                        if total_w <= 0:
                                            pick_slow = random.random() < 0.5
                                        else:
                                            pick_slow = random.random() * total_w < self.speed_fail_slow_pct

                                        if pick_slow:
                                            low = min(self.speed_fail_min, 1.0)
                                            self.current_speed_jitter = random.uniform(low, 1.0)
                                        else:
                                            high = max(1.0, self.speed_fail_max)
                                            self.current_speed_jitter = random.uniform(1.0, high)
                                    else:
                                        self.current_speed_jitter = 1.0

                                if self.speed_protection:
                                    self._flush_input_buffer()
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
                                    pitch, vel, is_mistake = data
                                    self._apply_velocity(vel)
                                    self._raw_note_on(pitch)
                                    if is_mistake:
                                        tick_mistake_made = True
                                    played_tick_pitches.append(pitch)
                                elif evt_type == "chord":
                                    pitches, vel, is_mistake = data
                                    self._apply_velocity(vel)
                                    self._play_chord_tap(pitches)
                                    if is_mistake:
                                        tick_mistake_made = True
                                    played_tick_pitches.extend(pitches)

                            elif evt_type == "note_off":
                                self._raw_note_off(data)

                            elif evt_type == "chord_off":
                                self._release_chord_tap(data)

                            elif evt_type == "pedal":
                                if data and not self.is_pedal_down:
                                    self._emit_keys([(SCAN_SPACE, False)])
                                    self.is_pedal_down = True
                                    self.sustain_changed.emit(True)
                                elif not data and self.is_pedal_down:
                                    self._emit_keys([(SCAN_SPACE, True)])
                                    self.is_pedal_down = False
                                    self.sustain_changed.emit(False)

                            event_idx += 1

                            if tick_mistake_made and self.perfectionist_mode:
                                if event_idx < total_events and events[event_idx][0] > t_evt + 0.002:
                                    break

                        self._flush_input_buffer()
                        self._batch_mode = False

                        if played_tick_pitches:
                            unique_pitches = sorted(set(played_tick_pitches))
                            pending_ui_pitches.extend(unique_pitches)

                        now_emit_check = time.perf_counter()
                        if pending_ui_pitches and (now_emit_check - last_notes_emit >= NOTES_UI_EMIT_INTERVAL):
                            self.notes_clicked.emit(pending_ui_pitches)
                            pending_ui_pitches = []
                            last_notes_emit = now_emit_check

                        if tick_mistake_made and self.perfectionist_mode:
                            flush_ui_notes()
                            time.sleep(0.035)
                            self.is_paused = True
                            self._release_all_keys()
                            last_real_time = time.perf_counter()
                            self.auto_paused.emit()
                    else:
                        if pending_ui_pitches and (now_perf - last_notes_emit >= NOTES_UI_EMIT_INTERVAL):
                            self.notes_clicked.emit(pending_ui_pitches)
                            pending_ui_pitches = []
                            last_notes_emit = now_perf

                        time_diff = (target_time - current_virtual_time) / speed_mult
                        if time_diff > 0.005:
                            time.sleep(min(0.01, time_diff - 0.002))
                        else:
                            time.sleep(0.0005)

                flush_ui_notes()
                if not self._stop_requested and self.loop_song:
                    self._release_all_keys()
                    time.sleep(0.08)
                    continue
                else:
                    break
        finally:
            self._batch_mode = False
            flush_ui_notes()
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