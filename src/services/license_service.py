import asyncio
import logging

from sqlalchemy.orm import Session

from src.database.models.license import License
from src.database.models.course import Course
from src.database.repositories.license_repository import LicenseRepository
from src.integrations.spotplayer.client import SpotPlayerClient
from src.integrations.spotplayer.exceptions import SpotPlayerError
from src.core.config.settings import get_settings


logger = logging.getLogger("spotplayer")

RETRY_DELAYS_SECONDS = [1, 3]


class LicenseService:
    """
    Issues SpotPlayer licenses for approved payments.

    When SPOTPLAYER_TEST_MODE=true (or test=True is passed), the SpotPlayer
    API receives "test": true so no paid license quota is consumed.
    """

    def __init__(self):
        self.repository = LicenseRepository()
        self.settings = get_settings()

    def _use_test_mode(self, test: bool | None) -> bool:
        if test is not None:
            return bool(test)
        return bool(self.settings.SPOTPLAYER_TEST_MODE)

    async def issue_license(
        self,
        db: Session,
        user_id: int,
        user_full_name: str,
        user_phone: str | None,
        product: Course,
        payment_id: int | None,
        *,
        test: bool | None = None,
        force_new: bool = False,
    ) -> License:
        existing = self.repository.get_by_user_and_product(
            db, user_id, product.id
        )

        if existing and existing.status == "active" and not force_new:
            return existing

        license_record = None if force_new else existing
        use_test = self._use_test_mode(test)

        def save_result(**values) -> License:
            nonlocal license_record
            if license_record is None:
                license_record = License(
                    user_id=user_id,
                    product_id=product.id,
                    payment_id=payment_id,
                )
                db.add(license_record)

            for key, value in values.items():
                setattr(license_record, key, value)

            if payment_id is not None:
                license_record.payment_id = payment_id

            db.commit()
            db.refresh(license_record)
            return license_record

        if not self.settings.SPOTPLAYER_API_KEY:
            return save_result(
                status="failed",
                error_message="SPOTPLAYER_API_KEY در .env تنظیم نشده است.",
            )

        course_ids = [
            sp_course.spotplayer_course_id
            for sp_course in product.spotplayer_courses
            if sp_course.enabled
        ]

        if not course_ids:
            return save_result(
                status="failed",
                error_message="هیچ کد دوره SpotPlayer فعالی برای این محصول ثبت نشده است.",
            )

        client = SpotPlayerClient(api_key=self.settings.SPOTPLAYER_API_KEY)
        watermark_text = user_phone or user_full_name
        display_name = user_full_name
        if use_test and not display_name.startswith("[TEST]"):
            display_name = f"[TEST] {display_name}"[:100]

        last_error = None
        attempts = len(RETRY_DELAYS_SECONDS) + 1

        for attempt in range(attempts):
            try:
                result = await client.create_license(
                    name=display_name,
                    course_ids=course_ids,
                    watermark_text=watermark_text,
                    test=use_test,
                )

                logger.info(
                    "SpotPlayer license created user_id=%s product_id=%s test=%s id=%s",
                    user_id,
                    product.id,
                    use_test,
                    result.get("_id"),
                )

                # Mark test licenses in error_message only as a soft flag when active
                # so admins can tell them apart without a schema migration.
                note = "TEST_LICENSE" if use_test else None
                return save_result(
                    status="active",
                    spotplayer_license_id=result["_id"],
                    license_key=result["key"],
                    license_url=result.get("url"),
                    error_message=note,
                )

            except SpotPlayerError as exc:
                last_error = str(exc)
                logger.error(
                    "SpotPlayer license creation failed (attempt %s/%s) "
                    "for user_id=%s product_id=%s test=%s: %s",
                    attempt + 1,
                    attempts,
                    user_id,
                    product.id,
                    use_test,
                    last_error,
                )

                if attempt < len(RETRY_DELAYS_SECONDS):
                    await asyncio.sleep(RETRY_DELAYS_SECONDS[attempt])

        return save_result(
            status="failed",
            error_message=last_error,
        )

    async def retry_license(
        self,
        db: Session,
        failed_license: License,
        user_full_name: str,
        user_phone: str | None,
        product: Course,
        *,
        test: bool | None = None,
    ) -> License:
        return await self.issue_license(
            db=db,
            user_id=failed_license.user_id,
            user_full_name=user_full_name,
            user_phone=user_phone,
            product=product,
            payment_id=failed_license.payment_id,
            test=test,
        )

    async def issue_test_license(
        self,
        db: Session,
        user_id: int,
        user_full_name: str,
        user_phone: str | None,
        product: Course,
    ) -> License:
        """Always call SpotPlayer with test=true (no paid quota)."""
        return await self.issue_license(
            db=db,
            user_id=user_id,
            user_full_name=user_full_name,
            user_phone=user_phone,
            product=product,
            payment_id=None,
            test=True,
            force_new=True,
        )
