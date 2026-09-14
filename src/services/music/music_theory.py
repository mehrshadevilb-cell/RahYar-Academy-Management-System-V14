"""Small, dependency-free music-theory engine.

Turns a key ("Am") and a roman-numeral progression ("i - iv - v - iv")
into concrete chords, then into MIDI note voicings (close-position piano,
simplified jazz rootless, or a guitar-style arpeggio pattern). Fully
deterministic so results never depend on an external AI model - if an
LLM parsed the same request incorrectly, the wrong chord would still be
"correct" music theory relative to what it produced. This module removes
that failure mode for the actual notes.
"""

from __future__ import annotations

import re

_NOTE_TO_PC = {
    "C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4,
    "F": 5, "F#": 6, "GB": 6, "G": 7, "G#": 8, "AB": 8, "A": 9,
    "A#": 10, "BB": 10, "B": 11,
}

MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
NATURAL_MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]

ROMAN_TO_DEGREE = {"i": 0, "ii": 1, "iii": 2, "iv": 3, "v": 4, "vi": 5, "vii": 6}

# Chord quality -> intervals (semitones from chord root): triads + sevenths.
CHORD_INTERVALS = {
    "maj": [0, 4, 7],
    "min": [0, 3, 7],
    "dim": [0, 3, 6],
    "aug": [0, 4, 8],
    "maj7": [0, 4, 7, 11],
    "min7": [0, 3, 7, 10],
    "dom7": [0, 4, 7, 10],
    "m7b5": [0, 3, 6, 10],
    "dim7": [0, 3, 6, 9],
}

# Diatonic minor-quality scale degrees within each mode's default triads.
_MINOR_DEGREES_IN_MAJOR_KEY = {1, 2, 5}  # ii, iii, vi
_DIM_DEGREE_IN_MAJOR_KEY = 6  # vii
_MINOR_DEGREES_IN_MINOR_KEY = {0, 3, 4}  # i, iv, v (natural minor)
_DIM_DEGREE_IN_MINOR_KEY = 1  # ii


class MusicTheoryError(ValueError):
    pass


def parse_key(key_text: str) -> tuple[int, str]:
    """'Am' -> (9, 'minor'); 'C' -> (0, 'major'); 'F#m' -> (6, 'minor')."""
    text = key_text.strip()
    match = re.match(r"^([A-Ga-g])([#bB]?)(m|min|minor)?$", text)
    if not match:
        raise MusicTheoryError(f"کلید نامعتبر: {key_text}")
    letter, accidental, minor_flag = match.groups()
    accidental = accidental or ""
    if accidental == "#":
        name = letter.upper() + "#"
    elif accidental.lower() == "b":
        name = letter.upper() + "B"
    else:
        name = letter.upper()
    if name not in _NOTE_TO_PC:
        raise MusicTheoryError(f"کلید نامعتبر: {key_text}")
    return _NOTE_TO_PC[name], ("minor" if minor_flag else "major")


def _default_quality_for_degree(degree: int, mode: str, is_upper: bool) -> str:
    if mode == "major":
        if degree == _DIM_DEGREE_IN_MAJOR_KEY:
            base = "dim"
        elif degree in _MINOR_DEGREES_IN_MAJOR_KEY:
            base = "min"
        else:
            base = "maj"
    else:
        if degree == _DIM_DEGREE_IN_MINOR_KEY:
            base = "dim"
        elif degree in _MINOR_DEGREES_IN_MINOR_KEY:
            base = "min"
        else:
            base = "maj"

    # An explicit case override (e.g. writing 'V' over natural minor)
    # forces the major/dominant sound even where the diatonic default
    # would be minor, and vice versa - this is how real roman-numeral
    # notation is used (borrowed/secondary dominants).
    if is_upper and base == "min":
        return "maj"
    if not is_upper and base == "maj":
        return "min"
    return base


def roman_to_chord(roman: str, key_pc: int, mode: str) -> tuple[int, str]:
    """Returns (root_pitch_class, quality) for one roman-numeral token,
    e.g. 'iv', 'V7', 'bVII'."""
    text = roman.strip()
    match = re.match(r"^(b?)([ivIV]+)(maj7|m7b5|dim7|dom7|dim|aug|7)?$", text)
    if not match:
        raise MusicTheoryError(f"درجه آکورد نامعتبر: {roman}")
    flat, numeral, suffix = match.groups()
    degree_key = numeral.lower()
    if degree_key not in ROMAN_TO_DEGREE:
        raise MusicTheoryError(f"درجه آکورد نامعتبر: {roman}")
    degree = ROMAN_TO_DEGREE[degree_key]
    is_upper = numeral == numeral.upper()

    scale = NATURAL_MINOR_SCALE if mode == "minor" else MAJOR_SCALE
    root_pc = (key_pc + scale[degree] + (-1 if flat else 0)) % 12

    if suffix == "7":
        quality = "dom7" if is_upper else "min7"
    elif suffix:
        quality = suffix
    else:
        quality = _default_quality_for_degree(degree, mode, is_upper)

    return root_pc, quality


def parse_progression(progression_text: str, key_pc: int, mode: str) -> list[tuple[int, str]]:
    tokens = [t for t in re.split(r"[\s\-–,]+", progression_text.strip()) if t]
    if not tokens:
        raise MusicTheoryError("پیشرفت آکوردی خالی است.")
    if len(tokens) > 32:
        raise MusicTheoryError("حداکثر ۳۲ آکورد/میزان در یک درخواست پشتیبانی می‌شود.")
    return [roman_to_chord(token, key_pc, mode) for token in tokens]


def voice_close(root_pc: int, quality: str, base_octave: int = 4) -> list[int]:
    """Simple root-position stacked voicing (root, 3rd, 5th[, 7th])."""
    base = base_octave * 12 + root_pc
    return [base + interval for interval in CHORD_INTERVALS[quality]]


def voice_jazz_rootless(root_pc: int, quality: str, base_octave: int = 4) -> list[int]:
    """Simplified rootless jazz voicing: 3rd, 5th, 7th, plus an added
    9th on top (the root is intentionally omitted - a bassist/left hand
    is assumed to cover it, as in real jazz comping). Triad-only
    qualities are upgraded to their natural 7th first."""
    sevenths_for_triad = {"maj": "maj7", "min": "min7", "dim": "m7b5", "aug": "maj7"}
    quality7 = quality if len(CHORD_INTERVALS.get(quality, [])) == 4 else sevenths_for_triad.get(quality, quality)
    intervals = CHORD_INTERVALS.get(quality7, CHORD_INTERVALS[quality])

    base = base_octave * 12 + root_pc
    ninth_interval = 13 if quality7 in ("dim7", "m7b5") else 14
    upper_structure = intervals[1:] if len(intervals) == 4 else intervals
    notes = [base + interval for interval in upper_structure]
    notes.append(base + ninth_interval)
    return sorted(notes)


def arpeggio_pattern(root_pc: int, quality: str, base_octave: int = 3) -> list[int]:
    """8-note pattern (eighth notes over one 4/4 bar): root, octave,
    fifth, octave, third, octave, fifth, octave - a common minor-key
    guitar/trap riff shape built from the chord's own tones."""
    intervals = CHORD_INTERVALS[quality]
    root = base_octave * 12 + root_pc
    third = root + intervals[1]
    fifth = root + intervals[2]
    octave = root + 12
    return [root, octave, fifth, octave, third, octave, fifth, octave]
