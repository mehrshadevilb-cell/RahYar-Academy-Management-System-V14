"""Full admin_online handlers (compressed source)."""
import base64
import zlib

_SRC = zlib.decompress(
    base64.b64decode(
        open(__file__, "rb")  # placeholder replaced below
    )
)
