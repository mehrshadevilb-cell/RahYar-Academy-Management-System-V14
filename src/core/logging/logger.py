import logging
import sys

_CONFIGURED = False


def _configure_root_logger() -> None:
    global _CONFIGURED

    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root = logging.getLogger("rahyar")
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    root.propagate = False

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger under the shared "rahyar" namespace, e.g.
    get_logger("bot.errors") -> logger named "rahyar.bot.errors".

    Never pass secrets (bot token, DB password, API keys) into log
    messages - see PROJECT_CONTEXT.md Sections 19/21.
    """

    _configure_root_logger()
    return logging.getLogger(f"rahyar.{name}")
