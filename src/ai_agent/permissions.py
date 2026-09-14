from pathlib import Path

PROTECTED_PATTERNS = [
    '.env',
    'secrets',
    'credentials',
    'production.db',
]


def can_modify(path: str) -> bool:
    value = str(Path(path)).lower()
    return not any(item in value for item in PROTECTED_PATTERNS)
