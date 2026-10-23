import time
import ctypes
from PyQt6.QtCore import QThread, pyqtSignal

try:
    import rtmidi
except ImportError:
    rtmidi = None

winmm = ctypes.windll.winmm


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