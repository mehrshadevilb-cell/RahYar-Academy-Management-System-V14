from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest

from src.database.base import Base
from src.database.models.online_course import OnlineCourse
from src.database.models.online_enrollment import (
    EnrollmentStatus,
    OnlineEnrollment,
    PaymentModel,
)
from src.database.models.user import User, UserRole
from src.services.exam_service import ExamService, ExamServiceError


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed(db):
    user = User(full_name="Student", role=UserRole.STUDENT)
    course = OnlineCourse(name="Harmony", teacher="T", duration_minutes=60)
    db.add_all([user, course])
    db.commit()
    db.refresh(user)
    db.refresh(course)
    db.add(
        OnlineEnrollment(
            user_id=user.id,
            online_course_id=course.id,
            payment_model=PaymentModel.TERM,
            remaining_sessions=12,
            status=EnrollmentStatus.ACTIVE,
        )
    )
    db.commit()
    return user, course


def test_exam_pass_and_attempt_limit():
    db = make_db()
    service = ExamService()
    user, course = seed(db)

    exam = service.create_exam(
        db,
        online_course_id=course.id,
        title="Midterm",
        pass_score_percent=50,
        max_attempts=1,
    )
    q1 = service.add_question(
        db, exam_id=exam.id, text="A?", options=["yes", "no"], correct_index=0
    )
    q2 = service.add_question(
        db, exam_id=exam.id, text="B?", options=["1", "2"], correct_index=1
    )

    attempt = service.start_attempt(db, exam_id=exam.id, user_id=user.id)
    opts1 = sorted(q1.options, key=lambda o: o.sort_order)
    attempt, done = service.answer(
        db,
        attempt_id=attempt.id,
        question_id=q1.id,
        option_id=opts1[0].id,
        user_id=user.id,
    )
    assert done is False

    opts2 = sorted(q2.options, key=lambda o: o.sort_order)
    attempt, done = service.answer(
        db,
        attempt_id=attempt.id,
        question_id=q2.id,
        option_id=opts2[1].id,
        user_id=user.id,
    )
    assert done is True
    assert attempt.passed is True
    assert attempt.score_percent == 100

    with pytest.raises(ExamServiceError, match="attempts_exhausted"):
        service.start_attempt(db, exam_id=exam.id, user_id=user.id)
