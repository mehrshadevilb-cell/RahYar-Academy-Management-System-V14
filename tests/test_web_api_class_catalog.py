from src.database.models.online_course import OnlineCourse
from src.web.catalog_schema import class_out


def test_online_class_catalog_exposes_planning_details():
    course = OnlineCourse(
        id=17,
        name="میکس و مسترینگ",
        teacher="مهرشاد بنائی",
        duration_minutes=90,
        monthly_price=4_500_000,
        term_price=12_000_000,
        monthly_sessions=4,
        term_sessions=12,
        is_active=True,
    )

    result = class_out(course)

    assert result.id == 17
    assert result.teacher == "مهرشاد بنائی"
    assert result.duration_minutes == 90
    assert result.monthly_price == 4_500_000
    assert result.term_price == 12_000_000
    assert result.monthly_sessions == 4
    assert result.term_sessions == 12
