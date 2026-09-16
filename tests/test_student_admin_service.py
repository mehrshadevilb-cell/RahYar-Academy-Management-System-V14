from src.services.student_admin_service import StudentAdminService, StudentFilter


def test_filter_enum_values():
    assert StudentFilter.ALL.value == "all"
    assert StudentFilter.TELEGRAM.value == "tg"
    assert StudentFilter.LEGACY.value == "legacy"


def test_service_page_size():
    assert StudentAdminService.PAGE_SIZE >= 5
