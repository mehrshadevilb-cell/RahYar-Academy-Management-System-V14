"""
Seeds the academy products (RahYar, RahYar Pro, Theory, RahYar Complete, ArtistYar).

Product/course/channel data here is structural configuration (not a secret like
an API key or card number), so it is safe to seed directly. Everything seeded
here is meant to become editable from the future in-Telegram admin panel.

Safe to run multiple times: existing products (matched by title) are updated
without creating duplicate products or SpotPlayer course mappings.
"""

from src.core.logging.logger import get_logger
from src.database.session import SessionLocal
from src.database.models.course import Course, ProductDeliveryType
from src.database.models.spotplayer_course import SpotPlayerCourse
from src.database.models.telegram_channel import TelegramChannel

logger = get_logger("rahyar.seed.products")

SUPABASE_COVER_BASE = "https://ejfgbiyfqjlqddbxvqhk.supabase.co/storage/v1/object/public/artistyar-media"
RAHYAR_COVER = f"{SUPABASE_COVER_BASE}/RahYar%20Package.JPEG"
RAHYAR_PRO_COVER = f"{SUPABASE_COVER_BASE}/RahYarPro%20Package.PNG"
THEORY_COVER = f"{SUPABASE_COVER_BASE}/Theory%20Package.PNG"
ARTISTYAR_COVER = f"{SUPABASE_COVER_BASE}/ArtistYar%20Package.JPG"

RAHYAR_SPOTPLAYER_ID = "69752d413c6f2edac4b6ce71"
RAHYAR_PRO_SPOTPLAYER_ID = "697475017e50673ccf9bd7aa"
THEORY_SPOTPLAYER_ID = "69752bbf7e50673ccf9cb9a5"


def seed_default_products() -> None:
    db = SessionLocal()
    try:
        def ensure_spotplayer_mapping(product: Course, spotplayer_id: str, course_name: str, sort_order: int):
            mapping = (
                db.query(SpotPlayerCourse)
                .filter(
                    SpotPlayerCourse.product_id == product.id,
                    SpotPlayerCourse.spotplayer_course_id == spotplayer_id,
                )
                .first()
            )
            if mapping is None:
                db.add(
                    SpotPlayerCourse(
                        product_id=product.id,
                        spotplayer_course_id=spotplayer_id,
                        course_name=course_name,
                        sort_order=sort_order,
                    )
                )
            else:
                mapping.course_name = course_name
                mapping.sort_order = sort_order
                mapping.enabled = True

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
        ensure_spotplayer_mapping(rahyar, RAHYAR_SPOTPLAYER_ID, "راه‌یار", 1)

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
        ensure_spotplayer_mapping(rahyar_pro, RAHYAR_PRO_SPOTPLAYER_ID, "راه‌یار پرو", 1)

        # ---- Product 3: Theory ----
        theory = db.query(Course).filter(Course.title == "تئوری موسیقی").first()
        if not theory:
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
        else:
            theory.thumbnail = THEORY_COVER
            theory.sort_order = 3
        ensure_spotplayer_mapping(theory, THEORY_SPOTPLAYER_ID, "تئوری موسیقی", 1)

        # ---- Product 4: RahYar Complete Bundle ----
        complete = db.query(Course).filter(Course.title == "پکیج کامل راه‌یار").first()
        if not complete:
            complete = Course(
                title="پکیج کامل راه‌یار",
                description="ترکیب کامل سه پکیج راه‌یار، راه‌یار پرو و تئوری موسیقی",
                price=25_000_000,
                thumbnail=RAHYAR_COVER,
                delivery_type=ProductDeliveryType.SPOTPLAYER,
                support_group_link="https://t.me/+TqZaRkAyD1JhNzJk",
                support_username="@hi_all",
                sort_order=4,
            )
            db.add(complete)
            db.flush()
        else:
            complete.price = 25_000_000
            complete.description = "ترکیب کامل سه پکیج راه‌یار، راه‌یار پرو و تئوری موسیقی"
            complete.thumbnail = RAHYAR_COVER
            complete.delivery_type = ProductDeliveryType.SPOTPLAYER
            complete.support_group_link = "https://t.me/+TqZaRkAyD1JhNzJk"
            complete.support_username = "@hi_all"
            complete.sort_order = 4

        ensure_spotplayer_mapping(complete, RAHYAR_SPOTPLAYER_ID, "راه‌یار", 1)
        ensure_spotplayer_mapping(complete, RAHYAR_PRO_SPOTPLAYER_ID, "راه‌یار پرو", 2)
        ensure_spotplayer_mapping(complete, THEORY_SPOTPLAYER_ID, "تئوری موسیقی", 3)

        # ---- Product 5: ArtistYar ----
        artistyar = db.query(Course).filter(Course.title == "آرتیست‌یار").first()
        if not artistyar:
            artistyar = Course(
                title="آرتیست‌یار",
                description="دسترسی به کانال‌های ضبط، میکس و فایل آرتیست‌یار",
                price=1_500_000,
                thumbnail=ARTISTYAR_COVER,
                delivery_type=ProductDeliveryType.TELEGRAM,
                sort_order=5,
            )
            db.add(artistyar)
            db.flush()
        else:
            artistyar.thumbnail = ARTISTYAR_COVER
            artistyar.sort_order = 5

        existing_channels = {
            channel.name: channel
            for channel in db.query(TelegramChannel).filter(TelegramChannel.product_id == artistyar.id).all()
        }
        for name, chat_id, sort_order in [
            ("Record", "-1002682858670", 1),
            ("Edit", "-1002317658121", 2),
            ("Files", "-1002505287920", 3),
        ]:
            channel = existing_channels.get(name)
            if channel is None:
                db.add(TelegramChannel(product_id=artistyar.id, name=name, chat_id=chat_id, sort_order=sort_order))
            else:
                channel.chat_id = chat_id
                channel.sort_order = sort_order

        db.commit()
        logger.info("seed_default_products completed")
    except Exception:
        db.rollback()
        logger.exception("seed_default_products failed; continuing startup")
    finally:
        db.close()


if __name__ == "__main__":
    seed_default_products()
