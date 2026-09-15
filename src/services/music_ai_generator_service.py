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
    """Prompt -> production-oriented MIDI plan, plus native AI audio.

    Artifacts are returned as bytes and are never persisted by this service.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.router = AIProviderRouter()

    def _plan(self, prompt: str, output: str, variation: int = 0) -> dict[str, Any]:
        system = """You are RahYar's professional music-production composer.
Turn a natural-language music request into a precise production plan. The user
may be extremely vague; infer sensible BPM, key, scale, meter, length, genre,
mood, sound palette, arrangement and musical role. For MIDI return ONLY JSON:
{"title":str,"bpm":int,"key":str,"scale":str,"meter":"4/4","bars":int,"tracks":[{"name":str,"program":int,"channel":int,"notes":[{"start":number,"duration":number,"note":int,"velocity":int}]}]}
start/duration are beats. Notes 0-127, velocity 1-127, program 0-127,
channel 0-15. Maximum 8 tracks, 64 bars, 512 notes/track. Write coherent
phrases with repetition, development, correct harmony, voice leading and groove;
never random note soup. Respect explicit constraints over defaults. Keep the
result useful in a real DAW."""
        result = self.router.chat([
            {"role": "system", "content": system},
            {"role": "user", "content": f"Output type: {output}\nVariation: {variation}\nUser request: {prompt}"},
        ], temperature=0.35, timeout_seconds=180, response_format={"type": "json_object"})
        choices = result.get("choices") or []
        content = ((choices[0].get("message") or {}).get("content") if choices else "")
        if isinstance(content, list):
            content = "".join(str(x.get("text", "")) for x in content if isinstance(x, dict))
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(content or "").strip(), flags=re.I | re.S).strip()
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
        for index, raw_track in enumerate(plan.get("tracks", [])[:8]):
            if not isinstance(raw_track, dict):
                continue
            track = midi.add_track()
            channel = max(0, min(15, int(raw_track.get("channel", index % 16))))
            program = max(0, min(127, int(raw_track.get("program", 0))))
            track.track_name(0, str(raw_track.get("name") or f"RahYar Track {index + 1}")[:120])
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
                off = max(on + 1, int(round((start + duration) * midi.ticks_per_beat)))
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
        values: list[Any] = []
        if isinstance(data, dict):
            for key in ("audio", "audio_base64", "b64_json", "data"):
                value = data.get(key)
                values.extend(value if isinstance(value, list) else [value]) if value else None
            for key in ("url", "audio_url", "download_url"):
                url = data.get(key)
                if isinstance(url, str):
                    try:
                        with urllib.request.urlopen(url, timeout=180) as response:
                            return response.read()
                    except Exception:
                        pass
        for item in values:
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

    def _audio_candidates(self) -> list[tuple[str, str, str]]:
        settings = self.settings
        path = (settings.MUSIC_AUDIO_PATH or "/audio/generations").strip()
        if not path.startswith("/"):
            path = "/" + path
        explicit_key = (settings.MUSIC_AUDIO_API_KEY or "").strip()
        explicit_base = (settings.MUSIC_AUDIO_BASE_URL or "").strip()
        explicit_model = (settings.MUSIC_AUDIO_MODEL or "").strip()
        if explicit_key and explicit_base and explicit_model:
            return [(explicit_key, normalize_openai_compatible_base_url(explicit_base), explicit_model)]
        try:
            providers = self.router.providers()
        except Exception:
            providers = []
        candidates = [(p.api_key, p.base_url, model) for p in providers for model in p.models]
        # Prefer models whose identifiers strongly suggest native audio/music,
        # then preserve the router's configured priority for everything else.
        candidates.sort(key=lambda item: (not bool(re.search(r"music|audio|lyria|stable-audio|suno|udio", item[2], re.I))))
        return candidates

    def generate_audio(self, prompt: str, variation: int = 0) -> tuple[bytes, dict[str, Any]]:
        settings = self.settings
        path = (settings.MUSIC_AUDIO_PATH or "/audio/generations").strip()
        if not path.startswith("/"):
            path = "/" + path
        candidates = self._audio_candidates()
        if not candidates:
            raise MusicAIGeneratorError("هیچ Audio provider قابل استفاده‌ای در ENV پیدا نشد.")
        errors: list[str] = []
        for api_key, base_url, model in candidates:
            payload = {
                "model": model,
                "prompt": prompt.strip(),
                "duration": max(1, min(120, int(settings.MUSIC_AUDIO_MAX_SECONDS))),
                "output_format": settings.MUSIC_AUDIO_FORMAT,
                "quality": "maximum",
                "variation": variation,
            }
            request = urllib.request.Request(
                normalize_openai_compatible_base_url(base_url).rstrip("/") + path,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "application/json, audio/*"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=max(30, int(settings.MUSIC_AUDIO_TIMEOUT_SECONDS))) as response:
                    audio = self._decode_audio_response(response.read(), str(response.headers.get_content_type() or ""))
                if audio and len(audio) >= 256:
                    return audio, {"model": model, "provider": base_url}
                errors.append(f"{model}:empty")
            except Exception as exc:
                errors.append(f"{model}:{type(exc).__name__}")
        raise MusicAIGeneratorError("هیچ مدل Audio موجود نتوانست فایل معتبر تولید کند.")
