from sqlalchemy.orm import Session

from src.database.models.user import User
from src.database.models.enrollment import Enrollment
from src.database.models.license import License


class LegacyImportService:
    """
    Handles linking pre-existing academy records (imported from the old
    SpotPlayer panel before the bot existed) to a student's real Telegram
    account the first time they register.

    A legacy/imported student is represented as a `User` row that has a
    `phone` but no `TelegramAccount` (they were created by the import
    script, not through /start). When a *real* Telegram user registers
    with that same phone number, their purchase history must be moved
    onto the live account rather than staying stranded on the orphan
    placeholder row - otherwise the student would see an empty "my
    courses" list despite having paid for real products in the past.
    """

    def find_unlinked_by_phone(self, db: Session, phone: str) -> User | None:
        """Returns a legacy placeholder user with this phone, if any -
        i.e. a user with no TelegramAccount attached yet."""

        candidate = (
            db.query(User)
            .filter(User.phone == phone)
            .first()
        )

        if candidate and candidate.telegram_account is None:
            return candidate

        return None

    def merge_into_live_user(
        self,
        db: Session,
        legacy_user: User,
        live_user: User,
    ) -> None:
        """Moves every record owned by `legacy_user` onto `live_user`,
        then removes the now-empty placeholder row. Safe to call only
        when `legacy_user.telegram_account is None` (caller's
        responsibility - this never touches an account someone is
        actually using)."""

        if legacy_user.id == live_user.id:
            return

        live_course_ids = {
            e.course_id
            for e in db.query(Enrollment).filter(
                Enrollment.user_id == live_user.id
            )
        }

        for enrollment in db.query(Enrollment).filter(
            Enrollment.user_id == legacy_user.id
        ):
            # Guard against the (unlikely) unique(user_id, course_id)
            # collision if the live account already has this course.
            if enrollment.course_id in live_course_ids:
                db.delete(enrollment)
            else:
                enrollment.user_id = live_user.id

        db.query(License).filter(
            License.user_id == legacy_user.id
        ).update({"user_id": live_user.id})

        db.delete(legacy_user)

        db.commit()
