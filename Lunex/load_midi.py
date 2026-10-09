import os
from symusic import Score


class MidiLoader:
    @staticmethod
    def load(file_path: str) -> dict:
        if not file_path.lower().endswith(".mid"):
            raise ValueError("Unsupported file format. Only .mid files are accepted.")

        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File does not exist: {file_path}")

        score = Score(file_path)
        try:
            score = score.to("second")
        except Exception:
            pass

        raw_notes = []
        pedal_events = []

        for track in score.tracks:
            for note in track.notes:
                pitch = int(note.pitch)
                if 21 <= pitch <= 108:
                    raw_notes.append({
                        "start": float(note.start),
                        "pitch": pitch,
                        "duration": float(note.duration),
                        "velocity": int(note.velocity)
                    })

            if hasattr(track, "pedals") and len(track.pedals) > 0:
                for ped in track.pedals:
                    p_start = float(getattr(ped, "time", getattr(ped, "start", 0.0)))
                    p_dur = float(getattr(ped, "duration", 0.0))
                    pedal_events.append({"time": p_start, "down": True})
                    pedal_events.append({"time": p_start + p_dur, "down": False})
            elif hasattr(track, "controls"):
                for ctrl in track.controls:
                    if getattr(ctrl, "number", 0) == 64:
                        c_time = float(getattr(ctrl, "time", getattr(ctrl, "start", 0.0)))
                        val = getattr(ctrl, "value", 0)
                        pedal_events.append({"time": c_time, "down": (val >= 64)})

        if not raw_notes:
            raise ValueError("No playable piano notes (A0 - C8) found in this MIDI.")

        raw_notes.sort(key=lambda x: x["start"])
        pedal_events.sort(key=lambda x: x["time"])
        duration = float(score.end())

        
        raw_tempos = []
        if hasattr(score, "tempos") and len(score.tempos) > 0:
            for t in score.tempos:
                t_time = float(getattr(t, "time", getattr(t, "start", 0.0)))
                t_qpm = float(getattr(t, "qpm", getattr(t, "bpm", 120.0)))
                raw_tempos.append({"time": t_time, "bpm": round(t_qpm)})

        raw_tempos.sort(key=lambda x: x["time"])

        
        cleaned_tempos = []
        last_bpm = None
        for t in raw_tempos:
            bpm = int(round(t["bpm"]))
            if bpm <= 0:
                bpm = 120
            if last_bpm is None or bpm != last_bpm:
                cleaned_tempos.append({"time": t["time"], "bpm": bpm})
                last_bpm = bpm

        if not cleaned_tempos:
            cleaned_tempos = [{"time": 0.0, "bpm": 120}]

        return {
            "score": score,
            "notes": raw_notes,
            "pedals": pedal_events,
            "tempos": cleaned_tempos,
            "path": os.path.abspath(file_path),
            "name": os.path.basename(file_path),
            "duration": duration,
            "notes_count": len(raw_notes),
        }