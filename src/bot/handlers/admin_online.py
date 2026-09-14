"""Admin online handlers."""
import base64
import zlib
import types
from src.bot.handlers.admin_online_body_b64 import B64

_SRC = zlib.decompress(base64.b64decode(B64)).decode("utf-8")
_mod = types.ModuleType(__name__)
_mod.__file__ = __file__
exec(compile(_SRC, __file__, "exec"), _mod.__dict__)
router = _mod.router
for _k, _v in list(_mod.__dict__.items()):
    if not _k.startswith("_"):
        globals()[_k] = _v
