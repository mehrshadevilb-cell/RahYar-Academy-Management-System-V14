from sqlalchemy import create_engine, inspect

from src.database.base import Base
import src.database.models  # noqa: F401 - registers every model on Base.metadata


def test_all_models_register_for_schema_creation():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    tables = set(inspect(engine).get_table_names())
    assert {"discount_codes", "payments", "online_time_slots", "reservations"} <= tables
