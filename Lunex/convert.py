# 61 Standard Keys (C2 to C7: MIDI 36 to 96)
NOTE_MAP_61 = {
    36: '1', 37: '!', 38: '2', 39: '@', 40: '3', 41: '4', 42: '$', 43: '5', 44: '%', 45: '6', 46: '^', 47: '7',
    48: '8', 49: '*', 50: '9', 51: '(', 52: '0', 53: 'q', 54: 'Q', 55: 'w', 56: 'W', 57: 'e', 58: 'E', 59: 'r',
    60: 't', 61: 'T', 62: 'y', 63: 'Y', 64: 'u', 65: 'i', 66: 'I', 67: 'o', 68: 'O', 69: 'p', 70: 'P', 71: 'a',
    72: 's', 73: 'S', 74: 'd', 75: 'D', 76: 'f', 77: 'g', 78: 'G', 79: 'h', 80: 'H', 81: 'j', 82: 'J', 83: 'k',
    84: 'l', 85: 'L', 86: 'z', 87: 'Z', 88: 'x', 89: 'c', 90: 'C', 91: 'v', 92: 'V', 93: 'b', 94: 'B', 95: 'n',
    96: 'm'
}

# 88 Keys: Lower Register (A0 to B1: MIDI 21 to 35)
NOTE_MAP_88_LOWER = {
    21: '1',  # A0
    22: '2',  # A#0
    23: '3',  # B0
    24: '4',  # C1
    25: '5',  # C#1
    26: '6',  # D1
    27: '7',  # D#1
    28: '8',  # E1
    29: '9',  # F1
    30: '0',  # F#1
    31: 'q',  # G1
    32: 'w',  # G#1
    33: 'e',  # A1
    34: 'r',  # A#1
    35: 't',  # B1
}

# 88 Keys: Higher Register (C#7 to C8: MIDI 97 to 108)
NOTE_MAP_88_HIGHER = {
    97: 'y',   # C#7
    98: 'u',   # D7
    99: 'i',   # D#7
    100: 'o',  # E7
    101: 'p',  # F7
    102: 'a',  # F#7
    103: 's',  # G7
    104: 'd',  # G#7
    105: 'f',  # A7
    106: 'g',  # A#7
    107: 'h',  # B7
    108: 'j',  # C8
}


def _format_single_chord(pitches: list[int]) -> str:
    
    lower_keys = [NOTE_MAP_88_LOWER[p] for p in sorted(pitches) if p in NOTE_MAP_88_LOWER]
    normal_keys = [NOTE_MAP_61[p] for p in sorted(pitches) if p in NOTE_MAP_61]
    higher_keys = [NOTE_MAP_88_HIGHER[p] for p in sorted(pitches) if p in NOTE_MAP_88_HIGHER]

    lower_str = "".join(lower_keys)
    normal_str = "".join(normal_keys)
    higher_str = "".join(higher_keys)

    total_notes = len(lower_keys) + len(normal_keys) + len(higher_keys)
    if total_notes == 0:
        return ""

    
    if total_notes == 1:
        if lower_str:
            return f":{lower_str}"
        elif higher_str:
            return f":{higher_str}"
        else:
            return normal_str

    
    parts = []

    
    if lower_str:
        parts.append(f":{lower_str}")

    
    if normal_str:
        
        if lower_str:
            parts.append(f"'{normal_str}")
        else:
            parts.append(normal_str)

    
    if higher_str:
        parts.append(f":{higher_str}")

    return f"[{''.join(parts)}]"


def convert_midi_to_qwerty(
    notes: list[dict], 
    keys_88: bool = False, 
    time_threshold: float = 0.015,
    tempos: list[dict] = None,
    include_tempo: bool = False,
    transpose: int = 0
) -> str:
    if not notes:
        return ""

    transpose_val = max(-24, min(24, int(transpose)))
    valid_notes = []

    for n in notes:
        p = int(n["pitch"]) + transpose_val
        if not keys_88:
            
            if 36 <= p <= 96:
                note_data = dict(n)
                note_data["pitch"] = p
                valid_notes.append(note_data)
        else:
            # Limit of 88 Keys
            if 21 <= p <= 108:
                note_data = dict(n)
                note_data["pitch"] = p
                valid_notes.append(note_data)

    if not valid_notes:
        return ""

    valid_notes.sort(key=lambda x: (x["start"], x["pitch"]))

    
    chords = []
    for n in valid_notes:
        st = float(n["start"])
        p = int(n["pitch"])
        if not chords or (st - chords[-1]["start"] > time_threshold):
            chords.append({"start": st, "pitches": [p]})
        else:
            if p not in chords[-1]["pitches"]:
                chords[-1]["pitches"].append(p)

    if not include_tempo or not tempos:
        output_tokens = []
        for chord in chords:
            token = _format_single_chord(chord["pitches"])
            if token:
                output_tokens.append(token)
        return " ".join(output_tokens) + " " if output_tokens else ""

    
    initial_bpm = 120
    current_bpm = None
    tempo_changes = []

    for t in tempos:
        bpm = int(round(t["bpm"]))
        if current_bpm is None:
            current_bpm = bpm
            initial_bpm = bpm
        elif t["time"] <= 0.01:
            current_bpm = bpm
            initial_bpm = bpm
        else:
            if bpm != current_bpm:
                tempo_changes.append({"time": float(t["time"]), "bpm": bpm})
                current_bpm = bpm

    events = []
    for c in chords:
        events.append((c["start"], 1, "chord", c["pitches"]))

    for tc in tempo_changes:
        events.append((tc["time"], 0, "tempo", tc["bpm"]))

    events.sort(key=lambda x: (x[0], x[1]))

    result_parts = [f"Tempo: {initial_bpm} BPM\n"]
    active_bpm = initial_bpm
    current_line = []

    for evt in events:
        _, _, evt_type, data = evt

        if evt_type == "tempo":
            new_bpm = data
            diff = new_bpm - active_bpm
            if diff != 0:
                pct = abs(diff)
                direction = "faster" if diff > 0 else "slower"
                if current_line:
                    result_parts.append(" ".join(current_line) + " ")
                    current_line = []
                result_parts.append(f"\n{pct}% {direction} - BPM changed to {new_bpm}\n")
                active_bpm = new_bpm

        elif evt_type == "chord":
            token = _format_single_chord(data)
            if token:
                current_line.append(token)

    if current_line:
        result_parts.append(" ".join(current_line) + " ")

    return "".join(result_parts)