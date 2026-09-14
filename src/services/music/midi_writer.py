"""Minimal, dependency-free Standard MIDI File (SMF format 1) writer.

Supports exactly what the music generator needs: a single track with
tempo, time signature, track name, program change, and note on/off
events. The SMF format is simple and stable enough that pulling in an
external MIDI library for this alone isn't justified (rule: keep
dependencies minimal) - this is ~100 lines of well-understood binary
format code with no runtime dependency risk.
"""

from __future__ import annotations

import struct


def _variable_length(value: int) -> bytes:
    """Encode an integer as a MIDI variable-length quantity."""
    if value < 0:
        raise ValueError("MIDI delta time cannot be negative")
    chunks = [value & 0x7F]
    value >>= 7
    while value:
        chunks.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(chunks))


class _MidiEvent:
    __slots__ = ("tick", "data")

    def __init__(self, tick: int, data: bytes):
        self.tick = tick
        self.data = data


class MidiTrack:
    def __init__(self) -> None:
        self._events: list[_MidiEvent] = []

    def add(self, tick: int, data: bytes) -> None:
        self._events.append(_MidiEvent(tick, data))

    def set_tempo(self, tick: int, bpm: float) -> None:
        microseconds_per_quarter = int(60_000_000 / bpm)
        self.add(tick, b"\xFF\x51\x03" + microseconds_per_quarter.to_bytes(3, "big"))

    def time_signature(self, tick: int, numerator: int = 4, denominator: int = 4) -> None:
        # MIDI stores the denominator as a power-of-two exponent (4 -> 2).
        denominator_exponent = max(0, int(denominator).bit_length() - 1)
        self.add(tick, b"\xFF\x58\x04" + bytes([numerator, denominator_exponent, 24, 8]))

    def track_name(self, tick: int, name: str) -> None:
        encoded = name.encode("utf-8")
        self.add(tick, b"\xFF\x03" + _variable_length(len(encoded)) + encoded)

    def program_change(self, tick: int, channel: int, program: int) -> None:
        self.add(tick, bytes([0xC0 | (channel & 0x0F), program & 0x7F]))

    def note_on(self, tick: int, channel: int, note: int, velocity: int) -> None:
        self.add(tick, bytes([0x90 | (channel & 0x0F), note & 0x7F, velocity & 0x7F]))

    def note_off(self, tick: int, channel: int, note: int, velocity: int = 0) -> None:
        self.add(tick, bytes([0x80 | (channel & 0x0F), note & 0x7F, velocity & 0x7F]))

    def to_bytes(self) -> bytes:
        ordered = sorted(self._events, key=lambda event: event.tick)
        body = bytearray()
        last_tick = 0
        for event in ordered:
            body += _variable_length(event.tick - last_tick)
            body += event.data
            last_tick = event.tick
        body += _variable_length(0) + b"\xFF\x2F\x00"  # End of track
        return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


class MidiFile:
    def __init__(self, ticks_per_beat: int = 480) -> None:
        self.ticks_per_beat = ticks_per_beat
        self.tracks: list[MidiTrack] = []

    def add_track(self) -> MidiTrack:
        track = MidiTrack()
        self.tracks.append(track)
        return track

    def to_bytes(self) -> bytes:
        header = b"MThd" + struct.pack(">IHHH", 6, 1, len(self.tracks), self.ticks_per_beat)
        return header + b"".join(track.to_bytes() for track in self.tracks)
