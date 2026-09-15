import pytest

from src.services.music_generator_service import MusicGeneratorError, MusicGeneratorService


def test_generate_am_progression_piano_close():
    service = MusicGeneratorService()
    midi_bytes = service.generate(
        key_text="Am",
        progression_text="i - iv - v - iv",
        instrument="piano",
        voicing="close",
        tempo=100,
    )
    assert midi_bytes[:4] == b"MThd"
    assert len(midi_bytes) > 20


def test_generate_guitar_riff():
    service = MusicGeneratorService()
    midi_bytes = service.generate(
        key_text="Am",
        progression_text="i - iv - v - iv",
        instrument="nylon_guitar",
        tempo=140,
    )
    assert midi_bytes[:4] == b"MThd"


def test_invalid_key_raises_music_generator_error():
    service = MusicGeneratorService()
    with pytest.raises(MusicGeneratorError):
        service.generate(key_text="Zm", progression_text="i - iv", instrument="piano")


def test_invalid_instrument_raises():
    service = MusicGeneratorService()
    with pytest.raises(MusicGeneratorError, match="ساز پشتیبانی نمی‌شود"):
        service.generate(key_text="Am", progression_text="i - iv", instrument="drums")


def test_tempo_out_of_range_raises():
    service = MusicGeneratorService()
    with pytest.raises(MusicGeneratorError, match="تمپو"):
        service.generate(key_text="Am", progression_text="i - iv", instrument="piano", tempo=999)


def test_too_many_chords_raises():
    service = MusicGeneratorService()
    progression = " - ".join(["i"] * 20)
    with pytest.raises(MusicGeneratorError, match="حداکثر"):
        service.generate(key_text="Am", progression_text=progression, instrument="piano")


def test_am_natural_minor_degrees_are_correct():
    # Regression check for the exact example from the request: i-iv-v-iv
    # in Am should be A minor, D minor, E minor, D minor (natural minor).
    from src.services.music.music_theory import parse_key, parse_progression

    key_pc, mode = parse_key("Am")
    chords = parse_progression("i - iv - v - iv", key_pc, mode)
    assert chords == [(9, "min"), (2, "min"), (4, "min"), (2, "min")]
