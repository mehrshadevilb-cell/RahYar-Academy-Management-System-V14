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

RETRY_DELAYS_SECONDS = [1, 3]  # exponential-ish backoff, 2 retries after the first try


class LicenseService:
    """
    Issues SpotPlayer licenses for approved payments.

    A license is never created before this is explicitly called by the
    payment-approval flow, and it never charges/re-charges the student -
    it only talks to SpotPlayer and records the result.
    """

    def __init__(self):
        self.repository = LicenseRepository()
        self.settings = get_settings()

    async def issue_license(
        self,
        db: Session,
        user_id: int,
        user_full_name: str,
        user_phone: str | None,
        product: Course,
        payment_id: int | None,
    ) -> License:

        # Never create a duplicate active license for the same product
        existing = self.repository.get_by_user_and_product(
            db, user_id, product.id
        )

        if existing and existing.status == "active":
            return existing

        if not self.settings.SPOTPLAYER_API_KEY:

            return self.repository.create(
                db,
                License(
                    user_id=user_id,
                    product_id=product.id,
                    payment_id=payment_id,
                    status="failed",
                    error_message="SPOTPLAYER_API_KEY در .env تنظیم نشده است.",
                ),
            )

        course_ids = [
            sp_course.spotplayer_course_id
            for sp_course in product.spotplayer_courses
            if sp_course.enabled
        ]

        if not course_ids:

            return self.repository.create(
                db,
                License(
                    user_id=user_id,
                    product_id=product.id,
                    payment_id=payment_id,
                    status="failed",
                    error_message="هیچ کد دوره SpotPlayer فعالی برای این محصول ثبت نشده است.",
                ),
            )

        client = SpotPlayerClient(api_key=self.settings.SPOTPLAYER_API_KEY)

        watermark_text = user_phone or user_full_name

        last_error = None

        attempts = len(RETRY_DELAYS_SECONDS) + 1

        for attempt in range(attempts):

            try:

                result = await client.create_license(
                    name=user_full_name,
                    course_ids=course_ids,
                    watermark_text=watermark_text,
                )

                return self.repository.create(
                    db,
                    License(
                        user_id=user_id,
                        product_id=product.id,
                        payment_id=payment_id,
                        spotplayer_license_id=result["_id"],
                        license_key=result["key"],
                        license_url=result["url"],
                        status="active",
                    ),
                )

            except SpotPlayerError as exc:

                last_error = str(exc)

                logger.error(
                    "SpotPlayer license creation failed (attempt %s/%s) "
                    "for user_id=%s product_id=%s: %s",
                    attempt + 1, attempts, user_id, product.id, last_error,
                )

                if attempt < len(RETRY_DELAYS_SECONDS):
                    await asyncio.sleep(RETRY_DELAYS_SECONDS[attempt])

        # All attempts failed - never lose the transaction, save it as failed
        # so the owner can retry manually once the issue is resolved.
        return self.repository.create(
            db,
            License(
                user_id=user_id,
                product_id=product.id,
                payment_id=payment_id,
                status="failed",
                error_message=last_error,
            ),
        )

    async def retry_license(
        self,
        db: Session,
        failed_license: License,
        user_full_name: str,
        user_phone: str | None,
        product: Course,
    ) -> License:

        return await self.issue_license(
            db=db,
            user_id=failed_license.user_id,
            user_full_name=user_full_name,
            user_phone=user_phone,
            product=product,
            payment_id=failed_license.payment_id,
        )
