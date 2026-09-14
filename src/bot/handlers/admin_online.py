"""Full admin_online handlers (compressed source for transport)."""
import base64
import zlib
import types

_SRC = zlib.decompress(
    base64.b64decode(
        open(__file__, "rb").read().split(b"_B64_START_\n", 1)[1].split(b"\n_B64_END_", 1)[0]
    )
).decode("utf-8")

_mod = types.ModuleType(__name__)
_mod.__file__ = __file__
exec(compile(_SRC, __file__, "exec"), _mod.__dict__)
router = _mod.router
for _k, _v in list(_mod.__dict__.items()):
    if not _k.startswith("_"):
        globals()[_k] = _v

_B64_START_
