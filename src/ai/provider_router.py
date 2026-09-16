from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse

from src.core.config.settings import get_settings, normalize_openai_compatible_base_url


@dataclass(frozen=True)
class AIProvider:
    name: str
    api_key: str
    base_url: str
    models: tuple[str, ...]
    priority: int = 100
    enabled: bool = True
    provider_type: str = "openai_compatible"

    @property
    def model(self) -> str:
        return self.models[0] if self.models else ""


class AIProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, retry_after: int = 0, provider: str = "") -> None:
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = max(0, retry_after)
        self.provider = provider


class AIProviderRouter:
    """AI provider pool with DB discovery, global free-first routing and model failover."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._cooldown_until: dict[str, float] = {}
        self._model_cooldown_until: dict[str, float] = {}

    @staticmethod
    def _normalize_base_url(value: str) -> str:
        return normalize_openai_compatible_base_url((value or "").strip())

    @staticmethod
    def _infer_provider_type(name: str, base_url: str) -> str:
        host = (urlparse(base_url).hostname or "").lower()
        lowered = f"{name} {host}".lower()
        if "generativelanguage.googleapis.com" in lowered or "google" in lowered or "gemini" in lowered:
            return "google"
        if "anthropic" in lowered or "claude" in lowered:
            return "anthropic"
        return "openai_compatible"

    @classmethod
    def _provider_from_env(cls, name: str, key_var: str, url_var: str, model_var: str, priority: int) -> AIProvider | None:
        key = (os.getenv(key_var) or "").strip()
        base_url = cls._normalize_base_url(os.getenv(url_var) or "")
        model = (os.getenv(model_var) or "").strip()
        if not (key and base_url and model):
            return None
        return AIProvider(name=name, api_key=key, base_url=base_url, models=(model,), priority=priority, provider_type=cls._infer_provider_type(name, base_url))

    @staticmethod
    def _is_free_model(model: Any) -> bool:
        if isinstance(model, str):
            model_id = model.lower()
            return model_id.endswith(":free") or "-free" in model_id
        model_id = str(getattr(model, "model_id", "") or "").lower()
        if model_id.endswith(":free") or "-free" in model_id:
            return True
        raw = getattr(model, "raw_metadata", None) or {}
        pricing = raw.get("pricing") if isinstance(raw, dict) else None
        if isinstance(pricing, dict):
            prompt = pricing.get("prompt", pricing.get("input"))
            completion = pricing.get("completion", pricing.get("output"))
            try:
                if prompt is not None and completion is not None:
                    return float(prompt) == 0.0 and float(completion) == 0.0
            except (TypeError, ValueError):
                pass
        try:
            return getattr(model, "pricing_input", None) is not None and getattr(model, "pricing_output", None) is not None and float(model.pricing_input) == 0.0 and float(model.pricing_output) == 0.0
        except (TypeError, ValueError):
            return False

    def _from_database(self) -> list[AIProvider]:
        try:
            from src.database.models.ai_provider import AIProvider as DBProvider
            from src.database.session import SessionLocal
            from src.services.ai.credential_crypto import decrypt_api_key
            db = SessionLocal()
            try:
                rows = db.query(DBProvider).filter(DBProvider.is_active.is_(True)).all()
                result: list[AIProvider] = []
                for index, provider in enumerate(rows):
                    active_models = [m for m in provider.models if m.is_active]
                    if not active_models:
                        continue
                    active_models.sort(key=lambda m: (not self._is_free_model(m), not m.is_default, -(m.context_window or 0), m.model_id))
                    try:
                        api_key = decrypt_api_key(provider.api_key_encrypted)
                    except Exception:
                        continue
                    result.append(AIProvider(name=provider.name, api_key=api_key, base_url=self._normalize_base_url(provider.base_url), models=tuple(m.model_id for m in active_models), priority=index, provider_type=provider.provider_type or self._infer_provider_type(provider.name, provider.base_url)))
                return result
            finally:
                db.close()
        except Exception:
            return []

    def _env_providers(self) -> list[AIProvider]:
        providers: list[AIProvider] = []
        primary = self._provider_from_env("primary", "AI_API_KEY", "AI_BASE_URL", "AI_MODEL", 10)
        if primary:
            providers.append(primary)
        secondary = self._provider_from_env("secondary", "AI2_API_KEY", "AI2_BASE_URL", "AI2_MODEL", 20)
        if secondary:
            providers.append(secondary)
        if not providers and self.settings.effective_ai_api_key:
            base_url = self._normalize_base_url(self.settings.effective_ai_base_url)
            providers.append(AIProvider(name="primary", api_key=self.settings.effective_ai_api_key, base_url=base_url, models=(self.settings.effective_ai_model,), priority=100, provider_type=self._infer_provider_type("primary", base_url)))
        return providers

    @staticmethod
    def _merge_providers(providers: list[AIProvider]) -> list[AIProvider]:
        merged: dict[tuple[str, str, str], AIProvider] = {}
        for provider in providers:
            for model in provider.models:
                key = (provider.name.lower(), provider.base_url.rstrip("/"), model)
                current = merged.get(key)
                if current is None or provider.priority < current.priority:
                    merged[key] = AIProvider(name=provider.name, api_key=provider.api_key, base_url=provider.base_url, models=(model,), priority=provider.priority, enabled=provider.enabled, provider_type=provider.provider_type)
        return sorted(merged.values(), key=lambda p: (p.priority, p.name, p.model))

    def _parse(self) -> list[AIProvider]:
        db_providers = self._from_database()
        raw = (self.settings.AI_PROVIDERS_JSON or "").strip()
        configured: list[AIProvider] = []
        if raw:
            try:
                rows = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise AIProviderError("AI_PROVIDERS_JSON is invalid JSON") from exc
            if not isinstance(rows, list):
                raise AIProviderError("AI_PROVIDERS_JSON must be a JSON array")
            for index, row in enumerate(rows):
                if not isinstance(row, dict) or row.get("enabled", True) is False:
                    continue
                key = str(row.get("api_key", "") or "")
                key_env = str(row.get("api_key_env", "") or "")
                if key_env:
                    key = os.getenv(key_env, "")
                base_url = self._normalize_base_url(str(row.get("base_url", "") or ""))
                name = str(row.get("name", f"provider-{index + 1}") or f"provider-{index + 1}")
                models = [str(m).strip() for m in row.get("models", []) if str(m).strip()] if isinstance(row.get("models"), list) else []
                if not models:
                    single = str(row.get("model", "") or "").strip()
                    if single:
                        models = [single]
                if key and base_url and models:
                    configured.append(AIProvider(name=name, api_key=key, base_url=base_url, models=tuple(models), priority=int(row.get("priority", 100)), provider_type=str(row.get("provider_type", "") or self._infer_provider_type(name, base_url))))
        candidates = configured + db_providers + self._env_providers()
        if not candidates:
            raise AIProviderError("No AI provider is configured")
        return self._merge_providers(candidates)

    def providers(self) -> list[AIProvider]:
        return self._parse()

    def reset_cooldowns(self) -> None:
        self._cooldown_until.clear()
        self._model_cooldown_until.clear()

    def cooldown_snapshot(self) -> dict[str, int]:
        now = time.time()
        return {key: max(0, int(round(until - now))) for key, until in self._model_cooldown_until.items() if until > now}

    def _headers(self, provider: AIProvider) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "RahYar-AIProviderRouter/1.5"}
        host = (urlparse(provider.base_url).hostname or "").lower()
        if host.endswith("agentrouter.org"):
            headers.update({"Originator": "codex_cli_rs", "Version": "0.101.0"})
        return headers

    @staticmethod
    def _anthropic_headers(provider: AIProvider) -> dict[str, str]:
        return {"x-api-key": provider.api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "RahYar-AIProviderRouter/1.5"}

    @staticmethod
    def _retry_after(headers: Any, body: str) -> int:
        value = headers.get("Retry-After") or headers.get("retry-after")
        try:
            if value is not None:
                return max(1, int(float(value)))
        except (TypeError, ValueError):
            pass
        try:
            data = json.loads(body)
            value = data.get("error", {}).get("metadata", {}).get("retry_after_seconds", 0)
            return max(1, int(float(value))) if value else 0
        except (TypeError, ValueError, json.JSONDecodeError):
            return 0

    @staticmethod
    def _is_rate_limited(code: int, body: str) -> bool:
        if code == 429:
            return True
        lowered = body.lower()
        return code in {402, 403} and any(x in lowered for x in ("rate", "capacity", "quota", "limit"))

    def _ordered_candidates(self, providers: list[AIProvider]) -> list[tuple[AIProvider, str]]:
        candidates = [(provider, model) for provider in providers for model in provider.models]
        candidates.sort(key=lambda item: (not self._is_free_model(item[1]), item[0].priority, item[1]))
        return candidates

    @staticmethod
    def _extract_text(data: Any, provider_type: str) -> str:
        if provider_type == "google":
            parts: list[str] = []
            for candidate in data.get("candidates", []) if isinstance(data, dict) else []:
                content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
                for part in content.get("parts", []) if isinstance(content, dict) else []:
                    if isinstance(part, dict) and part.get("text"):
                        parts.append(str(part["text"]))
            return " ".join(parts).strip()
        if provider_type == "anthropic":
            return " ".join(str(part.get("text", "")) for part in data.get("content", []) if isinstance(part, dict)).strip() if isinstance(data, dict) else ""
        choices = data.get("choices", []) if isinstance(data, dict) else []
        if not choices or not isinstance(choices[0], dict):
            return ""
        message = choices[0].get("message", {})
        content = message.get("content", "") if isinstance(message, dict) else ""
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return " ".join(str(part.get("text", "")) for part in content if isinstance(part, dict)).strip()
        return str(content).strip() if content else ""

    def _request(self, provider: AIProvider, model: str, messages: list[dict[str, Any]], kwargs: dict[str, Any], timeout: int) -> dict[str, Any]:
        if provider.provider_type == "google":
            system_parts: list[str] = []
            contents: list[dict[str, Any]] = []
            for message in messages:
                role = str(message.get("role", "user"))
                content = str(message.get("content", ""))
                if role == "system":
                    system_parts.append(content)
                else:
                    contents.append({"role": "model" if role == "assistant" else "user", "parts": [{"text": content}]})
            if not contents:
                contents = [{"role": "user", "parts": [{"text": ""}]}]
            generation: dict[str, Any] = {}
            if "temperature" in kwargs:
                generation["temperature"] = kwargs["temperature"]
            if "max_tokens" in kwargs:
                generation["maxOutputTokens"] = kwargs["max_tokens"]
            payload: dict[str, Any] = {"contents": contents}
            if system_parts:
                payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
            if generation:
                payload["generationConfig"] = generation
            url = provider.base_url.rstrip("/") + f"/models/{quote(model, safe='')}:generateContent?key={quote(provider.api_key, safe='')}"
            headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "RahYar-AIProviderRouter/1.5"}
        elif provider.provider_type == "anthropic":
            system_parts = [str(m.get("content", "")) for m in messages if m.get("role") == "system"]
            anthropic_messages = [{"role": "assistant" if m.get("role") == "assistant" else "user", "content": str(m.get("content", ""))} for m in messages if m.get("role") != "system"]
            payload = {"model": model, "max_tokens": int(kwargs.pop("max_tokens", 4096)), "messages": anthropic_messages or [{"role": "user", "content": ""}]}
            if system_parts:
                payload["system"] = "\n\n".join(system_parts)
            if "temperature" in kwargs:
                payload["temperature"] = kwargs["temperature"]
            url = provider.base_url.rstrip("/") + "/messages"
            headers = self._anthropic_headers(provider)
        else:
            payload = {"model": model, "messages": messages, **kwargs}
            url = provider.base_url.rstrip("/") + "/chat/completions"
            headers = self._headers(provider)
        request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)
        if not isinstance(data, dict):
            raise AIProviderError(f"Invalid AI provider response: {provider.name}/{model}", provider=provider.name)
        if not self._extract_text(data, provider.provider_type):
            raise AIProviderError(f"AI provider returned an empty response: {provider.name}/{model}", retryable=True, retry_after=30, provider=provider.name)
        return data

    def _test_request(self, provider: AIProvider, model: str, timeout: int) -> tuple[int, int, str]:
        if provider.provider_type == "google":
            url = provider.base_url.rstrip("/") + f"/models/{quote(model, safe='')}:generateContent?key={quote(provider.api_key, safe='')}"
            payload = {"contents": [{"role": "user", "parts": [{"text": "Reply with exactly: OK"}]}], "generationConfig": {"temperature": 0, "maxOutputTokens": 8}}
            headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "RahYar-AIProviderRouter/1.5"}
        elif provider.provider_type == "anthropic":
            url = provider.base_url.rstrip("/") + "/messages"
            payload = {"model": model, "max_tokens": 8, "temperature": 0, "messages": [{"role": "user", "content": "Reply with exactly: OK"}]}
            headers = self._anthropic_headers(provider)
        else:
            url = provider.base_url.rstrip("/") + "/chat/completions"
            payload = {"model": model, "messages": [{"role": "user", "content": "Reply with exactly: OK"}], "max_tokens": 8, "temperature": 0}
            headers = self._headers(provider)
        request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        started = time.perf_counter()
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            status_code = int(getattr(response, "status", 200) or 200)
        latency = round((time.perf_counter() - started) * 1000)
        text = self._extract_text(data, provider.provider_type)
        if not text:
            raise ValueError("empty model response")
        return status_code, latency, text

    def test_models(self, *, timeout_seconds: int = 15) -> list[dict[str, Any]]:
        providers = self.providers()
        results: list[dict[str, Any]] = []
        timeout = max(5, min(int(timeout_seconds), 60))
        for provider, model in self._ordered_candidates(providers):
            started = time.perf_counter()
            model_key = f"{provider.name}:{model}"
            row = {"provider": provider.name, "model": model, "free": self._is_free_model(model), "ok": False, "latency_ms": 0, "status": "unknown", "response": ""}
            try:
                http_status, latency, response_text = self._test_request(provider, model, timeout)
                row.update(ok=True, status="ok", http_status=http_status, latency_ms=latency, response=response_text[:300])
                self._model_cooldown_until.pop(model_key, None)
                self._cooldown_until.pop(provider.name, None)
            except urllib.error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8", errors="replace")[:300]
                except Exception:
                    pass
                row.update(status=f"http_{exc.code}", http_status=exc.code, retry_after=self._retry_after(exc.headers, body))
                if exc.code == 404:
                    self._model_cooldown_until[model_key] = time.time() + 3600
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                row.update(status=f"unavailable:{type(exc).__name__}")
            except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
                row.update(status=f"invalid_response:{type(exc).__name__}")
            finally:
                row["latency_ms"] = row["latency_ms"] or round((time.perf_counter() - started) * 1000)
            results.append(row)
        return results

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        providers = self.providers()
        timeout_seconds = kwargs.pop("timeout_seconds", None)
        if timeout_seconds is None:
            timeout_seconds = self.settings.AI_AGENT_TIMEOUT_SECONDS
        try:
            timeout_seconds = max(5, min(int(timeout_seconds), 120))
        except (TypeError, ValueError):
            timeout_seconds = min(max(self.settings.AI_AGENT_TIMEOUT_SECONDS, 5), 120)
        last: AIProviderError | None = None
        candidates = self._ordered_candidates(providers)
        try:
            transient_retries = max(0, min(int(self.settings.AI_AGENT_MAX_RETRIES), 5))
        except (TypeError, ValueError):
            transient_retries = 2
        transient_attempts: dict[str, int] = {}
        now = time.time()
        skipped_until: list[float] = []
        attempted = 0
        for provider, model in candidates:
            model_key = f"{provider.name}:{model}"
            provider_until = self._cooldown_until.get(provider.name, 0)
            model_until = self._model_cooldown_until.get(model_key, 0)
            blocked_until = max(provider_until, model_until)
            if blocked_until > now:
                skipped_until.append(blocked_until)
                continue
            attempted += 1
            request_kwargs = dict(kwargs)
            try:
                data = self._request(provider, model, messages, request_kwargs, timeout_seconds)
                self._model_cooldown_until.pop(model_key, None)
                data["_rahyar_provider"] = provider.name
                data["_rahyar_model"] = model
                data["_rahyar_is_free"] = self._is_free_model(model)
                return data
            except urllib.error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8", errors="replace")[:1000]
                except Exception:
                    pass
                retry_after = self._retry_after(exc.headers, body)
                lowered = body.lower()
                if exc.code == 404 or (exc.code in {400, 404} and any(x in lowered for x in ("not found", "model", "does not exist", "unknown model", "invalid model"))):
                    self._model_cooldown_until[model_key] = time.time() + 3600
                    last = AIProviderError(f"model not found: {provider.name}/{model} (HTTP {exc.code})", retryable=True, retry_after=3600, provider=provider.name)
                    continue
                if self._is_rate_limited(exc.code, body):
                    cooldown = min(retry_after or 300, 86400)
                    self._model_cooldown_until[model_key] = time.time() + cooldown
                    last = AIProviderError(f"model rate limited: {provider.name}/{model}", retryable=True, retry_after=cooldown, provider=provider.name)
                    continue
                if exc.code in {401, 403}:
                    self._model_cooldown_until[model_key] = time.time() + 120
                    last = AIProviderError(f"provider authentication failed: {provider.name}/{model}", retryable=True, retry_after=120, provider=provider.name)
                    continue
                last = AIProviderError(f"provider request failed: {provider.name}/{model} (HTTP {exc.code})", retryable=exc.code >= 500 or exc.code in {408, 409, 425, 429}, retry_after=60 if exc.code >= 500 else (retry_after or 0), provider=provider.name)
                if exc.code >= 500:
                    used = transient_attempts.get(model_key, 0)
                    if used < transient_retries:
                        transient_attempts[model_key] = used + 1
                        candidates.append((provider, model))
                    else:
                        self._model_cooldown_until[model_key] = time.time() + 60
                continue
            except (urllib.error.URLError, TimeoutError, OSError):
                last = AIProviderError(f"provider unavailable: {provider.name}/{model}", retryable=True, retry_after=30, provider=provider.name)
                self._model_cooldown_until[model_key] = time.time() + 30
                continue
            except AIProviderError as exc:
                last = exc
                self._model_cooldown_until[model_key] = time.time() + (exc.retry_after or 30)
                continue
        if last:
            raise last
        if skipped_until and attempted == 0:
            retry_after = max(1, int(round(min(skipped_until) - time.time())))
            raise AIProviderError(f"All configured AI models are cooling down; retry in {retry_after}s", retryable=True, retry_after=retry_after)
        raise AIProviderError("All configured AI models are temporarily unavailable", retryable=True, retry_after=30)
