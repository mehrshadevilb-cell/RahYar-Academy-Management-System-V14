"""Auto-generated compressed AIAgentService module (restore)."""
from __future__ import annotations

import base64
import sys
import types
import zlib

_PARTS = [
    "PLACEHOLDER_WILL_FAIL",
]


def _load():
    raw = zlib.decompress(base64.b64decode("".join(_PARTS)))
    mod = types.ModuleType("src.services._ai_agent_loaded")
    mod.__file__ = __file__
    code = compile(raw, "ai_agent_service.py", "exec")
    sys.modules[mod.__name__] = mod
    exec(code, mod.__dict__)
    return mod


_m = _load()
AIAgentError = _m.AIAgentError
AIAgentService = _m.AIAgentService
