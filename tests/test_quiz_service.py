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
from src.services.quiz_service import QuizService, QuizServiceError


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed(db):
    user = User(full_name="Student", role=UserRole.STUDENT)
    course = OnlineCourse(name="Theory", teacher="T", duration_minutes=60)
    db.add_all([user, course])
    db.commit()
    db.refresh(user)
    db.refresh(course)
    db.add(
        OnlineEnrollment(
            user_id=user.id,
            online_course_id=course.id,
            payment_model=PaymentModel.MONTHLY,
            remaining_sessions=4,
            status=EnrollmentStatus.ACTIVE,
        )
    )
    db.commit()
    return user, course


def test_full_quiz_flow():
    db = make_db()
    service = QuizService()
    user, course = seed(db)

    quiz = service.create_quiz(db, online_course_id=course.id, title="Harmony 1")
    q1 = service.add_question(
        db,
        quiz_id=quiz.id,
        text="2+2?",
        options=["3", "4", "5"],
        correct_index=1,
    )
    q2 = service.add_question(
        db,
        quiz_id=quiz.id,
        text="Capital of France?",
        options=["Paris", "London"],
        correct_index=0,
    )

    attempt = service.start_attempt(db, quiz_id=quiz.id, user_id=user.id)
    opts1 = sorted(q1.options, key=lambda o: o.sort_order)
    attempt, correct, done = service.answer(
        db,
        attempt_id=attempt.id,
        question_id=q1.id,
        option_id=opts1[1].id,
        user_id=user.id,
    )
    assert correct is True
    assert done is False

    opts2 = sorted(q2.options, key=lambda o: o.sort_order)
    attempt, correct, done = service.answer(
        db,
        attempt_id=attempt.id,
        question_id=q2.id,
        option_id=opts2[0].id,
        user_id=user.id,
    )
    assert done is True
    assert attempt.score == 2
    assert attempt.completed_at is not None


def test_not_enrolled_blocked():
    db = make_db()
    service = QuizService()
    user, course = seed(db)
    outsider = User(full_name="X", role=UserRole.STUDENT)
    db.add(outsider)
    db.commit()
    db.refresh(outsider)

    quiz = service.create_quiz(db, online_course_id=course.id, title="Q")
    service.add_question(
        db, quiz_id=quiz.id, text="A?", options=["1", "2"], correct_index=0
    )
    with pytest.raises(QuizServiceError, match="not_enrolled"):
        service.start_attempt(db, quiz_id=quiz.id, user_id=outsider.id)
