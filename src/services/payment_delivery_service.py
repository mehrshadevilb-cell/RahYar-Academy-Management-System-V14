"""Shared approved-payment delivery orchestration.

The Telegram owner handler and the web admin API both approve the same Payment
records.  This service is the only place that turns an approved payment into
an enrollment and the configured delivery (SpotPlayer license or Telegram
channel invite links).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aiogram import Bot
from sqlalchemy.orm import Session

from src.database.models.course import Course, ProductDeliveryType
from src.database.models.license import License
from src.database.models.payment import Payment
from src.database.models.user import User
from src.database.repositories.telegram_repository import TelegramRepository
from src.services.artistyar_service import ArtistYarService
from src.services.enrollment_service import EnrollmentService
from src.services.license_service import LicenseService
from src.services.payment_service import PaymentService
from src.services.referral_service import ReferralService

WINDOWS_DOWNLOAD_URL = "https://app.spotplayer.ir/assets/bin/spotplayer/setup.exe"
MAC_DOWNLOAD_URL = "https://app.spotplayer.ir/assets/bin/spotplayer/setup.dmg"


@dataclass(frozen=True)
class ChannelDelivery:
    """One ArtistYar channel delivery attempt."""

    channel_name: str
    invite_link: str | None
    error: str | None


@dataclass
class PaymentDeliveryResult:
    """Serializable outcome of approving and delivering one payment."""

    payment: Payment
    user: User
    course: Course
    enrollment_id: int
    license: License | None = None
    channel_deliveries: list[ChannelDelivery] = field(default_factory=list)
    student_notified: bool = False
    warnings: list[str] = field(default_factory=list)
    referral_rewarded: Any | None = None

    @property
    def delivery_status(self) -> str:
        if self.license is not None:
            return self.license.status
        if self.channel_deliveries:
            return "active" if all(item.invite_link for item in self.channel_deliveries) else "partial"
        return "enrolled"

    def public_summary(self) -> dict[str, Any]:
        """Return safe operational detail for the authenticated web admin."""
        return {
            "delivery_type": self.course.delivery_type.value,
            "status": self.delivery_status,
            "license_id": self.license.id if self.license else None,
            "license_status": self.license.status if self.license else None,
            "license_key": self.license.license_key if self.license and self.license.status == "active" else None,
            "license_url": self.license.license_url if self.license and self.license.status == "active" else None,
            "invite_links": [
                {
                    "channel_name": item.channel_name,
                    "invite_link": item.invite_link,
                    "error": item.error,
                }
                for item in self.channel_deliveries
            ],
            "student_notified": self.student_notified,
            "warnings": self.warnings,
        }


class PaymentDeliveryService:
    """Approve payments and grant course access through one idempotent path."""

    def __init__(
        self,
        *,
        payment_service: PaymentService | None = None,
        enrollment_service: EnrollmentService | None = None,
        license_service: LicenseService | None = None,
        artistyar_service: ArtistYarService | None = None,
        referral_service: ReferralService | None = None,
        telegram_repository: TelegramRepository | None = None,
    ) -> None:
        self.payment_service = payment_service or PaymentService()
        self.enrollment_service = enrollment_service or EnrollmentService()
        self.license_service = license_service or LicenseService()
        self.artistyar_service = artistyar_service or ArtistYarService()
        self.referral_service = referral_service or ReferralService()
        self.telegram_repository = telegram_repository or TelegramRepository()

    async def approve_and_deliver(
        self,
        db: Session,
        *,
        payment_id: int,
        admin_telegram_id: int,
        bot: Bot | None = None,
        notify_student: bool = True,
    ) -> PaymentDeliveryResult | None:
        """Approve a pending payment, create enrollment, and run its delivery.

        ``PaymentService.approve`` locks and makes the approval idempotent;
        enrollment and downstream providers are also idempotent, so a retry
        after a timeout cannot create duplicate access records.
        """
        payment = self.payment_service.approve(db, payment_id, admin_telegram_id)
        if payment is None:
            return None
        return await self.deliver_approved_payment(
            db,
            payment=payment,
            bot=bot,
            notify_student=notify_student,
            reward_referral=True,
        )

    async def deliver_approved_payment(
        self,
        db: Session,
        *,
        payment: Payment,
        bot: Bot | None = None,
        notify_student: bool = True,
        reward_referral: bool = True,
    ) -> PaymentDeliveryResult:
        """Complete delivery for an already-approved payment.

        This method is deliberately safe to call again after a partial
        external-provider failure: existing enrollment, license, and invite
        link records are reused by the underlying services.
        """
        if payment.status != "approved":
            raise ValueError("payment_must_be_approved")

        course = db.query(Course).filter(Course.id == payment.course_id).first()
        user = db.query(User).filter(User.id == payment.user_id).first()
        if course is None or user is None:
            raise ValueError("payment_delivery_entities_missing")

        enrollment = self.enrollment_service.create_enrollment(
            db=db,
            user_id=user.id,
            course_id=course.id,
        )
        result = PaymentDeliveryResult(
            payment=payment,
            user=user,
            course=course,
            enrollment_id=enrollment.id,
        )
        if reward_referral:
            result.referral_rewarded = self.referral_service.reward_referrer_if_pending(db, user.id)

        telegram_account = self.telegram_repository.get_by_user_id(db, user.id)

        if course.delivery_type == ProductDeliveryType.SPOTPLAYER:
            license_ = await self.license_service.issue_license(
                db=db,
                user_id=user.id,
                user_full_name=user.full_name,
                user_phone=user.phone,
                product=course,
                payment_id=payment.id,
            )
            result.license = license_
            if license_.status == "active":
                if notify_student and bot and telegram_account:
                    await self._send_spotplayer_license(bot, telegram_account.telegram_id, course, license_)
                    result.student_notified = True
                elif notify_student:
                    result.warnings.append("student_telegram_not_linked")
            else:
                result.warnings.append("spotplayer_license_failed")

        elif course.delivery_type == ProductDeliveryType.TELEGRAM:
            if bot is None:
                result.warnings.append("telegram_delivery_bot_unavailable")
                return result

            raw_deliveries = await self.artistyar_service.deliver_channels(
                bot=bot,
                db=db,
                user_id=user.id,
                product=course,
            )
            result.channel_deliveries = [
                ChannelDelivery(
                    channel_name=str(item.get("channel_name") or "کانال"),
                    invite_link=item.get("invite_link"),
                    error=item.get("error"),
                )
                for item in raw_deliveries
            ]
            successful = [item for item in result.channel_deliveries if item.invite_link]
            failed = [item for item in result.channel_deliveries if not item.invite_link]
            if notify_student and successful and telegram_account:
                await self._send_channel_links(bot, telegram_account.telegram_id, successful)
                result.student_notified = True
            elif notify_student and successful:
                result.warnings.append("student_telegram_not_linked")
            if failed:
                result.warnings.append("telegram_invite_link_failed")

        return result

    @staticmethod
    async def _send_spotplayer_license(
        bot: Bot,
        telegram_id: str,
        course: Course,
        license_: License,
    ) -> None:
        support_line = (
            f"\n\n🎧 گروه پشتیبانی:\n{course.support_group_link}"
            if course.support_group_link
            else ""
        )
        await bot.send_message(
            chat_id=telegram_id,
            text=(
                "🎓 لایسنس شما آماده شد!\n\n"
                f"🔑 کلید لایسنس:\n{license_.license_key}\n\n"
                f"💻 دانلود ویندوز:\n{WINDOWS_DOWNLOAD_URL}\n\n"
                f"🍎 دانلود مک:\n{MAC_DOWNLOAD_URL}\n\n"
                "پس از نصب نرم‌افزار SpotPlayer، کلید لایسنس بالا را وارد کنید."
                f"{support_line}"
            ),
        )

    @staticmethod
    async def _send_channel_links(
        bot: Bot,
        telegram_id: str,
        deliveries: list[ChannelDelivery],
    ) -> None:
        links_text = "\n".join(
            f"📢 {item.channel_name}:\n{item.invite_link}"
            for item in deliveries
            if item.invite_link
        )
        await bot.send_message(
            chat_id=telegram_id,
            text=(
                "✅ لینک‌های دسترسی شما:\n\n"
                f"{links_text}\n\n"
                "⚠️ این لینک‌ها فقط یک‌بار قابل استفاده هستند."
            ),
        )
