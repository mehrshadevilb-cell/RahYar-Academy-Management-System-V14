import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("AI_DB_ONLY", "false")
for _provider_key in (
    "OPENAI_API_KEY",
    "AI_API_KEY",
    "AI2_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
):
    os.environ.pop(_provider_key, None)
