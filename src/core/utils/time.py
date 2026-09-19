"""Time helpers shared by database models and services.

The current schema uses SQLAlchemy DateTime columns without timezone=True.
Return a naive UTC value at the persistence boundary until the schema can be
migrated consistently; callers that compare external timestamps should attach
UTC explicitly before comparison.
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return the current UTC time as a naive value for legacy DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
