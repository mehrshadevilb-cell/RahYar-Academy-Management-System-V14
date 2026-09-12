from sqlalchemy import create_engine

from src.core.config import get_settings


settings = get_settings()

engine_kwargs = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}

# SQLite does not support the same connection pool options as PostgreSQL.
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update({
        "pool_size": 5,
        "max_overflow": 10,
        "pool_recycle": 1800,
    })

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
