from pathlib import Path


TEMPLATE = Path(__file__).parents[1] / "src" / "web" / "templates" / "base.html"


def test_web_theme_is_explicitly_dark_only() -> None:
    html = TEMPLATE.read_text(encoding="utf-8")

    assert '<meta name="color-scheme" content="dark" />' in html
    assert '<meta name="theme-color" content="#0f1419" />' in html
    assert "color-scheme: dark;" in html
    assert "prefers-color-scheme: light" not in html
    assert "prefers-color-scheme: dark" not in html


def test_web_base_keeps_required_layout_hooks() -> None:
    html = TEMPLATE.read_text(encoding="utf-8")

    for marker in (
        'lang="fa" dir="rtl"',
        '{% block title %}',
        '{% block content %}',
        'href="/products"',
        'href="/classes"',
        'class="wrap"',
        'class="btn"',
    ):
        assert marker in html
