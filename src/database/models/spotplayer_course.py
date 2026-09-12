from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class SpotPlayerCourse(Base):
    """
    One SpotPlayer course id belonging to a product.
    A single product (e.g. RahYar) can contain multiple SpotPlayer courses.
    """

    __tablename__ = "spotplayer_courses"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id"),
        nullable=False,
    )

    spotplayer_course_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    course_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    product = relationship(
        "Course",
        back_populates="spotplayer_courses",
    )
