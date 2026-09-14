from sqlalchemy.orm import Session

from src.database.models.assignment import Assignment, AssignmentSubmission, SubmissionStatus
from src.database.models.online_enrollment import EnrollmentStatus
from src.database.repositories.assignment_repository import AssignmentRepository
from src.services.online_enrollment_service import OnlineEnrollmentService

MAX_CONTENT_LENGTH = 4000


class AssignmentServiceError(ValueError):
    pass


class AssignmentService:

    def __init__(self) -> None:
        self.repository = AssignmentRepository()
        self.enrollment_service = OnlineEnrollmentService()

    def create_assignment(
        self,
        db: Session,
        *,
        online_course_id: int,
        title: str,
        description: str,
    ) -> Assignment:
        title = (title or "").strip()
        description = (description or "").strip()
        if not title:
            raise AssignmentServiceError("empty_title")
        if not description:
            raise AssignmentServiceError("empty_description")
        if len(title) > 200:
            raise AssignmentServiceError("title_too_long")
        if len(description) > MAX_CONTENT_LENGTH:
            raise AssignmentServiceError("description_too_long")

        return self.repository.create_assignment(
            db,
            Assignment(
                online_course_id=online_course_id,
                title=title,
                description=description,
                is_active=True,
            ),
        )

    def get_assignment(self, db: Session, assignment_id: int) -> Assignment | None:
        return self.repository.get_assignment(db, assignment_id)

    def list_for_course(
        self, db: Session, online_course_id: int, *, active_only: bool = True
    ) -> list[Assignment]:
        return self.repository.list_by_course(db, online_course_id, active_only=active_only)

    def list_active(self, db: Session) -> list[Assignment]:
        return self.repository.list_active(db)

    def toggle_active(self, db: Session, assignment_id: int) -> Assignment:
        assignment = self.repository.get_assignment(db, assignment_id)
        if not assignment:
            raise AssignmentServiceError("not_found")
        return self.repository.toggle_active(db, assignment)

    def submit(
        self,
        db: Session,
        *,
        assignment_id: int,
        user_id: int,
        content: str,
    ) -> AssignmentSubmission:
        assignment = self.repository.get_assignment(db, assignment_id)
        if not assignment or not assignment.is_active:
            raise AssignmentServiceError("assignment_unavailable")

        content = (content or "").strip()
        if not content:
            raise AssignmentServiceError("empty_content")
        if len(content) > MAX_CONTENT_LENGTH:
            raise AssignmentServiceError("content_too_long")

        enrollments = self.enrollment_service.get_active_by_user(db, user_id)
        allowed = any(
            e.online_course_id == assignment.online_course_id
            and e.status == EnrollmentStatus.ACTIVE
            for e in enrollments
        )
        if not allowed:
            raise AssignmentServiceError("not_enrolled")

        existing = self.repository.get_user_submission(db, assignment_id, user_id)
        if existing and existing.status == SubmissionStatus.PENDING:
            raise AssignmentServiceError("already_pending")

        return self.repository.create_submission(
            db,
            AssignmentSubmission(
                assignment_id=assignment_id,
                user_id=user_id,
                content=content,
                status=SubmissionStatus.PENDING,
            ),
        )

    def list_pending_submissions(self, db: Session) -> list[AssignmentSubmission]:
        return self.repository.list_pending_submissions(db)

    def get_submission(self, db: Session, submission_id: int) -> AssignmentSubmission | None:
        return self.repository.get_submission(db, submission_id)

    def get_user_submission(
        self, db: Session, assignment_id: int, user_id: int
    ) -> AssignmentSubmission | None:
        return self.repository.get_user_submission(db, assignment_id, user_id)

    def review(
        self,
        db: Session,
        submission_id: int,
        *,
        feedback: str,
        score: int | None = None,
        returned: bool = False,
    ) -> AssignmentSubmission:
        submission = self.repository.get_submission(db, submission_id)
        if not submission:
            raise AssignmentServiceError("not_found")
        if submission.status != SubmissionStatus.PENDING:
            raise AssignmentServiceError("already_reviewed")

        feedback = (feedback or "").strip()
        if not feedback:
            raise AssignmentServiceError("empty_feedback")
        if len(feedback) > MAX_CONTENT_LENGTH:
            raise AssignmentServiceError("feedback_too_long")
        if score is not None and (score < 0 or score > 100):
            raise AssignmentServiceError("invalid_score")

        status = SubmissionStatus.RETURNED if returned else SubmissionStatus.REVIEWED
        return self.repository.review_submission(
            db,
            submission,
            feedback=feedback,
            score=score,
            status=status,
        )
