from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


CLOUDFLARE_FALLBACK_MODELS: tuple[str, ...] = (
    "@cf/meta/llama-3.1-8b-instruct",
    "@cf/meta/llama-3.2-3b-instruct",
    "@cf/qwen/qwen2.5-coder-32b-instruct",
    "@cf/google/gemma-2-9b-it",
    "@cf/mistral/mistral-7b-instruct-v0.2",
)


def resolve_cloudflare_key() -> str:
    return (
        os.getenv("CLOUDFLARE_API_KEY")
        or os.getenv("CLOUDFLARE_API_TOKEN")
        or os.getenv("CLAUDFLARE_API_KEY")  # common typo
        or ""
    ).strip()


def resolve_cloudflare_base_url(normalize) -> str:
    base = (
        os.getenv("CLOUDFLARE_AI_BASE_URL")
        or os.getenv("CLOUDFLARE_BASE_URL")
        or ""
    ).strip()
    if not base:
        account_id = (os.getenv("CLOUDFLARE_ACCOUNT_ID") or "").strip()
        if account_id:
            base = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1"
    return normalize(base) if base else ""


def resolve_cloudflare_model() -> str:
    return (
        os.getenv("CLOUDFLARE_AI_MODEL")
        or os.getenv("CLOUDFLARE_MODEL")
        or ""
    ).strip()


def discover_cloudflare_models(api_key: str, base_url: str, timeout: int = 15) -> tuple[str, ...]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "RahYar-CloudflareDiscovery/1.0",
    }
    base = base_url.rstrip("/")
    urls = [base + "/models"]
    if base.endswith("/ai/v1"):
        urls.append(base[: -len("/v1")] + "/models/search?per_page=50&hide_experimental=true")
    models: list[str] = []
    for url in urls:
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=max(5, min(timeout, 25))) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue
        items: list[Any] = []
        if isinstance(payload, dict):
            for key in ("result", "data", "models"):
                if isinstance(payload.get(key), list):
                    items.extend(payload[key])
        for item in items:
            if isinstance(item, dict):
                mid = str(item.get("id") or item.get("name") or item.get("model") or "").strip()
                task = str(item.get("task") or item.get("task_type") or "").lower()
                if task and "embed" in task and "generat" not in task:
                    continue
            else:
                mid = str(item).strip()
            if mid.startswith("@cf/") or (mid and "cloudflare.com" in base):
                if mid and mid not in models:
                    models.append(mid)
    if not models:
        models = list(CLOUDFLARE_FALLBACK_MODELS)

    def rank(m: str) -> tuple[int, str]:
        ml = m.lower()
        score = 0
        if "instruct" in ml or "chat" in ml:
            score -= 10
        if "llama-3.1-8b" in ml:
            score -= 5
        if "embed" in ml or "bge-" in ml:
            score += 50
        return (score, m)

    return tuple(sorted(dict.fromkeys(models), key=rank))
