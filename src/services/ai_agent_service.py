"""AIAgentService — loads restored implementation from compressed parts."""
from __future__ import annotations

import base64
import sys
import types
import zlib
from importlib import resources
from pathlib import Path

_DIR = Path(__file__).resolve().parent / "_ai_agent_blob"


def _load():
    parts = []
    for i in range(20):
        p = _DIR / f"part{i}.txt"
        if not p.exists():
            break
        parts.append(p.read_text(encoding="utf-8").strip())
    if not parts:
        raise ImportError("ai_agent_service blob parts missing under _ai_agent_blob/")
    raw = zlib.decompress(base64.b64decode("".join(parts)))
    mod = types.ModuleType("src.services._ai_agent_loaded")
    mod.__file__ = str(Path(__file__).resolve())
    sys.modules[mod.__name__] = mod
    exec(compile(raw, "ai_agent_service.py", "exec"), mod.__dict__)
    return mod


_m = _load()
AIAgentError = _m.AIAgentError
AIAgentService = _m.AIAgentService
