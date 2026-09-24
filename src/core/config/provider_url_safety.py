from __future__ import annotations

import re
from urllib.parse import urlparse

_API_KEY_PREFIXES = ("gsk_", "sk-", "sk_", "sk-ant-", "xai-", "xk-", "or-", "csk-")


def looks_like_api_key(value: str) -> bool:
    candidate = (value or "").strip()
    lowered = candidate.lower()
    if not candidate:
        return False
    if lowered.startswith(_API_KEY_PREFIXES):
        return True
    return "://" not in candidate and len(candidate) >= 32 and bool(re.fullmatch(r"[A-Za-z0-9_.:+\-/=]+", candidate))


def validate_provider_base_url(value: str) -> str:
    candidate = (value or "").strip().rstrip("/")
    if not candidate or looks_like_api_key(candidate):
        return ""
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    if parsed.username or parsed.password:
        return ""
    return candidate
