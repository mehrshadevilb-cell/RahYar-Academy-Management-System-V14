from sqlalchemy.orm import Session

from src.database.models.class_inquiry import ClassInquiry, ClassInquiryStatus
from src.database.models.online_course import OnlineCourse
from src.database.models.user import User
from src.services.canonical_identity_service import CanonicalIdentityService
from src.services.web_order_service import WebOrderError, WebOrderService


class ClassInquiryService:
    """Single persistence path used by HTML, JSON, and future bot admin flows."""

    def __init__(self) -> None:
        self.orders = WebOrderService()
        self.identity = CanonicalIdentityService()

    def create_or_reuse(
        self,
        db: Session,
        *,
        course: OnlineCourse,
        full_name: str,
        phone: str,
        message: str | None = None,
        source: str = "website",
        requested_plan: str | None = None,
    ) -> tuple[User, ClassInquiry]:
        user = self.orders.ensure_user(db, full_name=full_name, phone=phone)
        inquiry = (
            db.query(ClassInquiry)
            .filter(
                ClassInquiry.user_id == user.id,
                ClassInquiry.online_course_id == course.id,
                ClassInquiry.status.in_((ClassInquiryStatus.PENDING, ClassInquiryStatus.REVIEWING)),
            )
            .order_by(ClassInquiry.id.desc())
            .first()
        )
        if inquiry:
            if message:
                inquiry.message = message[:2000]
            if requested_plan:
                inquiry.requested_plan = requested_plan[:30]
            db.commit()
            db.refresh(inquiry)
            return user, inquiry

        inquiry = ClassInquiry(
            user_id=user.id,
            online_course_id=course.id,
            source=source[:30],
            requested_plan=requested_plan[:30] if requested_plan else None,
            message=message[:2000] if message else None,
            status=ClassInquiryStatus.PENDING,
        )
        db.add(inquiry)
        db.commit()
        db.refresh(inquiry)
        return user, inquiry
