"""Turns a natural chord-progression request into a downloadable MIDI
file: block/jazz-voiced piano chords, or an arpeggiated nylon-guitar
riff. Pure music theory + MIDI writing - deterministic, no external AI
call, no audio synthesis.

Real rendered audio (an actual guitar/piano *sound*, not MIDI note
data) is intentionally out of scope here: it needs a synthesizer binary
(e.g. FluidSynth) plus a SoundFont asset (100+ MB), which is a separate
infrastructure decision (new system dependency, larger Docker image)
and should not be added silently.
"""

from __future__ import annotations

from src.services.music.midi_writer import MidiFile
from src.services.music.music_theory import (
    MusicTheoryError,
    arpeggio_pattern,
    parse_key,
    parse_progression,
    voice_close,
    voice_jazz_rootless,
)

GM_PROGRAM = {
    "nylon_guitar": 24,  # General MIDI: Acoustic Guitar (nylon)
    "piano": 0,  # General MIDI: Acoustic Grand Piano
}

MAX_CHORDS = 16
MIN_TEMPO = 40
MAX_TEMPO = 220
MAX_LOOP_COUNT = 8


class MusicGeneratorError(ValueError):
    pass


class MusicGeneratorService:
    def generate(
        self,
        *,
        key_text: str,
        progression_text: str,
        instrument: str,
        voicing: str = "close",
        tempo: int = 120,
        loop_count: int = 1,
    ) -> bytes:
        """Returns the raw bytes of a Standard MIDI File. One chord in
        the progression = one 4/4 bar. Raises MusicGeneratorError on any
        invalid input - callers must show this message to the user
        as-is (it's already Persian and user-safe)."""
        if instrument not in GM_PROGRAM:
            raise MusicGeneratorError(f"ساز پشتیبانی نمی‌شود: {instrument}")
        if not (MIN_TEMPO <= tempo <= MAX_TEMPO):
            raise MusicGeneratorError(f"تمپو باید بین {MIN_TEMPO} و {MAX_TEMPO} باشد.")
        if not (1 <= loop_count <= MAX_LOOP_COUNT):
            raise MusicGeneratorError(f"تعداد تکرار لوپ باید بین ۱ و {MAX_LOOP_COUNT} باشد.")

        try:
            key_pc, mode = parse_key(key_text)
            chords = parse_progression(progression_text, key_pc, mode)
        except MusicTheoryError as exc:
            raise MusicGeneratorError(str(exc)) from exc

        if len(chords) > MAX_CHORDS:
            raise MusicGeneratorError(f"حداکثر {MAX_CHORDS} آکورد/میزان پشتیبانی می‌شود.")

        midi = MidiFile(ticks_per_beat=480)
        track = midi.add_track()
        ticks_per_bar = midi.ticks_per_beat * 4  # 4/4 only, for now

        track.time_signature(0, 4, 4)
        track.set_tempo(0, tempo)
        track.track_name(0, "RahYar Generated Part")
        track.program_change(0, channel=0, program=GM_PROGRAM[instrument])

        tick = 0
        for _ in range(loop_count):
            for root_pc, quality in chords:
                if instrument == "nylon_guitar":
                    notes = arpeggio_pattern(root_pc, quality, base_octave=3)
                    step = ticks_per_bar // len(notes)
                    for index, note in enumerate(notes):
                        on_tick = tick + index * step
                        track.note_on(on_tick, 0, note, 95)
                        track.note_off(on_tick + step, 0, note, 0)
                else:
                    voicer = voice_jazz_rootless if voicing == "jazz" else voice_close
                    for note in voicer(root_pc, quality):
                        track.note_on(tick, 0, note, 85)
                        track.note_off(tick + ticks_per_bar, 0, note, 0)
                tick += ticks_per_bar

        return midi.to_bytes()
