from pathlib import Path

# Full implementation loaded from sibling module to keep this entry thin.
from src.bot.handlers import admin_online_body as _body

globals().update({k: v for k, v in vars(_body).items() if not k.startswith("_") or k == "router"})
router = _body.router
