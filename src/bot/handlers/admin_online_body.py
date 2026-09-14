"""Assemble full admin_online implementation from split parts."""
from pathlib import Path

_p = Path(__file__).resolve().parent
_code = (_p / "_admin_online_part1.py").read_text(encoding="utf-8")
_code += (_p / "_admin_online_part2.py").read_text(encoding="utf-8")
exec(_code, globals())
del _code, _p
