"""Restored AIProviderRouter (zlib+base64 body expanded at import)."""
from __future__ import annotations
import base64
import sys
import types
import zlib

_B64_CHUNKS = (
    "PLACEHOLDER_WILL_REPLACE"
)
_src = zlib.decompress(base64.b64decode("".join(_B64_CHUNKS))).decode("utf-8")
_ns: dict = {"__name__": __name__}
exec(compile(_src, "provider_router.py", "exec"), _ns)
for _k, _v in list(_ns.items()):
    if _k.startswith("__"):
        continue
    globals()[_k] = _v
