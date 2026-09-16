"""Startup diagnostics helpers.

Small utility layer to make deployment failures visible in container logs.
"""

from collections.abc import Callable

from src.core.logging.logger import get_logger

logger = get_logger("rahyar.startup")


def run_step(name: str, fn: Callable[[], object]) -> object:
    """Run a startup step and keep the original exception visible."""
    logger.info("[BOOT] starting: %s", name)
    try:
        result = fn()
        logger.info("[BOOT] completed: %s", name)
        return result
    except Exception:
        logger.exception("[BOOT] failed: %s", name)
        raise
