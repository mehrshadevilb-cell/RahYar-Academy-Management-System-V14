from src.services.music_ai_generator_service import MusicAIGeneratorService


def test_midi_plan_is_real_smf():
    service = MusicAIGeneratorService()
    midi = service._midi_from_plan(
        {
            "bpm": 140,
            "key": "F#",
            "scale": "minor",
            "bars": 2,
            "tracks": [
                {
                    "name": "Lead",
                    "program": 80,
                    "channel": 0,
                    "notes": [
                        {"start": 0, "duration": 1, "note": 66, "velocity": 100},
                        {"start": 1, "duration": 1, "note": 69, "velocity": 95},
                    ],
                }
            ],
        }
    )
    assert midi[:4] == b"MThd"
    assert b"MTrk" in midi


def test_auto_output_understands_midi_request():
    # Keep this test independent of any external provider.
    from src.bot.handlers.music_generator import _auto_output

    assert _auto_output("یه ملودی MIDI در F# minor") == "midi"
    assert _auto_output("یه بیت دارک trap") == "audio"
