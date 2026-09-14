from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from src.database.models.exam import (
    Exam,
    ExamAnswer,
    ExamAttempt,
    ExamOption,
    ExamQuestion,
)


class ExamRepository:

    def create_exam(self, db: Session, exam: Exam) -> Exam:
        db.add(exam)
        db.commit()
        db.refresh(exam)
        return exam

    def get_exam(self, db: Session, exam_id: int) -> Exam | None:
        return (
            db.query(Exam)
            .options(joinedload(Exam.questions).joinedload(ExamQuestion.options))
            .filter(Exam.id == exam_id)
            .first()
        )

    def list_by_course(
        self, db: Session, online_course_id: int, *, active_only: bool = True
    ) -> list[Exam]:
        q = db.query(Exam).filter(Exam.online_course_id == online_course_id)
        if active_only:
            q = q.filter(Exam.is_active.is_(True))
        return q.order_by(Exam.id.desc()).all()

    def add_question(self, db: Session, question: ExamQuestion) -> ExamQuestion:
        db.add(question)
        db.commit()
        db.refresh(question)
        return question

    def add_option(self, db: Session, option: ExamOption) -> ExamOption:
        db.add(option)
        db.commit()
        db.refresh(option)
        return option

    def create_attempt(self, db: Session, attempt: ExamAttempt) -> ExamAttempt:
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        return attempt

    def get_attempt(self, db: Session, attempt_id: int) -> ExamAttempt | None:
        return (
            db.query(ExamAttempt)
            .options(joinedload(ExamAttempt.answers))
            .filter(ExamAttempt.id == attempt_id)
            .first()
        )

    def get_open_attempt(
        self, db: Session, exam_id: int, user_id: int
    ) -> ExamAttempt | None:
        return (
            db.query(ExamAttempt)
            .filter(
                ExamAttempt.exam_id == exam_id,
                ExamAttempt.user_id == user_id,
                ExamAttempt.completed_at.is_(None),
            )
            .order_by(ExamAttempt.id.desc())
            .first()
        )

    def count_completed_attempts(
        self, db: Session, exam_id: int, user_id: int
    ) -> int:
        return (
            db.query(ExamAttempt)
            .filter(
                ExamAttempt.exam_id == exam_id,
                ExamAttempt.user_id == user_id,
                ExamAttempt.completed_at.isnot(None),
            )
            .count()
        )

    def save_answer(self, db: Session, answer: ExamAnswer) -> ExamAnswer:
        db.add(answer)
        db.commit()
        db.refresh(answer)
        return answer

    def complete_attempt(
        self,
        db: Session,
        attempt: ExamAttempt,
        *,
        score: int,
        total: int,
        score_percent: int,
        passed: bool,
    ) -> ExamAttempt:
        attempt.score = score
        attempt.total_questions = total
        attempt.score_percent = score_percent
        attempt.passed = passed
        attempt.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(attempt)
        return attempt

    def get_option(self, db: Session, option_id: int) -> ExamOption | None:
        return db.query(ExamOption).filter(ExamOption.id == option_id).first()
