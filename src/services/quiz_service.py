from sqlalchemy.orm import Session

from src.database.models.online_enrollment import EnrollmentStatus
from src.database.models.quiz import (
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizOption,
    QuizQuestion,
)
from src.database.repositories.quiz_repository import QuizRepository
from src.services.online_enrollment_service import OnlineEnrollmentService

MAX_OPTIONS = 6
MIN_OPTIONS = 2


class QuizServiceError(ValueError):
    pass


class QuizService:

    def __init__(self) -> None:
        self.repository = QuizRepository()
        self.enrollment_service = OnlineEnrollmentService()

    def create_quiz(
        self, db: Session, *, online_course_id: int, title: str
    ) -> Quiz:
        title = (title or "").strip()
        if not title:
            raise QuizServiceError("empty_title")
        if len(title) > 200:
            raise QuizServiceError("title_too_long")
        return self.repository.create_quiz(
            db,
            Quiz(online_course_id=online_course_id, title=title, is_active=True),
        )

    def get_quiz(self, db: Session, quiz_id: int) -> Quiz | None:
        return self.repository.get_quiz(db, quiz_id)

    def list_for_course(
        self, db: Session, online_course_id: int, *, active_only: bool = True
    ) -> list[Quiz]:
        return self.repository.list_by_course(
            db, online_course_id, active_only=active_only
        )

    def add_question(
        self,
        db: Session,
        *,
        quiz_id: int,
        text: str,
        options: list[str],
        correct_index: int,
    ) -> QuizQuestion:
        quiz = self.repository.get_quiz(db, quiz_id)
        if not quiz:
            raise QuizServiceError("quiz_not_found")

        text = (text or "").strip()
        if not text:
            raise QuizServiceError("empty_question")

        cleaned = [o.strip() for o in options if (o or "").strip()]
        if len(cleaned) < MIN_OPTIONS:
            raise QuizServiceError("too_few_options")
        if len(cleaned) > MAX_OPTIONS:
            raise QuizServiceError("too_many_options")
        if correct_index < 0 or correct_index >= len(cleaned):
            raise QuizServiceError("invalid_correct_index")

        sort_order = len(quiz.questions)
        question = QuizQuestion(quiz_id=quiz_id, text=text, sort_order=sort_order)
        question = self.repository.add_question(db, question)

        for i, opt_text in enumerate(cleaned):
            self.repository.add_option(
                db,
                QuizOption(
                    question_id=question.id,
                    text=opt_text,
                    is_correct=(i == correct_index),
                    sort_order=i,
                ),
            )

        return self.repository.get_quiz(db, quiz_id).questions[-1]  # type: ignore

    def toggle_active(self, db: Session, quiz_id: int) -> Quiz:
        quiz = self.repository.get_quiz(db, quiz_id)
        if not quiz:
            raise QuizServiceError("quiz_not_found")
        return self.repository.toggle_active(db, quiz)

    def _assert_enrolled(self, db: Session, user_id: int, online_course_id: int) -> None:
        enrollments = self.enrollment_service.get_active_by_user(db, user_id)
        ok = any(
            e.online_course_id == online_course_id and e.status == EnrollmentStatus.ACTIVE
            for e in enrollments
        )
        if not ok:
            raise QuizServiceError("not_enrolled")

    def start_attempt(self, db: Session, *, quiz_id: int, user_id: int) -> QuizAttempt:
        quiz = self.repository.get_quiz(db, quiz_id)
        if not quiz or not quiz.is_active:
            raise QuizServiceError("quiz_unavailable")
        if not quiz.questions:
            raise QuizServiceError("quiz_empty")

        self._assert_enrolled(db, user_id, quiz.online_course_id)

        open_attempt = self.repository.get_open_attempt(db, quiz_id, user_id)
        if open_attempt:
            return open_attempt

        return self.repository.create_attempt(
            db,
            QuizAttempt(
                quiz_id=quiz_id,
                user_id=user_id,
                score=0,
                total_questions=len(quiz.questions),
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
    ) -> tuple[QuizAttempt, bool, bool]:
        """Returns (attempt, is_correct, just_completed)."""
        attempt = self.repository.get_attempt(db, attempt_id)
        if not attempt or attempt.user_id != user_id:
            raise QuizServiceError("attempt_not_found")
        if attempt.completed_at is not None:
            raise QuizServiceError("already_completed")

        quiz = self.repository.get_quiz(db, attempt.quiz_id)
        if not quiz:
            raise QuizServiceError("quiz_unavailable")

        question = next((q for q in quiz.questions if q.id == question_id), None)
        if not question:
            raise QuizServiceError("question_not_found")

        if any(a.question_id == question_id for a in attempt.answers):
            raise QuizServiceError("already_answered")

        option = self.repository.get_option(db, option_id)
        if not option or option.question_id != question_id:
            raise QuizServiceError("invalid_option")

        is_correct = bool(option.is_correct)
        self.repository.save_answer(
            db,
            QuizAnswer(
                attempt_id=attempt.id,
                question_id=question_id,
                selected_option_id=option_id,
                is_correct=is_correct,
            ),
        )

        attempt = self.repository.get_attempt(db, attempt_id)
        answered_ids = {a.question_id for a in attempt.answers}
        all_ids = {q.id for q in quiz.questions}
        just_completed = answered_ids >= all_ids

        if just_completed:
            score = sum(1 for a in attempt.answers if a.is_correct)
            attempt = self.repository.complete_attempt(
                db, attempt, score=score, total=len(quiz.questions)
            )

        return attempt, is_correct, just_completed

    def next_unanswered_question(
        self, db: Session, attempt_id: int
    ) -> QuizQuestion | None:
        attempt = self.repository.get_attempt(db, attempt_id)
        if not attempt:
            return None
        quiz = self.repository.get_quiz(db, attempt.quiz_id)
        if not quiz:
            return None
        answered = {a.question_id for a in attempt.answers}
        for q in sorted(quiz.questions, key=lambda x: x.sort_order):
            if q.id not in answered:
                return q
        return None
