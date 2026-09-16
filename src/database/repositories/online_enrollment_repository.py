from sqlalchemy.orm import Session, joinedload

from src.database.models.online_enrollment import OnlineEnrollment, EnrollmentStatus


class OnlineEnrollmentRepository:

    def create(self, db: Session, enrollment: OnlineEnrollment):
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        return enrollment

    def get_by_id(self, db: Session, enrollment_id: int):
        return (
            db.query(OnlineEnrollment)
            .options(joinedload(OnlineEnrollment.online_course))
            .filter(OnlineEnrollment.id == enrollment_id)
            .first()
        )

    def get_active_by_user(self, db: Session, user_id: int):
        return (
            db.query(OnlineEnrollment)
            .options(joinedload(OnlineEnrollment.online_course))
            .filter(
                OnlineEnrollment.user_id == user_id,
                OnlineEnrollment.status == EnrollmentStatus.ACTIVE,
            )
            .all()
        )

    def get_by_course(self, db: Session, online_course_id: int) -> list[OnlineEnrollment]:
        return (
            db.query(OnlineEnrollment)
            .options(joinedload(OnlineEnrollment.online_course))
            .filter(OnlineEnrollment.online_course_id == online_course_id)
            .order_by(OnlineEnrollment.created_at.desc())
            .all()
        )

    def get_active_for_user_course(
        self, db: Session, user_id: int, online_course_id: int
    ) -> OnlineEnrollment | None:
        return (
            db.query(OnlineEnrollment)
            .filter(
                OnlineEnrollment.user_id == user_id,
                OnlineEnrollment.online_course_id == online_course_id,
                OnlineEnrollment.status == EnrollmentStatus.ACTIVE,
            )
            .first()
        )

    def save(self, db: Session, enrollment: OnlineEnrollment) -> OnlineEnrollment:
        db.commit()
        db.refresh(enrollment)
        return enrollment
