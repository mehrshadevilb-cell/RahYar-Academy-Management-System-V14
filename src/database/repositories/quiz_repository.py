from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from src.database.models.quiz import (
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizOption,
    QuizQuestion,
)


class QuizRepository:

    def create_quiz(self, db: Session, quiz: Quiz) -> Quiz:
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
        return quiz

    def get_quiz(self, db: Session, quiz_id: int) -> Quiz | None:
        return (
            db.query(Quiz)
            .options(
                joinedload(Quiz.questions).joinedload(QuizQuestion.options)
            )
            .filter(Quiz.id == quiz_id)
            .first()
        )

    def list_by_course(
        self, db: Session, online_course_id: int, *, active_only: bool = True
    ) -> list[Quiz]:
        q = db.query(Quiz).filter(Quiz.online_course_id == online_course_id)
        if active_only:
            q = q.filter(Quiz.is_active.is_(True))
        return q.order_by(Quiz.id.desc()).all()

    def add_question(self, db: Session, question: QuizQuestion) -> QuizQuestion:
        db.add(question)
        db.commit()
        db.refresh(question)
        return question

    def add_option(self, db: Session, option: QuizOption) -> QuizOption:
        db.add(option)
        db.commit()
        db.refresh(option)
        return option

    def toggle_active(self, db: Session, quiz: Quiz) -> Quiz:
        quiz.is_active = not quiz.is_active
        db.commit()
        db.refresh(quiz)
        return quiz

    def create_attempt(self, db: Session, attempt: QuizAttempt) -> QuizAttempt:
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        return attempt

    def get_attempt(self, db: Session, attempt_id: int) -> QuizAttempt | None:
        return (
            db.query(QuizAttempt)
            .options(joinedload(QuizAttempt.answers))
            .filter(QuizAttempt.id == attempt_id)
            .first()
        )

    def get_open_attempt(
        self, db: Session, quiz_id: int, user_id: int
    ) -> QuizAttempt | None:
        return (
            db.query(QuizAttempt)
            .filter(
                QuizAttempt.quiz_id == quiz_id,
                QuizAttempt.user_id == user_id,
                QuizAttempt.completed_at.is_(None),
            )
            .order_by(QuizAttempt.id.desc())
            .first()
        )

    def save_answer(self, db: Session, answer: QuizAnswer) -> QuizAnswer:
        db.add(answer)
        db.commit()
        db.refresh(answer)
        return answer

    def complete_attempt(
        self, db: Session, attempt: QuizAttempt, score: int, total: int
    ) -> QuizAttempt:
        attempt.score = score
        attempt.total_questions = total
        attempt.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(attempt)
        return attempt

    def get_option(self, db: Session, option_id: int) -> QuizOption | None:
        return db.query(QuizOption).filter(QuizOption.id == option_id).first()

    def list_attempts_for_user(
        self, db: Session, user_id: int, quiz_id: int
    ) -> list[QuizAttempt]:
        return (
            db.query(QuizAttempt)
            .filter(QuizAttempt.user_id == user_id, QuizAttempt.quiz_id == quiz_id)
            .order_by(QuizAttempt.id.desc())
            .all()
        )
