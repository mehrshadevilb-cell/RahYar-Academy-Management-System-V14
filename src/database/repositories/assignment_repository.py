from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.database.models.assignment import Assignment, AssignmentSubmission, SubmissionStatus


class AssignmentRepository:

    def create_assignment(self, db: Session, assignment: Assignment) -> Assignment:
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        return assignment

    def get_assignment(self, db: Session, assignment_id: int) -> Assignment | None:
        return db.query(Assignment).filter(Assignment.id == assignment_id).first()

    def list_by_course(
        self, db: Session, online_course_id: int, *, active_only: bool = True
    ) -> list[Assignment]:
        q = db.query(Assignment).filter(Assignment.online_course_id == online_course_id)
        if active_only:
            q = q.filter(Assignment.is_active.is_(True))
        return q.order_by(Assignment.id.desc()).all()

    def list_active(self, db: Session, limit: int = 50) -> list[Assignment]:
        return (
            db.query(Assignment)
            .filter(Assignment.is_active.is_(True))
            .order_by(Assignment.id.desc())
            .limit(limit)
            .all()
        )

    def toggle_active(self, db: Session, assignment: Assignment) -> Assignment:
        assignment.is_active = not assignment.is_active
        db.commit()
        db.refresh(assignment)
        return assignment

    def create_submission(
        self, db: Session, submission: AssignmentSubmission
    ) -> AssignmentSubmission:
        db.add(submission)
        db.commit()
        db.refresh(submission)
        return submission

    def get_submission(
        self, db: Session, submission_id: int
    ) -> AssignmentSubmission | None:
        return (
            db.query(AssignmentSubmission)
            .filter(AssignmentSubmission.id == submission_id)
            .first()
        )

    def get_user_submission(
        self, db: Session, assignment_id: int, user_id: int
    ) -> AssignmentSubmission | None:
        return (
            db.query(AssignmentSubmission)
            .filter(
                AssignmentSubmission.assignment_id == assignment_id,
                AssignmentSubmission.user_id == user_id,
            )
            .order_by(AssignmentSubmission.id.desc())
            .first()
        )

    def list_pending_submissions(
        self, db: Session, limit: int = 30
    ) -> list[AssignmentSubmission]:
        return (
            db.query(AssignmentSubmission)
            .filter(AssignmentSubmission.status == SubmissionStatus.PENDING)
            .order_by(AssignmentSubmission.id.asc())
            .limit(limit)
            .all()
        )

    def review_submission(
        self,
        db: Session,
        submission: AssignmentSubmission,
        *,
        feedback: str,
        score: int | None,
        status: SubmissionStatus,
    ) -> AssignmentSubmission:
        submission.admin_feedback = feedback
        submission.score = score
        submission.status = status
        submission.reviewed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(submission)
        return submission
