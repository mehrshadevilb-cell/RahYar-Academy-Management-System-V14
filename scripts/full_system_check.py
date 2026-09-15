from __future__ import annotations

import importlib
import pathlib
import subprocess
import sys
from dataclasses import dataclass


ROOT = pathlib.Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]


CHECKS = (
    Check("compileall", (sys.executable, "-m", "compileall", "-q", "src", "tests", "alembic", "scripts")),
    Check("alembic heads", ("alembic", "heads")),
    Check("pytest", (sys.executable, "-m", "pytest", "-q")),
)

# Import checks catch broken module-level dependencies that compileall cannot see.
IMPORTS = (
    "src.ai.provider_router",
    "src.ai.latency_aware_provider_router",
    "src.services.provider_model_health_service",
    "src.services.routed_ai_agent_service",
    "src.services.ai_agent_runtime",
    "src.bot.handlers.admin_ai",
)


def run(command: tuple[str, ...]) -> int:
    completed = subprocess.run(command, cwd=ROOT, check=False)
    return completed.returncode


def main() -> int:
    failures: list[str] = []
    print("=== RahYar full system check ===")

    for name, command in ((check.name, check.command) for check in CHECKS):
        print(f"[CHECK] {name}")
        code = run(command)
        if code:
            failures.append(f"{name} (exit={code})")

    print("[CHECK] critical imports")
    for module in IMPORTS:
        try:
            importlib.import_module(module)
            print(f"  OK {module}")
        except Exception as exc:  # pragma: no cover - diagnostic script
            failures.append(f"import {module}: {type(exc).__name__}: {exc}")
            print(f"  FAIL {module}: {type(exc).__name__}: {exc}")

    if failures:
        print("\nFAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
