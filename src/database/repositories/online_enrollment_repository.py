from sqlalchemy.orm import Session

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
            .filter(OnlineEnrollment.id == enrollment_id)
            .first()
        )

    def get_active_by_user(self, db: Session, user_id: int):
        return (
            db.query(OnlineEnrollment)
            .filter(
                OnlineEnrollment.user_id == user_id,
                OnlineEnrollment.status == EnrollmentStatus.ACTIVE,
            )
            .all()
        )
