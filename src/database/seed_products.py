"""
Seeds the three real academy products (RahYar, Theory, ArtistYar).

Product/course/channel data here is structural configuration (not a
secret like an API key or card number), so it is safe to seed directly.
Everything seeded here is meant to become editable from the future
in-Telegram admin panel - this script only sets the initial values.

Safe to run multiple times: existing products (matched by title) are
left untouched.
"""

from src.database.session import SessionLocal
from src.database.models.course import Course, ProductDeliveryType
from src.database.models.spotplayer_course import SpotPlayerCourse
from src.database.models.telegram_channel import TelegramChannel


def seed_default_products():

    db = SessionLocal()

    def product_exists(title: str) -> bool:
        return (
            db.query(Course)
            .filter(Course.title == title)
            .first()
            is not None
        )

    # ---- Product 1: RahYar ----
    if not product_exists("راه‌یار"):

        rahyar = Course(
            title="راه‌یار",
            description="بسته کامل آموزش تنظیم، میکس و مسترینگ راه‌یار",
            price=15_000_000,
            delivery_type=ProductDeliveryType.SPOTPLAYER,
            support_group_link="https://t.me/+TqZaRkAyD1JhNzJk",
            support_username="@hi_all",
            sort_order=1,
        )

        db.add(rahyar)
        db.flush()

        db.add_all([
            SpotPlayerCourse(
                product_id=rahyar.id,
                spotplayer_course_id="69752d413c6f2edac4b6ce71",
                course_name="راه‌یار - بخش اول",
                sort_order=1,
            ),
            SpotPlayerCourse(
                product_id=rahyar.id,
                spotplayer_course_id="697475017e50673ccf9bd7aa",
                course_name="راه‌یار - بخش دوم",
                sort_order=2,
            ),
        ])

        print("Product added: راه‌یار")

    # ---- Product 2: Theory ----
    if not product_exists("تئوری موسیقی"):

        theory = Course(
            title="تئوری موسیقی",
            description="آموزش تئوری موسیقی",
            price=380_000,
            delivery_type=ProductDeliveryType.SPOTPLAYER,
            sort_order=2,
        )

        db.add(theory)
        db.flush()

        db.add(
            SpotPlayerCourse(
                product_id=theory.id,
                spotplayer_course_id="69752bbf7e50673ccf9cb9a5",
                course_name="تئوری موسیقی",
                sort_order=1,
            )
        )

        print("Product added: تئوری موسیقی")

    # ---- Product 3: ArtistYar ----
    if not product_exists("آرتیست‌یار"):

        artistyar = Course(
            title="آرتیست‌یار",
            description="دسترسی به کانال‌های ضبط، میکس و فایل آرتیست‌یار",
            price=1_500_000,
            delivery_type=ProductDeliveryType.TELEGRAM,
            sort_order=3,
        )

        db.add(artistyar)
        db.flush()

        db.add_all([
            TelegramChannel(
                product_id=artistyar.id,
                name="Record",
                chat_id="-1002682858670",
                sort_order=1,
            ),
            TelegramChannel(
                product_id=artistyar.id,
                name="Edit",
                chat_id="-1002317658121",
                sort_order=2,
            ),
            TelegramChannel(
                product_id=artistyar.id,
                name="Files",
                chat_id="-1002505287920",
                sort_order=3,
            ),
        ])

        print("Product added: آرتیست‌یار")

    db.commit()
    db.close()


if __name__ == "__main__":
    seed_default_products()
