"""JSON API for the ArtistYar Next.js website.

Shares the same PostgreSQL database and payment rules as the Telegram bot:
website can create pending orders/inquiries; access is never granted until
the owner approves in Telegram.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from aiogram.types import BufferedInputFile
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from src.bot.bot import bot
from src.core.config.settings import get_settings
from src.core.logging.logger import get_logger
from src.services.web_order_service import WebOrderError, WebOrderService
from src.services.class_inquiry_service import ClassInquiryService
from src.bot.keyboards.payment_review_keyboard import payment_review_keyboard
from src.database.models.free_lesson import FreeLesson
from src.database.models.student_profile import StudentProfile
from src.database.models.telegram_account import TelegramAccount
from src.database.models.user import User, UserRole
from src.database.models.admin_log import AdminLog
from src.database.models.online_course import OnlineCourse
from src.database.models.online_enrollment import EnrollmentStatus, OnlineEnrollment
from src.database.models.site_event import SiteEvent
from src.database.models.reservation import Reservation, ReservationStatus
from src.services.reservation_service import ReservationService
from src.web.deps import get_db

logger = get_logger("web.api_v1")
settings = get_settings()
order_service = WebOrderService()
class_inquiry_service = ClassInquiryService()
reservation_service = ReservationService()

router = APIRouter(prefix="/api/v1", tags=["artistyar-api"])


class ProductOut(BaseModel):
    id: int
    title: str
    description: str | None = None
    price: int
    is_active: bool = True
    delivery_type: str = "spotplayer"
    thumbnail: str | None = None


class ClassOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    is_active: bool = True


class OrderIn(BaseModel):
    product_id: int
    full_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=10, max_length=20)
    note: str | None = Field(default=None, max_length=500)


class InquiryIn(BaseModel):
    course_id: int
    full_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=10, max_length=20)
    message: str | None = Field(default=None, max_length=1000)


class AnalyticsEventIn(BaseModel):
    event_type: str = Field(default="page_view", pattern="^[a-z0-9_.-]{1,40}$")
    path: str = Field(default="/", min_length=1, max_length=240)
    metadata: dict[str, str] | None = None


class OrderStatusOut(BaseModel):
    payment_id: int
    product_title: str
    amount: int
    status: str
    created_at: str


class LicenseOut(BaseModel):
    id: int
    product_title: str
    status: str
    license_key: str | None = None
    license_url: str | None = None
    payment_id: int | None = None
    created_at: str


class ChapterIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    time: int = Field(ge=0)


class FreeLessonIn(BaseModel):
    slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    duration_label: str = Field(default="", max_length=40)
    video_url: str | None = Field(default=None, max_length=500)
    thumbnail_url: str | None = Field(default=None, max_length=500)
    chapters: list[ChapterIn] = Field(default_factory=list, max_length=30)
    sort_order: int = Field(default=0, ge=0, le=10000)
    is_active: bool = True


class FreeLessonOut(FreeLessonIn):
    id: int
    created_at: str
    updated_at: str


class StudentAdminOut(BaseModel):
    id: int
    full_name: str
    phone: str | None = None
    email: str | None = None
    bio: str | None = None
    level: str | None = None
    experience_years: int = 0
    telegram_id: str | None = None
    telegram_username: str | None = None
    created_at: str


class StudentAdminUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=100)
    bio: str | None = Field(default=None, max_length=4000)
    level: str | None = Field(default=None, max_length=50)
    experience_years: int = Field(default=0, ge=0, le=80)


class ReservationReviewIn(BaseModel):
    action: str = Field(pattern="^(confirm|reject)$")
    notes: str | None = Field(default=None, max_length=500)


def _student_out(user: User, profile: StudentProfile | None, account: TelegramAccount | None) -> StudentAdminOut:
    return StudentAdminOut(
        id=user.id,
        full_name=user.full_name,
        phone=user.phone,
        email=user.email,
        bio=profile.bio if profile else None,
        level=profile.level if profile else None,
        experience_years=int(profile.experience_years if profile else 0),
        telegram_id=account.telegram_id if account else None,
        telegram_username=account.username if account else None,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


def _lesson_out(lesson: FreeLesson) -> FreeLessonOut:
    return FreeLessonOut(
        id=lesson.id,
        slug=lesson.slug,
        title=lesson.title,
        description=lesson.description,
        duration_label=lesson.duration_label or "",
        video_url=lesson.video_url,
        thumbnail_url=lesson.thumbnail_url,
        chapters=lesson.chapters or [],
        sort_order=lesson.sort_order,
        is_active=lesson.is_active,
        created_at=lesson.created_at.isoformat() if lesson.created_at else "",
        updated_at=lesson.updated_at.isoformat() if lesson.updated_at else "",
    )


def require_web_admin(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")):
    expected = (settings.WEB_ADMIN_API_KEY or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="web_admin_api_key_not_configured")
    if not x_admin_key or not secrets.compare_digest(x_admin_key, expected):
        raise HTTPException(status_code=403, detail="admin_access_denied")


@router.post("/analytics/events", status_code=202)
async def collect_analytics_event(body: AnalyticsEventIn, request: Request, db: Session = Depends(get_db)):
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    client = forwarded or (request.client.host if request.client else "unknown")
    user_agent = request.headers.get("user-agent", "")[:240]
    secret = settings.ANALYTICS_HASH_SECRET or settings.SECRET_KEY or "artistyar-analytics"
    visitor_hash = hashlib.sha256(f"{secret}:{client}:{user_agent}".encode()).hexdigest()
    db.add(SiteEvent(event_type=body.event_type, path=body.path, visitor_hash=visitor_hash, event_metadata=body.metadata))
    db.commit()
    return {"ok": True}


@router.get("/admin/classes")
async def admin_active_classes(db: Session = Depends(get_db), _admin: None = Depends(require_web_admin)):
    courses = db.query(OnlineCourse).filter(OnlineCourse.is_active.is_(True)).order_by(OnlineCourse.name.asc()).all()
    rows = []
    for course in courses:
        active = db.query(func.count(OnlineEnrollment.id)).filter(OnlineEnrollment.online_course_id == course.id, OnlineEnrollment.status == EnrollmentStatus.ACTIVE).scalar() or 0
        rows.append({"id": course.id, "name": course.name, "teacher": course.teacher, "duration_minutes": course.duration_minutes, "monthly_sessions": course.monthly_sessions, "active_students": int(active)})
    return rows


@router.get("/admin/students/{student_id}/enrollments")
async def admin_student_enrollments(student_id: int, db: Session = Depends(get_db), _admin: None = Depends(require_web_admin)):
    user = db.query(User).filter(User.id == student_id, User.role == UserRole.STUDENT).first()
    if not user:
        raise HTTPException(status_code=404, detail="student_not_found")
    enrollments = db.query(OnlineEnrollment).join(OnlineCourse).filter(OnlineEnrollment.user_id == student_id).order_by(desc(OnlineEnrollment.created_at)).all()
    return [{"id": item.id, "course_id": item.online_course_id, "course_name": item.online_course.name, "status": item.status.value, "payment_model": item.payment_model.value, "remaining_sessions": item.remaining_sessions, "completed_sessions": item.completed_sessions, "created_at": item.created_at.isoformat() if item.created_at else ""} for item in enrollments]


@router.get("/admin/analytics/summary")
async def admin_analytics_summary(db: Session = Depends(get_db), _admin: None = Depends(require_web_admin)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since_30 = now - timedelta(days=30)
    since_7 = now - timedelta(days=7)
    visits_30 = db.query(func.count(SiteEvent.id)).filter(SiteEvent.event_type == "page_view", SiteEvent.created_at >= since_30).scalar() or 0
    visitors_30 = db.query(func.count(func.distinct(SiteEvent.visitor_hash))).filter(SiteEvent.event_type == "page_view", SiteEvent.created_at >= since_30).scalar() or 0
    visits_7 = db.query(func.count(SiteEvent.id)).filter(SiteEvent.event_type == "page_view", SiteEvent.created_at >= since_7).scalar() or 0
    top_paths = db.query(SiteEvent.path, func.count(SiteEvent.id).label("count")).filter(SiteEvent.event_type == "page_view", SiteEvent.created_at >= since_30).group_by(SiteEvent.path).order_by(desc("count")).limit(10).all()
    ai_events = db.query(func.count(AdminLog.id)).filter(AdminLog.created_at >= since_30, AdminLog.action.ilike("%ai%")).scalar() or 0
    ai_chats = db.query(func.count(SiteEvent.id)).filter(SiteEvent.event_type == "ai_chat", SiteEvent.created_at >= since_30).scalar() or 0
    ai_errors = db.query(func.count(SiteEvent.id)).filter(SiteEvent.event_type == "ai_error", SiteEvent.created_at >= since_30).scalar() or 0
    active_enrollments = db.query(func.count(OnlineEnrollment.id)).filter(OnlineEnrollment.status == EnrollmentStatus.ACTIVE).scalar() or 0
    total_enrollments = db.query(func.count(OnlineEnrollment.id)).scalar() or 0
    active_classes = db.query(func.count(OnlineCourse.id)).filter(OnlineCourse.is_active.is_(True)).scalar() or 0
    students = db.query(func.count(User.id)).filter(User.role == UserRole.STUDENT).scalar() or 0
    return {"period_days": 30, "site": {"page_views_7d": int(visits_7), "page_views_30d": int(visits_30), "unique_visitors_30d": int(visitors_30), "top_paths": [{"path": path, "count": int(count)} for path, count in top_paths]}, "education": {"active_classes": int(active_classes), "active_enrollments": int(active_enrollments), "total_enrollments": int(total_enrollments), "students": int(students)}, "ai_agent": {"admin_ai_events_30d": int(ai_events), "website_chats_30d": int(ai_chats), "errors_30d": int(ai_errors), "source": "site_events+admin_logs"}}


@router.get("/admin/reservations")
async def admin_reservations(db: Session = Depends(get_db), _admin: None = Depends(require_web_admin)):
    rows = (
        db.query(Reservation, OnlineEnrollment.user_id, User.full_name, OnlineCourse.name)
        .join(OnlineEnrollment)
        .join(User, User.id == OnlineEnrollment.user_id)
        .join(OnlineCourse, OnlineCourse.id == OnlineEnrollment.online_course_id)
        .filter(Reservation.status.in_((ReservationStatus.PAYMENT_SUBMITTED, ReservationStatus.PENDING)))
        .order_by(Reservation.requested_date.asc(), Reservation.requested_time.asc())
        .all()
    )
    return [{
        "id": row.id,
        "student_id": user_id,
        "student_name": student_name,
        "course_name": course_name,
        "requested_date": row.requested_date,
        "requested_time": row.requested_time,
        "status": row.status.value,
        "payment_proof": row.payment_proof,
        "admin_notes": row.admin_notes,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    } for row, user_id, student_name, course_name in rows]


@router.post("/admin/reservations/{reservation_id}/review")
async def review_admin_reservation(
    reservation_id: int,
    body: ReservationReviewIn,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_web_admin),
):
    reservation = reservation_service.get_by_id(db, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="reservation_not_found")
    if body.action == "confirm":
        updated = reservation_service.confirm(db, reservation_id)
        if updated and updated.status != ReservationStatus.CONFIRMED:
            raise HTTPException(status_code=409, detail="reservation_payment_required")
    else:
        updated = reservation_service.reject(db, reservation_id, body.notes)
    return {"ok": True, "id": updated.id, "status": updated.status.value, "message": "رزرو تأیید شد." if body.action == "confirm" else "رزرو رد شد."}


@router.get("/admin/students", response_model=list[StudentAdminOut])
async def admin_list_students(
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    _admin: None = Depends(require_web_admin),
):
    query = db.query(User).filter(User.role == UserRole.STUDENT)
    needle = (q or "").strip()
    if needle:
        like = f"%{needle}%"
        query = query.filter((User.full_name.ilike(like)) | (User.phone.ilike(like)))
    # The admin roster should include every student, not only the previous 200-row window.
    users = query.order_by(User.created_at.desc()).limit(5000).all()
    ids = [user.id for user in users]
    profiles = {p.user_id: p for p in db.query(StudentProfile).filter(StudentProfile.user_id.in_(ids)).all()} if ids else {}
    accounts = {a.user_id: a for a in db.query(TelegramAccount).filter(TelegramAccount.user_id.in_(ids)).all()} if ids else {}
    return [_student_out(user, profiles.get(user.id), accounts.get(user.id)) for user in users]


@router.put("/admin/students/{student_id}", response_model=StudentAdminOut)
async def admin_update_student(
    student_id: int,
    body: StudentAdminUpdate,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_web_admin),
):
    user = db.query(User).filter(User.id == student_id, User.role == UserRole.STUDENT).first()
    if not user:
        raise HTTPException(status_code=404, detail="student_not_found")
    phone = None
    if body.phone:
        try:
            phone = order_service.normalize_phone(body.phone)
        except WebOrderError as exc:
            raise HTTPException(status_code=400, detail="invalid_phone") from exc
        duplicate = db.query(User).filter(User.phone == phone, User.id != student_id).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="phone_already_linked")
    user.full_name = body.full_name.strip()
    user.phone = phone
    email = body.email.strip().lower() if body.email else None
    if email:
        duplicate_email = db.query(User).filter(User.email == email, User.id != student_id).first()
        if duplicate_email:
            raise HTTPException(status_code=409, detail="email_already_linked")
    user.email = email
    profile = user.student_profile
    if not profile:
        profile = StudentProfile(user_id=user.id)
        db.add(profile)
    profile.bio = body.bio.strip() if body.bio else None
    profile.level = body.level.strip() if body.level else None
    profile.experience_years = body.experience_years
    db.commit()
    db.refresh(user)
    return _student_out(user, profile, user.telegram_account)


@router.get("/health")
async def api_v1_health():
    return {
        "ok": True,
        "service": "rahyar-api-v1",
        "site": settings.SITE_NAME,
    }


@router.get("/products", response_model=list[ProductOut])
async def list_products(db: Session = Depends(get_db)):
    try:
        products = order_service.list_products(db)
    except Exception:
        logger.exception("api_v1 list_products failed")
        raise HTTPException(status_code=503, detail="products_unavailable") from None
    return [
        ProductOut(
            id=p.id,
            title=p.title,
            description=getattr(p, "description", None),
            price=int(p.price or 0),
            is_active=bool(p.is_active),
            delivery_type=getattr(p.delivery_type, "value", str(p.delivery_type or "spotplayer")),
            thumbnail=getattr(p, "thumbnail", None),
        )
        for p in products
    ]


@router.get("/free-lessons", response_model=list[FreeLessonOut])
async def list_free_lessons(db: Session = Depends(get_db)):
    lessons = (
        db.query(FreeLesson)
        .filter(FreeLesson.is_active.is_(True))
        .order_by(FreeLesson.sort_order.asc(), FreeLesson.id.asc())
        .all()
    )
    return [_lesson_out(lesson) for lesson in lessons]


@router.get("/admin/free-lessons", response_model=list[FreeLessonOut])
async def admin_list_free_lessons(
    db: Session = Depends(get_db),
    _admin: None = Depends(require_web_admin),
):
    lessons = db.query(FreeLesson).order_by(FreeLesson.sort_order.asc(), FreeLesson.id.asc()).all()
    return [_lesson_out(lesson) for lesson in lessons]


@router.post("/admin/free-lessons", response_model=FreeLessonOut, status_code=201)
async def admin_create_free_lesson(
    body: FreeLessonIn,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_web_admin),
):
    if db.query(FreeLesson).filter(FreeLesson.slug == body.slug).first():
        raise HTTPException(status_code=409, detail="lesson_slug_exists")
    lesson = FreeLesson(
        **body.model_dump(exclude={"chapters"}),
        chapters=[chapter.model_dump() for chapter in body.chapters],
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return _lesson_out(lesson)


@router.put("/admin/free-lessons/{lesson_id}", response_model=FreeLessonOut)
async def admin_update_free_lesson(
    lesson_id: int,
    body: FreeLessonIn,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_web_admin),
):
    lesson = db.query(FreeLesson).filter(FreeLesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="lesson_not_found")
    duplicate = db.query(FreeLesson).filter(FreeLesson.slug == body.slug, FreeLesson.id != lesson_id).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="lesson_slug_exists")
    for key, value in body.model_dump(exclude={"chapters"}).items():
        setattr(lesson, key, value)
    lesson.chapters = [chapter.model_dump() for chapter in body.chapters]
    db.commit()
    db.refresh(lesson)
    return _lesson_out(lesson)


@router.delete("/admin/free-lessons/{lesson_id}", status_code=204)
async def admin_delete_free_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_web_admin),
):
    lesson = db.query(FreeLesson).filter(FreeLesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="lesson_not_found")
    db.delete(lesson)
    db.commit()


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    product = order_service.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    return ProductOut(
        id=product.id,
        title=product.title,
        description=getattr(product, "description", None),
        price=int(product.price or 0),
        is_active=bool(product.is_active),
        delivery_type=getattr(product.delivery_type, "value", str(product.delivery_type or "spotplayer")),
        thumbnail=getattr(product, "thumbnail", None),
    )


@router.get("/classes", response_model=list[ClassOut])
async def list_classes(db: Session = Depends(get_db)):
    try:
        classes = order_service.list_online_classes(db)
    except Exception:
        logger.exception("api_v1 list_classes failed")
        raise HTTPException(status_code=503, detail="classes_unavailable") from None
    return [
        ClassOut(
            id=c.id,
            name=c.name,
            description=getattr(c, "description", None),
            is_active=bool(c.is_active),
        )
        for c in classes
    ]


@router.post("/orders")
async def create_order(body: OrderIn, db: Session = Depends(get_db)):
    try:
        user, payment, product = order_service.create_product_order(
            db,
            product_id=body.product_id,
            full_name=body.full_name,
            phone=body.phone,
            note=body.note,
        )
    except WebOrderError as exc:
        mapping = {
            "invalid_phone": "شماره موبایل معتبر نیست.",
            "invalid_name": "نام را کامل وارد کنید.",
            "product_unavailable": "محصول در دسترس نیست.",
        }
        raise HTTPException(
            status_code=400,
            detail=mapping.get(str(exc), "ثبت سفارش ناموفق بود."),
        ) from exc

    if settings.OWNER_ID:
        try:
            await bot.send_message(
                chat_id=settings.OWNER_ID,
                text=(
                    "🛒 سفارش API از سایت آرتیست‌یار\n\n"
                    f"محصول: {product.title}\n"
                    f"مبلغ: {payment.amount:,} تومان\n"
                    f"هنرجو: {user.full_name}\n"
                    f"موبایل: {user.phone}\n"
                    f"پرداخت #{payment.id} — pending\n"
                    "پس از رسید در پنل تلگرام تأیید کنید."
                ),
            )
        except Exception:
            logger.exception("Failed owner notify for API order %s", payment.id)

    card = order_service.get_active_card(db)
    bot_url = None
    if settings.BOT_USERNAME:
        bot_url = f"https://t.me/{settings.BOT_USERNAME.lstrip('@')}?start=webpay_{payment.id}"
    return {
        "ok": True,
        "payment_id": payment.id,
        "amount": payment.amount,
        "status": payment.status,
        "product_title": product.title,
        "card": {
            "number": card.card_number if card else None,
            "holder": card.card_holder if card else None,
        },
        "bot_url": bot_url,
        "message": "سفارش ثبت شد و در انتظار تأیید ادمین است.",
    }


@router.get("/orders/{payment_id}/status", response_model=OrderStatusOut)
async def order_status(
    payment_id: int,
    phone: str = Query(min_length=10, max_length=20),
    db: Session = Depends(get_db),
):
    try:
        result = order_service.get_product_order_status(
            db,
            payment_id=payment_id,
            phone=phone,
        )
    except WebOrderError as exc:
        if str(exc) == "invalid_phone":
            raise HTTPException(status_code=400, detail="invalid_phone") from exc
        raise

    if not result:
        raise HTTPException(status_code=404, detail="order_not_found")

    _, payment, product = result
    return OrderStatusOut(
        payment_id=payment.id,
        product_title=product.title,
        amount=int(payment.amount or 0),
        status=str(payment.status),
        created_at=payment.created_at.isoformat(),
    )


@router.post("/orders/{payment_id}/receipt")
async def upload_order_receipt(
    payment_id: int,
    phone: str = Form(..., min_length=10, max_length=20),
    receipt: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not settings.OWNER_ID:
        raise HTTPException(status_code=503, detail="owner_notifications_unavailable")
    if not receipt.content_type or not (
        receipt.content_type.startswith("image/")
        or receipt.content_type == "application/pdf"
    ):
        raise HTTPException(status_code=400, detail="receipt_must_be_image_or_pdf")
    data = await receipt.read()
    if not data or len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="receipt_size_invalid")
    row = order_service.get_payment_for_phone(db, payment_id=payment_id, phone=phone)
    if not row:
        raise HTTPException(status_code=404, detail="order_not_found")
    user, payment, product = row
    if payment.status != "pending":
        raise HTTPException(status_code=409, detail="order_already_reviewed")

    payment.receipt_file_id = f"web-upload:{payment.id}"
    payment.admin_notes = "رسید از سایت دریافت شد؛ در انتظار تأیید ادمین"
    db.commit()
    caption = (
        "🧾 رسید پرداخت از سایت آرتیست‌یار\n\n"
        f"👤 نام: {user.full_name}\n"
        f"📱 موبایل: {user.phone or 'ثبت نشده'}\n"
        f"🎵 دوره: {product.title}\n"
        f"💳 مبلغ: {payment.amount:,} تومان\n"
        f"🆔 شماره پرداخت: {payment.id}\n"
        "\nبا دکمه زیر تأیید یا رد کنید."
    )
    telegram_file = BufferedInputFile(data, filename=receipt.filename or f"receipt-{payment.id}")
    if receipt.content_type.startswith("image/"):
        sent = await bot.send_photo(
            chat_id=settings.OWNER_ID,
            photo=telegram_file,
            caption=caption,
            reply_markup=payment_review_keyboard(payment.id),
        )
        payment.receipt_file_id = sent.photo[-1].file_id
    else:
        sent = await bot.send_document(
            chat_id=settings.OWNER_ID,
            document=telegram_file,
            caption=caption,
            reply_markup=payment_review_keyboard(payment.id),
        )
        payment.receipt_file_id = sent.document.file_id
    db.commit()
    return {"ok": True, "payment_id": payment.id, "status": payment.status, "message": "رسید برای بررسی ارسال شد."}


@router.get("/licenses", response_model=list[LicenseOut])
async def list_licenses(
    phone: str = Query(min_length=10, max_length=20),
    db: Session = Depends(get_db),
):
    try:
        rows = order_service.list_licenses_for_phone(db, phone=phone)
    except WebOrderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        LicenseOut(
            id=license_.id,
            product_title=course.title,
            status=license_.status,
            license_key=license_.license_key,
            license_url=license_.license_url,
            payment_id=license_.payment_id,
            created_at=license_.created_at.isoformat(),
        )
        for license_, course, _payment in rows
    ]


@router.post("/class-inquiries")
async def class_inquiry(body: InquiryIn, db: Session = Depends(get_db)):
    course = order_service.get_online_class(db, body.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="class_not_found")
    try:
        user, inquiry = class_inquiry_service.create_or_reuse(
            db,
            course=course,
            full_name=body.full_name,
            phone=body.phone,
            message=body.message,
            source="website-api",
        )
    except WebOrderError as exc:
        mapping = {
            "invalid_phone": "شماره موبایل معتبر نیست.",
            "invalid_name": "نام را کامل وارد کنید.",
        }
        raise HTTPException(
            status_code=400,
            detail=mapping.get(str(exc), "ثبت درخواست ناموفق بود."),
        ) from exc

    if settings.OWNER_ID:
        try:
            await bot.send_message(
                chat_id=settings.OWNER_ID,
                text=(
                    "🎼 درخواست کلاس از API آرتیست‌یار\n\n"
                    f"کلاس: {course.name}\n"
                    f"هنرجو: {user.full_name}\n"
                    f"موبایل: {user.phone}\n"
                    f"درخواست #{inquiry.id}\n"
                    f"پیام: {(body.message or '—')[:500]}"
                ),
            )
        except Exception:
            logger.exception("Failed owner notify for class inquiry")

    return {
        "ok": True,
        "inquiry_id": inquiry.id,
        "status": inquiry.status.value,
        "course_name": course.name,
        "message": "درخواست ثبت شد. ادمین از پنل تلگرام پیگیری می‌کند.",
    }
