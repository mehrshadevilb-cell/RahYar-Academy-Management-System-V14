from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest

from src.database.base import Base
from src.database.models.assignment import SubmissionStatus
from src.database.models.online_course import OnlineCourse
from src.database.models.online_enrollment import (
    EnrollmentStatus,
    OnlineEnrollment,
    PaymentModel,
)
from src.database.models.user import User, UserRole
from src.services.assignment_service import AssignmentService, AssignmentServiceError


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed(db):
    user = User(full_name="Student", role=UserRole.STUDENT)
    course = OnlineCourse(name="Mixing", teacher="T", duration_minutes=60)
    db.add_all([user, course])
    db.commit()
    db.refresh(user)
    db.refresh(course)
    enrollment = OnlineEnrollment(
        user_id=user.id,
        online_course_id=course.id,
        payment_model=PaymentModel.MONTHLY,
        remaining_sessions=4,
        status=EnrollmentStatus.ACTIVE,
    )
    db.add(enrollment)
    db.commit()
    return user, course


def test_create_submit_review():
    db = make_db()
    service = AssignmentService()
    user, course = seed(db)

    assignment = service.create_assignment(
        db,
        online_course_id=course.id,
        title="تمرین اکولایزر",
        description="یک ترک را EQ کنید و توضیح دهید",
    )
    submission = service.submit(
        db,
        assignment_id=assignment.id,
        user_id=user.id,
        content="لینک فایل + توضیح",
    )
    assert submission.status == SubmissionStatus.PENDING

    reviewed = service.review(
        db, submission.id, feedback="خوب بود", score=90, returned=False
    )
    assert reviewed.status == SubmissionStatus.REVIEWED
    assert reviewed.score == 90


def test_not_enrolled_cannot_submit():
    db = make_db()
    service = AssignmentService()
    user, course = seed(db)
    outsider = User(full_name="Other", role=UserRole.STUDENT)
    db.add(outsider)
    db.commit()
    db.refresh(outsider)

    assignment = service.create_assignment(
        db, online_course_id=course.id, title="A", description="B"
    )
    with pytest.raises(AssignmentServiceError, match="not_enrolled"):
        service.submit(
            db, assignment_id=assignment.id, user_id=outsider.id, content="x"
        )


def test_duplicate_pending_blocked():
    db = make_db()
    service = AssignmentService()
    user, course = seed(db)
    assignment = service.create_assignment(
        db, online_course_id=course.id, title="A", description="B"
    )
    service.submit(db, assignment_id=assignment.id, user_id=user.id, content="first")
    with pytest.raises(AssignmentServiceError, match="already_pending"):
        service.submit(db, assignment_id=assignment.id, user_id=user.id, content="second")
