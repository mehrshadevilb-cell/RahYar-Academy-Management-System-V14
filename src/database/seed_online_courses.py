"""
Seeds the two online-class price tiers described in the academy's
pricing sheet. Two values were not explicitly given and are filled with
a reasonable default (clearly marked) - the owner can correct these
from a future online-classes admin screen:

  - "تنظیم / میکس / مسترینگ": duration was given as a 90-180 minute
    range, not a single number -> defaulted to 135 (the midpoint).
  - "تئوری / هارمونی / گوش‌نوازی": no term (12-session) price was given
    -> left as None until the owner sets one.
"""

from src.core.logging.logger import get_logger
from src.database.session import SessionLocal
from src.database.models.online_course import OnlineCourse

logger = get_logger("rahyar.seed.online_courses")


def seed_default_online_courses() -> None:
    db = SessionLocal()
    try:
        def exists(name: str) -> bool:
            return (
                db.query(OnlineCourse)
                .filter(OnlineCourse.name == name)
                .first()
                is not None
            )

        if not exists("تنظیم / میکس / مسترینگ"):
            db.add(
                OnlineCourse(
                    name="تنظیم / میکس / مسترینگ",
                    duration_minutes=135,  # assumed midpoint of the given 90-180 range
                    monthly_price=11_500_000,
                    term_price=35_000_000,
                    monthly_sessions=4,
                    term_sessions=12,
                )
            )
            logger.info("Online course added: تنظیم / میکس / مسترینگ")

        if not exists("تئوری / هارمونی / گوش‌نوازی"):
            db.add(
                OnlineCourse(
                    name="تئوری / هارمونی / گوش‌نوازی",
                    duration_minutes=20,
                    monthly_price=2_000_000,
                    term_price=None,  # not specified yet
                    monthly_sessions=4,
                    term_sessions=12,
                )
            )
            logger.info("Online course added: تئوری / هارمونی / گوش‌نوازی")

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("seed_default_online_courses failed; continuing startup")
    finally:
        db.close()


if __name__ == "__main__":
    seed_default_online_courses()
