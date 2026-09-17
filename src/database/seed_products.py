"""
Seeds the four real academy products (RahYar, RahYar Pro, Theory, ArtistYar).

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

SUPABASE_COVER_BASE = "https://ejfgbiyfqjlqddbxvqhk.supabase.co/storage/v1/object/public/artistyar-media"
RAHYAR_COVER = f"{SUPABASE_COVER_BASE}/RahYar%20Package.JPEG"
RAHYAR_PRO_COVER = f"{SUPABASE_COVER_BASE}/RahYarPro%20Package.PNG"
THEORY_COVER = f"{SUPABASE_COVER_BASE}/Theory%20Package.PNG"
ARTISTYAR_COVER = f"{SUPABASE_COVER_BASE}/ArtistYar%20Package.JPG"


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
    rahyar = db.query(Course).filter(Course.title == "راه‌یار").first()
    if not rahyar:
        rahyar = Course(
            title="راه‌یار",
            description="بسته کامل آموزش تنظیم، میکس و مسترینگ راه‌یار",
            price=24_000_000,
            thumbnail=RAHYAR_COVER,
            delivery_type=ProductDeliveryType.SPOTPLAYER,
            support_group_link="https://t.me/+TqZaRkAyD1JhNzJk",
            support_username="@hi_all",
            sort_order=1,
        )
        db.add(rahyar)
        db.flush()
    else:
        rahyar.price = 24_000_000
        rahyar.description = "بسته کامل آموزش تنظیم، میکس و مسترینگ راه‌یار"
        rahyar.thumbnail = RAHYAR_COVER
        rahyar.sort_order = 1

    rahyar_courses = db.query(SpotPlayerCourse).filter(SpotPlayerCourse.product_id == rahyar.id).all()
    rahyar_main = next((item for item in rahyar_courses if item.spotplayer_course_id == "69752d413c6f2edac4b6ce71"), None)
    if not rahyar_main:
        db.add(SpotPlayerCourse(product_id=rahyar.id, spotplayer_course_id="69752d413c6f2edac4b6ce71", course_name="راه‌یار", sort_order=1))

    # ---- Product 2: RahYar Pro ----
    rahyar_pro = db.query(Course).filter(Course.title == "راه‌یار پرو").first()
    if not rahyar_pro:
        rahyar_pro = Course(
            title="راه‌یار پرو",
            description="نسخه حرفه‌ای آموزش تنظیم، میکس و مسترینگ راه‌یار",
            price=3_000_000,
            thumbnail=RAHYAR_PRO_COVER,
            delivery_type=ProductDeliveryType.SPOTPLAYER,
            sort_order=2,
        )
        db.add(rahyar_pro)
        db.flush()
    else:
        rahyar_pro.price = 3_000_000
        rahyar_pro.description = "نسخه حرفه‌ای آموزش تنظیم، میکس و مسترینگ راه‌یار"
        rahyar_pro.thumbnail = RAHYAR_PRO_COVER
        rahyar_pro.sort_order = 2

    pro_course = db.query(SpotPlayerCourse).filter(SpotPlayerCourse.spotplayer_course_id == "697475017e50673ccf9bd7aa").first()
    if pro_course:
        pro_course.product_id = rahyar_pro.id
        pro_course.course_name = "راه‌یار پرو"
        pro_course.sort_order = 1
    else:
        db.add(SpotPlayerCourse(product_id=rahyar_pro.id, spotplayer_course_id="697475017e50673ccf9bd7aa", course_name="راه‌یار پرو", sort_order=1))

    # ---- Product 2: Theory ----
    if not product_exists("تئوری موسیقی"):

        theory = Course(
            title="تئوری موسیقی",
            description="آموزش تئوری موسیقی",
            price=380_000,
            thumbnail=THEORY_COVER,
            delivery_type=ProductDeliveryType.SPOTPLAYER,
            sort_order=3,
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
    else:
        theory = db.query(Course).filter(Course.title == "تئوری موسیقی").first()
        theory.thumbnail = THEORY_COVER

    # ---- Product 3: ArtistYar ----
    if not product_exists("آرتیست‌یار"):

        artistyar = Course(
            title="آرتیست‌یار",
            description="دسترسی به کانال‌های ضبط، میکس و فایل آرتیست‌یار",
            price=1_500_000,
            thumbnail=ARTISTYAR_COVER,
            delivery_type=ProductDeliveryType.TELEGRAM,
            sort_order=4,
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
    else:
        artistyar = db.query(Course).filter(Course.title == "آرتیست‌یار").first()
        artistyar.thumbnail = ARTISTYAR_COVER

    db.commit()
    db.close()


if __name__ == "__main__":
    seed_default_products()
