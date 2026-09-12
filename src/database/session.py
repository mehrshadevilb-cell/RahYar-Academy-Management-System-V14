from sqlalchemy.orm import sessionmaker

from .connection import engine


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)