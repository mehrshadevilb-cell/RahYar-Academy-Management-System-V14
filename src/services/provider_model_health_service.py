from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import quote

from src.ai.provider_router import AIProvider, AIProviderRouter
from src.core.config.provider_url_safety import validate_provider_base_url


class ProviderModelHealthService:
    """Discover and live-test the provider model pool used by the Agent."""

    MAX_CONCURRENT_TESTS = 8

    def __init__(self, router: AIProviderRouter | None = None) -> None:
        self.router = router or AIProviderRouter()

    @staticmethod
    def _headers(provider: AIProvider) -> dict[str, str]:
        host = provider.base_url.split("/", 3)[2].lower() if "://" in provider.base_url else ""
        if provider.provider_type == "anthropic":
            return {"x-api-key": provider.api_key, "anthropic-version": "2023-06-01", "Accept": "application/json", "User-Agent": "RahYar-ProviderModelHealth/1.1"}
        authorization = provider.api_key if host.endswith("bytez.com") else f"Bearer {provider.api_key}"
        headers = {"Authorization": authorization, "Accept": "application/json", "User-Agent": "RahYar-ProviderModelHealth/1.1"}
        if host.endswith("agentrouter.org"):
            headers.update({"Originator": "codex_cli_rs", "Version": "0.101.0"})
        return headers

    @staticmethod
    def _safe_detail(text: str, api_key: str) -> str:
        detail = (text or "")[:500]
        if api_key:
            detail = detail.replace(api_key, "[REDACTED]")
        return detail

    def discover(self, provider: AIProvider, *, timeout_seconds: int = 20) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        base_url = validate_provider_base_url(provider.base_url)
        started = time.perf_counter()
        if not base_url:
            self._sync_router_health(provider, "__discovery__", False, 300)
            return [], {"status": "invalid_base_url", "latency_ms": 0, "detail": "Provider BASE_URL is invalid or missing"}
        url = base_url + "/models"
        if provider.provider_type == "google":
            url += "?key=" + quote(provider.api_key, safe="")
        try:
            request = urllib.request.Request(url, headers=self._headers(provider), method="GET")
            with urllib.request.urlopen(request, timeout=max(5, min(int(timeout_seconds), 60))) as response:
                payload = json.loads(response.read().decode("utf-8"))
                http_status = int(getattr(response, "status", 200) or 200)
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                raw_body = exc.read()
                if raw_body:
                    body = raw_body.decode("utf-8", errors="replace")
            except Exception:
                pass
            retry_after = self.router._retry_after(exc.headers, body)
            cooldown = retry_after or (300 if exc.code in {401, 403, 429} else 60)
            self._sync_router_health(provider, "__discovery__", False, cooldown)
            return [], {"status": f"http_{exc.code}", "http_status": exc.code, "latency_ms": round((time.perf_counter() - started) * 1000), "retry_after": retry_after, "detail": self._safe_detail(body, provider.api_key)}
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            self._sync_router_health(provider, "__discovery__", False, 60)
            return [], {"status": f"discovery_failed:{type(exc).__name__}", "latency_ms": round((time.perf_counter() - started) * 1000), "detail": self._safe_detail(str(exc), provider.api_key)}
        except Exception as exc:
            self._sync_router_health(provider, "__discovery__", False, 60)
            return [], {"status": f"discovery_failed:{type(exc).__name__}", "latency_ms": round((time.perf_counter() - started) * 1000), "detail": self._safe_detail(str(exc), provider.api_key)}

        raw_items: list[dict[str, Any]] = []
        if provider.provider_type == "google":
            for item in payload.get("models", []) if isinstance(payload, dict) else []:
                model_id = str(item.get("name", "")).removeprefix("models/").strip()
                methods = item.get("supportedGenerationMethods") or []
                if model_id and (not methods or "generateContent" in methods):
                    raw_items.append({"id": model_id, "display_name": item.get("displayName") or model_id, "pricing_input": item.get("pricing_input"), "pricing_output": item.get("pricing_output"), "raw_metadata": item})
        else:
            data = payload.get("data", []) if isinstance(payload, dict) else []
            raw_items = [item for item in data if isinstance(item, dict) and item.get("id")]
        models = [{"model_id": str(item.get("id") or item.get("name")), "display_name": str(item.get("display_name") or item.get("name") or item.get("id")), "pricing_input": item.get("pricing_input"), "pricing_output": item.get("pricing_output"), "raw_metadata": item.get("raw_metadata", item)} for item in raw_items]
        self._sync_router_health(provider, "__discovery__", True)
        return models, {"status": "ok", "http_status": http_status, "latency_ms": round((time.perf_counter() - started) * 1000), "count": len(models)}

    @staticmethod
    def pricing_status(model: dict[str, Any]) -> str:
        model_id = str(model.get("model_id") or "").lower()
        if model_id.endswith(":free") or "-free" in model_id:
            return "known_free"
        values = []
        for key in ("pricing_input", "pricing_output"):
            value = model.get(key)
            if value is not None:
                try: values.append(float(value))
                except (TypeError, ValueError): return "unknown"
        if values: return "known_free" if all(value == 0 for value in values) else "known_paid"
        raw = model.get("raw_metadata") or {}
        pricing = raw.get("pricing") if isinstance(raw, dict) else None
        if isinstance(pricing, dict):
            candidates = (pricing.get("prompt", pricing.get("input")), pricing.get("completion", pricing.get("output")))
            if all(value is not None for value in candidates):
                try: return "known_free" if all(float(value) == 0 for value in candidates) else "known_paid"
                except (TypeError, ValueError): return "unknown"
        return "unknown"

    @classmethod
    def _free(cls, model: dict[str, Any]) -> bool:
        return cls.pricing_status(model) == "known_free"

    def _sync_router_health(self, provider: AIProvider, model: str, ok: bool, retry_after: int = 0) -> None:
        key = f"{provider.name}:{model}"
        if ok:
            self.router._model_cooldown_until.pop(key, None)
            if model == "__discovery__": self.router._cooldown_until.pop(provider.name, None)
            return
        if retry_after: self.router._model_cooldown_until[key] = time.time() + min(max(int(retry_after), 1), 86400)

    def _live_test_one(self, provider: AIProvider, model: str, timeout_seconds: int, item: dict[str, Any]) -> dict[str, Any]:
        live_provider = AIProvider(name=provider.name, api_key=provider.api_key, base_url=provider.base_url, models=(model,), priority=provider.priority, enabled=provider.enabled, provider_type=provider.provider_type)
        started = time.perf_counter(); pricing = self.pricing_status(item)
        row = {"provider": provider.name, "model": model, "display_name": item.get("display_name") or model, "free": pricing == "known_free", "pricing_status": pricing, "discovered": True, "ok": False, "latency_ms": 0, "status": "unknown", "response": ""}
        try:
            status, latency, response = self.router._test_request(live_provider, model, timeout_seconds)
            row.update(ok=True, status="ok", http_status=status, latency_ms=latency, response=response[:300]); self._sync_router_health(provider, model, True)
        except urllib.error.HTTPError as exc:
            body = ""
            try: body = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception: pass
            retry_after = self.router._retry_after(exc.headers, body); row.update(status=f"http_{exc.code}", http_status=exc.code, retry_after=retry_after, detail=self._safe_detail(body, provider.api_key))
            if exc.code in {401, 403, 429} or exc.code >= 500: self._sync_router_health(provider, model, False, retry_after or (300 if exc.code in {401,403,429} else 60))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            row.update(status=f"unavailable:{type(exc).__name__}"); self._sync_router_health(provider, model, False, 30)
        except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
            row.update(status=f"invalid_response:{type(exc).__name__}"); self._sync_router_health(provider, model, False, 60)
        except Exception as exc:
            row.update(status=f"test_failed:{type(exc).__name__}"); self._sync_router_health(provider, model, False, 60)
        finally: row["latency_ms"] = row["latency_ms"] or round((time.perf_counter() - started) * 1000)
        return row

    def test_all(self, *, timeout_seconds: int = 15, discover_catalog: bool = True, sort_results: bool = True, test_paid: bool = True) -> list[dict[str, Any]]:
        providers = self.router.providers(); results: list[dict[str, Any]] = []; jobs: list[tuple[AIProvider, str, dict[str, Any]]] = []; seen: set[tuple[str, str, str]] = set()
        for provider in providers:
            discovered, discovery = self.discover(provider, timeout_seconds=min(timeout_seconds, 20)) if discover_catalog else ([], None)
            catalog = discovered or [{"model_id": model, "display_name": model, "raw_metadata": {}} for model in provider.models]
            for item in catalog:
                model = str(item.get("model_id") or "").strip(); key = (provider.name.lower(), provider.base_url.rstrip("/"), model)
                if not model or key in seen: continue
                seen.add(key); pricing = self.pricing_status(item)
                row = {"provider": provider.name, "model": model, "display_name": item.get("display_name") or model, "free": pricing == "known_free", "pricing_status": pricing, "discovered": bool(discovered), "discovery": discovery, "ok": False, "live_tested": True, "latency_ms": 0, "status": "queued_live_test", "response": ""}
                results.append(row)
                if test_paid or pricing == "known_free": jobs.append((provider, model, item))
        row_map = {(row["provider"], row["model"]): row for row in results}
        with ThreadPoolExecutor(max_workers=self.MAX_CONCURRENT_TESTS, thread_name_prefix="ra-health") as executor:
            futures = {executor.submit(self._live_test_one, provider, model, timeout_seconds, item): (provider.name, model) for provider, model, item in jobs}
            for future in as_completed(futures):
                key = futures[future]
                try: tested = future.result()
                except Exception as exc: tested = {"ok": False, "status": f"test_failed:{type(exc).__name__}"}
                if row_map.get(key) is not None: row_map[key].update(tested, live_tested=True)
        if sort_results: results.sort(key=lambda row: (row["pricing_status"] != "known_free", not row["ok"], row["latency_ms"], row["provider"], row["model"]))
        return results
