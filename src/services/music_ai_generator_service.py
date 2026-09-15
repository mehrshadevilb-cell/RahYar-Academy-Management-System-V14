from __future__ import annotations

import base64
import json
import re
import urllib.request
from typing import Any

from src.ai.provider_router import AIProviderRouter
from src.core.config.settings import get_settings, normalize_openai_compatible_base_url
from src.services.music.midi_writer import MidiFile


class MusicAIGeneratorError(RuntimeError):
    pass


class MusicAIGeneratorService:
    """Prompt -> production-oriented MIDI plan, plus optional native AI audio.

    Generation artifacts are returned as bytes and are never persisted by this
    service. The text model is used only to interpret musical intent and create
    structured note data; the MIDI writer creates a real editable SMF file.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.router = AIProviderRouter()

    def _plan(self, prompt: str, output: str, variation: int = 0) -> dict[str, Any]:
        system = """You are RahYar's professional music-production composer.
Turn a natural-language music request into a precise production plan.
The user may be extremely vague. Infer sensible BPM, key, scale, meter,
length, genre, mood, sound palette, arrangement and musical role.
For MIDI, output only valid JSON with this schema:
{"title":str,"bpm":int,"key":str,"scale":str,"meter":"4/4","bars":int,"tracks":[{"name":str,"program":int,"channel":int,"notes":[{"start":number,"duration":number,"note":int,"velocity":int}]}]}
start/duration are beats from 0. Notes must be 0-127, velocity 1-127,
program 0-127, channel 0-15. Maximum 8 tracks, 64 bars, 512 notes/track.
Write musically coherent phrases with repetition and variation, not random notes.
Use correct harmony, voice leading, groove and register. Respect explicit user
constraints over defaults. If output is audio, still infer the same plan and
return JSON only for the internal planning step.
"""
        user = f"Output type: {output}\nVariation: {variation}\nUser request: {prompt}"
        result = self.router.chat([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ], temperature=0.35, timeout_seconds=180, response_format={"type": "json_object"})
        choices = result.get("choices") or []
        content = ((choices[0].get("message") or {}).get("content") if choices else "")
        if isinstance(content, list):
            content = "".join(str(x.get("text", "")) for x in content if isinstance(x, dict))
        content = str(content or "").strip()
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I | re.S).strip()
        try:
            plan = json.loads(content)
        except json.JSONDecodeError as exc:
            raise MusicAIGeneratorError("مدل AI پاسخ موسیقایی قابل‌خواندن تولید نکرد.") from exc
        if not isinstance(plan, dict) or not isinstance(plan.get("tracks"), list):
            raise MusicAIGeneratorError("برنامه موسیقی تولیدشده ناقص است.")
        return plan

    @staticmethod
    def _clamp_note(value: Any) -> int:
        return max(0, min(127, int(round(float(value)))))

    def _midi_from_plan(self, plan: dict[str, Any]) -> bytes:
        bpm = max(40, min(240, int(plan.get("bpm", 120))))
        midi = MidiFile(ticks_per_beat=480)
        tracks = plan.get("tracks", [])[:8]
        for index, raw_track in enumerate(tracks):
            if not isinstance(raw_track, dict):
                continue
            track = midi.add_track()
            name = str(raw_track.get("name") or f"RahYar Track {index + 1}")[:120]
            channel = max(0, min(15, int(raw_track.get("channel", index % 16))))
            program = max(0, min(127, int(raw_track.get("program", 0))))
            track.track_name(0, name)
            if index == 0:
                track.time_signature(0, 4, 4)
                track.set_tempo(0, bpm)
            track.program_change(0, channel, program)
            notes = raw_track.get("notes", [])
            if not isinstance(notes, list):
                continue
            for raw in notes[:512]:
                if not isinstance(raw, dict):
                    continue
                try:
                    start = max(0.0, float(raw.get("start", 0)))
                    duration = max(0.05, min(32.0, float(raw.get("duration", 1))))
                    note = self._clamp_note(raw.get("note", 60))
                    velocity = max(1, min(127, int(raw.get("velocity", 90))))
                except (TypeError, ValueError):
                    continue
                on = int(round(start * midi.ticks_per_beat))
                off = int(round((start + duration) * midi.ticks_per_beat))
                if off <= on:
                    off = on + 1
                track.note_on(on, channel, note, velocity)
                track.note_off(off, channel, note, 0)
        if not midi.tracks:
            raise MusicAIGeneratorError("هیچ نت معتبری برای MIDI تولید نشد.")
        return midi.to_bytes()

    def generate_midi(self, prompt: str, variation: int = 0) -> tuple[bytes, dict[str, Any]]:
        if not prompt.strip():
            raise MusicAIGeneratorError("توضیح موسیقی را بنویس.")
        plan = self._plan(prompt, "midi", variation)
        return self._midi_from_plan(plan), plan

    @staticmethod
    def _decode_audio_response(body: bytes, content_type: str) -> bytes | None:
        if content_type.startswith("audio/") or content_type in {"application/octet-stream", "application/wav"}:
            return body
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            return None
        candidates: list[Any] = []
        if isinstance(data, dict):
            for key in ("audio", "audio_base64", "b64_json", "data"):
                value = data.get(key)
                if isinstance(value, str):
                    candidates.append(value)
                elif isinstance(value, list):
                    candidates.extend(value)
            for key in ("url", "audio_url", "download_url"):
                if isinstance(data.get(key), str):
                    try:
                        with urllib.request.urlopen(data[key], timeout=180) as response:
                            return response.read()
                    except Exception:
                        pass
        for item in candidates:
            if isinstance(item, dict):
                item = item.get("b64_json") or item.get("audio") or item.get("url")
            if not isinstance(item, str):
                continue
            if item.startswith("http"):
                try:
                    with urllib.request.urlopen(item, timeout=180) as response:
                        return response.read()
                except Exception:
                    continue
            try:
                return base64.b64decode(item, validate=True)
            except Exception:
                continue
        return None

    def generate_audio(self, prompt: str, variation: int = 0) -> tuple[bytes, dict[str, Any]]:
        """Call a native music/audio endpoint configured in ENV.

        The endpoint is intentionally configurable because the existing AI pool
        is heterogeneous: chat models can plan music, but only a music-capable
        provider can return an actual audio file.
        """
        settings = self.settings
        api_key = (settings.MUSIC_AUDIO_API_KEY or settings.effective_ai_api_key or "").strip()
        base_url = normalize_openai_compatible_base_url(settings.MUSIC_AUDIO_BASE_URL or settings.effective_ai_base_url)
        model = (settings.MUSIC_AUDIO_MODEL or settings.effective_ai_model).strip()
        path = (settings.MUSIC_AUDIO_PATH or "/audio/generations").strip()
        if not api_key or not base_url or not model:
            raise MusicAIGeneratorError("سرویس Audio Generation در ENV تنظیم نشده است.")
        if not path.startswith("/"):
            path = "/" + path
        payload = {
            "model": model,
            "prompt": prompt.strip(),
            "duration": max(1, min(120, int(settings.MUSIC_AUDIO_MAX_SECONDS))),
            "output_format": settings.MUSIC_AUDIO_FORMAT,
            "quality": "maximum",
            "variation": variation,
        }
        request = urllib.request.Request(
            base_url.rstrip("/") + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "application/json, audio/*"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=max(30, int(settings.MUSIC_AUDIO_TIMEOUT_SECONDS))) as response:
                body = response.read()
                audio = self._decode_audio_response(body, str(response.headers.get_content_type() or ""))
        except Exception as exc:
            raise MusicAIGeneratorError("مدل Audio در دسترس نیست؛ مدل بعدی/تنظیمات Audio را بررسی می‌کنیم.") from exc
        if not audio or len(audio) < 256:
            raise MusicAIGeneratorError("سرویس Audio فایل معتبر برنگرداند.")
        return audio, {"model": model, "bpm": None, "key": None}
