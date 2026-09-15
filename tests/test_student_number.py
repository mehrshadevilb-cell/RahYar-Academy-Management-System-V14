from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database.base import Base
from src.database.models.user import User
from src.database.repositories.profile_repository import ProfileRepository
import src.database.models  # noqa: F401 - register all models


def test_student_number_resolves_rh_and_numeric_formats():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        student = User(full_name="Test Student")
        db.add(student)
        db.commit()
        db.refresh(student)

        repository = ProfileRepository()
        assert repository.get_by_student_number(db, f"RH{student.id:06d}").id == student.id
        assert repository.get_by_student_number(db, str(student.id)).id == student.id
        assert repository.get_by_student_number(db, "not-a-number") is None
