"""Request context helpers.

Keeps request-scoped metadata isolated from FastAPI routes and services.
This is the first step toward better tracing and debugging across the
Telegram + Web + AI stack.
"""

from contextvars import ContextVar


request_id_context: ContextVar[str | None] = ContextVar(
    "request_id_context",
    default=None,
)


def get_request_id() -> str | None:
    """Return the current request identifier when available."""
    return request_id_context.get()


def set_request_id(request_id: str) -> None:
    """Store request identifier for the current execution context."""
    request_id_context.set(request_id)
