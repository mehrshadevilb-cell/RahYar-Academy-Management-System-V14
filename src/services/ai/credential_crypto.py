from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from src.core.config import get_settings


def _fernet() -> Fernet:
    secret = get_settings().SECRET_KEY.encode("utf-8")
    if len(secret) < 32:
        raise ValueError("SECRET_KEY must contain at least 32 characters for AI credential encryption")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt_api_key(value: str) -> str:
    if not value:
        raise ValueError("API key cannot be empty")
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_api_key(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        raise ValueError("Unable to decrypt AI provider credential") from exc
