from sqlalchemy.orm import Session

from src.database.models.exam import (
    Exam,
    ExamAnswer,
    ExamAttempt,
    ExamOption,
    ExamQuestion,
)
from src.database.models.online_enrollment import EnrollmentStatus
from src.database.repositories.exam_repository import ExamRepository
from src.services.online_enrollment_service import OnlineEnrollmentService

MIN_OPTIONS = 2
MAX_OPTIONS = 6


class ExamServiceError(ValueError):
    pass


class ExamService:

    def __init__(self) -> None:
        self.repository = ExamRepository()
        self.enrollment_service = OnlineEnrollmentService()

    def create_exam(
        self,
        db: Session,
        *,
        online_course_id: int,
        title: str,
        pass_score_percent: int = 70,
        max_attempts: int = 1,
    ) -> Exam:
        title = (title or "").strip()
        if not title:
            raise ExamServiceError("empty_title")
        if not (0 <= pass_score_percent <= 100):
            raise ExamServiceError("invalid_pass_score")
        if max_attempts < 1:
            raise ExamServiceError("invalid_max_attempts")

        return self.repository.create_exam(
            db,
            Exam(
                online_course_id=online_course_id,
                title=title,
                pass_score_percent=pass_score_percent,
                max_attempts=max_attempts,
                is_active=True,
            ),
        )

    def get_exam(self, db: Session, exam_id: int) -> Exam | None:
        return self.repository.get_exam(db, exam_id)

    def list_for_course(
        self, db: Session, online_course_id: int, *, active_only: bool = True
    ) -> list[Exam]:
        return self.repository.list_by_course(
            db, online_course_id, active_only=active_only
        )

    def add_question(
        self,
        db: Session,
        *,
        exam_id: int,
        text: str,
        options: list[str],
        correct_index: int,
    ) -> ExamQuestion:
        exam = self.repository.get_exam(db, exam_id)
        if not exam:
            raise ExamServiceError("exam_not_found")

        text = (text or "").strip()
        if not text:
            raise ExamServiceError("empty_question")

        cleaned = [o.strip() for o in options if (o or "").strip()]
        if len(cleaned) < MIN_OPTIONS:
            raise ExamServiceError("too_few_options")
        if len(cleaned) > MAX_OPTIONS:
            raise ExamServiceError("too_many_options")
        if correct_index < 0 or correct_index >= len(cleaned):
            raise ExamServiceError("invalid_correct_index")

        question = self.repository.add_question(
            db,
            ExamQuestion(
                exam_id=exam_id,
                text=text,
                sort_order=len(exam.questions),
            ),
        )
        for i, opt_text in enumerate(cleaned):
            self.repository.add_option(
                db,
                ExamOption(
                    question_id=question.id,
                    text=opt_text,
                    is_correct=(i == correct_index),
                    sort_order=i,
                ),
            )
        refreshed = self.repository.get_exam(db, exam_id)
        return refreshed.questions[-1]  # type: ignore

    def _assert_enrolled(self, db: Session, user_id: int, online_course_id: int) -> None:
        enrollments = self.enrollment_service.get_active_by_user(db, user_id)
        ok = any(
            e.online_course_id == online_course_id and e.status == EnrollmentStatus.ACTIVE
            for e in enrollments
        )
        if not ok:
            raise ExamServiceError("not_enrolled")

    def start_attempt(self, db: Session, *, exam_id: int, user_id: int) -> ExamAttempt:
        exam = self.repository.get_exam(db, exam_id)
        if not exam or not exam.is_active:
            raise ExamServiceError("exam_unavailable")
        if not exam.questions:
            raise ExamServiceError("exam_empty")

        self._assert_enrolled(db, user_id, exam.online_course_id)

        open_attempt = self.repository.get_open_attempt(db, exam_id, user_id)
        if open_attempt:
            return open_attempt

        completed = self.repository.count_completed_attempts(db, exam_id, user_id)
        if completed >= exam.max_attempts:
            raise ExamServiceError("attempts_exhausted")

        return self.repository.create_attempt(
            db,
            ExamAttempt(
                exam_id=exam_id,
                user_id=user_id,
                score=0,
                total_questions=len(exam.questions),
            ),
        )

    def answer(
        self,
        db: Session,
        *,
        attempt_id: int,
        question_id: int,
        option_id: int,
        user_id: int,
    ) -> tuple[ExamAttempt, bool]:
        """Returns (attempt, just_completed). Does NOT reveal correctness mid-exam."""
        attempt = self.repository.get_attempt(db, attempt_id)
        if not attempt or attempt.user_id != user_id:
            raise ExamServiceError("attempt_not_found")
        if attempt.completed_at is not None:
            raise ExamServiceError("already_completed")

        exam = self.repository.get_exam(db, attempt.exam_id)
        if not exam:
            raise ExamServiceError("exam_unavailable")

        question = next((q for q in exam.questions if q.id == question_id), None)
        if not question:
            raise ExamServiceError("question_not_found")
        if any(a.question_id == question_id for a in attempt.answers):
            raise ExamServiceError("already_answered")

        option = self.repository.get_option(db, option_id)
        if not option or option.question_id != question_id:
            raise ExamServiceError("invalid_option")

        self.repository.save_answer(
            db,
            ExamAnswer(
                attempt_id=attempt.id,
                question_id=question_id,
                selected_option_id=option_id,
                is_correct=bool(option.is_correct),
            ),
        )

        attempt = self.repository.get_attempt(db, attempt_id)
        answered = {a.question_id for a in attempt.answers}
        all_ids = {q.id for q in exam.questions}
        just_completed = answered >= all_ids

        if just_completed:
            score = sum(1 for a in attempt.answers if a.is_correct)
            total = len(exam.questions)
            percent = int(round((score / total) * 100)) if total else 0
            passed = percent >= exam.pass_score_percent
            attempt = self.repository.complete_attempt(
                db,
                attempt,
                score=score,
                total=total,
                score_percent=percent,
                passed=passed,
            )

        return attempt, just_completed

    def next_unanswered_question(
        self, db: Session, attempt_id: int
    ) -> ExamQuestion | None:
        attempt = self.repository.get_attempt(db, attempt_id)
        if not attempt:
            return None
        exam = self.repository.get_exam(db, attempt.exam_id)
        if not exam:
            return None
        answered = {a.question_id for a in attempt.answers}
        for q in sorted(exam.questions, key=lambda x: x.sort_order):
            if q.id not in answered:
                return q
        return None
