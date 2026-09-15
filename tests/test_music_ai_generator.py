from src.services.music_ai_generator_service import MusicAIGeneratorService, MusicAIGeneratorError


def test_midi_plan_is_real_smf():
    service = MusicAIGeneratorService()
    midi = service._midi_from_plan(
        {
            "bpm": 140,
            "key": "F#",
            "scale": "minor",
            "bars": 2,
            "tracks": [{"name": "Lead", "program": 80, "channel": 0, "notes": [{"start": 0, "duration": 1, "note": 66, "velocity": 100}, {"start": 1, "duration": 1, "note": 69, "velocity": 95}] }],
        }
    )
    assert midi[:4] == b"MThd"
    assert b"MTrk" in midi


def test_auto_output_defaults_to_connected_ai_midi():
    from src.bot.handlers.music_generator import _auto_output

    assert _auto_output("یه ملودی MIDI در F# minor") == "midi"
    assert _auto_output("یه بیت دارک trap") == "midi"
    assert _auto_output("یه فایل صوتی wav بساز") == "audio"


def test_native_google_response_is_read():
    data = {"candidates": [{"content": {"parts": [{"text": '{"tracks":[]}' }]}}]}
    assert MusicAIGeneratorService._response_text(data) == '{"tracks":[]}'


def test_native_anthropic_response_is_read():
    data = {"content": [{"type": "text", "text": '{"tracks":[]}' }]}
    assert MusicAIGeneratorService._response_text(data) == '{"tracks":[]}'


def test_json_object_can_be_extracted_from_code_fence():
    value = MusicAIGeneratorService._extract_json_object('```json\n{"title":"x","tracks":[]}\n```')
    assert value == {"title": "x", "tracks": []}


def test_plan_validation_rejects_empty_notes():
    try:
        MusicAIGeneratorService._validate_plan({"tracks": [{"notes": []}]})
    except MusicAIGeneratorError:
        return
    raise AssertionError("empty musical plan must be rejected")
