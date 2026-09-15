from __future__ import annotations

import base64
import json
import re
import time
import urllib.request
from typing import Any

from src.ai.provider_router import AIProviderRouter
from src.core.config.settings import get_settings, normalize_openai_compatible_base_url
from src.services.music.midi_writer import MidiFile


class MusicAIGeneratorError(RuntimeError):
    pass


class MusicAIGeneratorService:
    """Prompt -> production-oriented MIDI plan, plus explicitly configured native AI audio."""

    MAX_PLAN_ATTEMPTS = 3

    def __init__(self) -> None:
        self.settings = get_settings()
        self.router = AIProviderRouter()

    @staticmethod
    def _extract_json_object(content: str) -> dict[str, Any] | None:
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I | re.S).strip()
        try:
            value = json.loads(text)
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(text[start : end + 1])
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _validate_plan(plan: dict[str, Any]) -> None:
        tracks = plan.get("tracks")
        if not isinstance(tracks, list) or not tracks:
            raise MusicAIGeneratorError("برنامه موسیقی تولیدشده ترک قابل استفاده ندارد.")
        valid_notes = 0
        for raw_track in tracks[:8]:
            if not isinstance(raw_track, dict):
                continue
            notes = raw_track.get("notes")
            if not isinstance(notes, list):
                continue
            for raw in notes[:512]:
                if not isinstance(raw, dict):
                    continue
                try:
                    start = float(raw.get("start", 0))
                    duration = float(raw.get("duration", 0))
                    note = int(float(raw.get("note", 60)))
                    velocity = int(float(raw.get("velocity", 90)))
                    if start >= 0 and 0.01 <= duration <= 32 and 0 <= note <= 127 and 1 <= velocity <= 127:
                        valid_notes += 1
                except (TypeError, ValueError):
                    continue
        if valid_notes == 0:
            raise MusicAIGeneratorError("مدل AI هیچ نت معتبر و قابل تبدیل به MIDI تولید نکرد.")
        plan["tracks"] = tracks[:8]
        plan["bpm"] = max(40, min(240, int(float(plan.get("bpm", 120)))))
        plan["bars"] = max(1, min(64, int(float(plan.get("bars", 16)))))

    def _plan(self, prompt: str, output: str, variation: int = 0) -> dict[str, Any]:
        system = """You are RahYar's professional music-production composer.
Turn a natural-language music request into a precise production plan. The user
may be extremely vague; infer sensible BPM, key, scale, meter, length, genre,
mood, sound palette, arrangement and musical role. Return ONLY valid JSON:
{"title":str,"bpm":int,"key":str,"scale":str,"meter":"4/4","bars":int,"tracks":[{"name":str,"program":int,"channel":int,"notes":[{"start":number,"duration":number,"note":int,"velocity":int}]}]}
start/duration are beats. Notes 0-127, velocity 1-127, program 0-127,
channel 0-15. Maximum 8 tracks, 64 bars, 512 notes/track. Write coherent
phrases with repetition, development, correct harmony, voice leading and groove;
never random note soup. Respect explicit constraints over defaults. Keep the
result useful in a real DAW. Never return markdown, commentary, or code fences."""
        last_error: Exception | None = None
        for _ in range(self.MAX_PLAN_ATTEMPTS):
            try:
                result = self.router.chat([
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"Output type: {output}\nVariation: {variation}\nUser request: {prompt}"},
                ], temperature=0.35, timeout_seconds=90)
                content = self.router._extract_text(result, str(result.get("_rahyar_provider_type") or "openai_compatible"))
                if not content:
                    choices = result.get("choices") or []
                    content = ((choices[0].get("message") or {}).get("content") if choices else "")
                    if isinstance(content, list):
                        content = "".join(str(x.get("text", "")) for x in content if isinstance(x, dict))
                plan = self._extract_json_object(str(content or ""))
                if plan is None:
                    raise MusicAIGeneratorError("مدل AI پاسخ موسیقایی قابل‌خواندن تولید نکرد.")
                self._validate_plan(plan)
                return plan
            except (MusicAIGeneratorError, ValueError, TypeError) as exc:
                last_error = exc
                provider = str(result.get("_rahyar_provider") or "") if "result" in locals() and isinstance(result, dict) else ""
                model = str(result.get("_rahyar_model") or "") if "result" in locals() and isinstance(result, dict) else ""
                if provider and model:
                    self.router._model_cooldown_until[f"{provider}:{model}"] = time.time() + 20
                continue
        if isinstance(last_error, MusicAIGeneratorError):
            raise last_error
        raise MusicAIGeneratorError("مدل‌های AI نتوانستند یک برنامه موسیقی معتبر بسازند.") from last_error

    @staticmethod
    def _clamp_note(value: Any) -> int:
        return max(0, min(127, int(round(float(value)))))

    def _midi_from_plan(self, plan: dict[str, Any]) -> bytes:
        bpm = max(40, min(240, int(plan.get("bpm", 120))))
        midi = MidiFile(ticks_per_beat=480)
        total_notes = 0
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
                    velocity = max(1, min(127, int(float(raw.get("velocity", 90)))))
                except (TypeError, ValueError):
                    continue
                on = int(round(start * midi.ticks_per_beat))
                off = max(on + 1, int(round((start + duration) * midi.ticks_per_beat)))
                track.note_on(on, channel, note, velocity)
                track.note_off(off, channel, note, 0)
                total_notes += 1
        if not midi.tracks or total_notes == 0:
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
                if value:
                    values.extend(value if isinstance(value, list) else [value])
            for key in ("url", "audio_url", "download_url"):
                url = data.get(key)
                if isinstance(url, str):
                    try:
                        with urllib.request.urlopen(url, timeout=90) as response:
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
                    with urllib.request.urlopen(item, timeout=90) as response:
                        return response.read()
                except Exception:
                    continue
            try:
                return base64.b64decode(item, validate=True)
            except Exception:
                continue
        return None

    def _audio_candidates(self) -> list[tuple[str, str, str]]:
        explicit_key = (self.settings.MUSIC_AUDIO_API_KEY or "").strip()
        explicit_base = (self.settings.MUSIC_AUDIO_BASE_URL or "").strip()
        explicit_model = (self.settings.MUSIC_AUDIO_MODEL or "").strip()
        if explicit_key and explicit_base and explicit_model:
            return [(explicit_key, normalize_openai_compatible_base_url(explicit_base), explicit_model)]
        return []

    def generate_audio(self, prompt: str, variation: int = 0) -> tuple[bytes, dict[str, Any]]:
        settings = self.settings
        path = (settings.MUSIC_AUDIO_PATH or "/audio/generations").strip()
        if not path.startswith("/"):
            path = "/" + path
        candidates = self._audio_candidates()
        if not candidates:
            raise MusicAIGeneratorError("Audio API هنوز وصل نشده؛ خروجی MIDI با AI فعلی آماده است. برای Audio مقدارهای MUSIC_AUDIO_API_KEY / MUSIC_AUDIO_BASE_URL / MUSIC_AUDIO_MODEL را تنظیم کن.")
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
                with urllib.request.urlopen(request, timeout=max(30, min(120, int(settings.MUSIC_AUDIO_TIMEOUT_SECONDS)))) as response:
                    audio = self._decode_audio_response(response.read(), str(response.headers.get_content_type() or ""))
                if audio and len(audio) >= 256:
                    return audio, {"model": model, "provider": base_url}
                errors.append(f"{model}:empty")
            except Exception as exc:
                errors.append(f"{model}:{type(exc).__name__}")
        raise MusicAIGeneratorError("هیچ مدل Audio موجود نتوانست فایل معتبر تولید کند.")
