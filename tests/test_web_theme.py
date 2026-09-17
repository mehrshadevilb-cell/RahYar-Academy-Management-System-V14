from pathlib import Path


ROOT = Path(__file__).parents[1]
TEMPLATE_DIR = ROOT / "src" / "web" / "templates"
BASE = TEMPLATE_DIR / "base.html"


def test_web_theme_is_explicitly_dark_only() -> None:
    html = BASE.read_text(encoding="utf-8")

    assert '<meta name="color-scheme" content="dark" />' in html
    assert '<meta name="theme-color" content="#0b0f14" />' in html
    assert ":root {\n      color-scheme: dark;" in html
    assert "html { color-scheme: dark;" in html
    assert "color-scheme: dark;" in html
    assert "prefers-color-scheme: light" not in html
    assert "prefers-color-scheme: dark" not in html


def test_storefront_templates_use_shared_base_layout() -> None:
    pages = (
        "home.html",
        "products.html",
        "product_detail.html",
        "classes.html",
        "class_detail.html",
        "error.html",
        "order_success.html",
        "inquiry_success.html",
    )
    for page in pages:
        html = (TEMPLATE_DIR / page).read_text(encoding="utf-8")
        assert html.startswith('{% extends "base.html" %}'), page


def test_detail_forms_have_mobile_friendly_controls() -> None:
    for page in ("product_detail.html", "class_detail.html"):
        html = (TEMPLATE_DIR / page).read_text(encoding="utf-8")
        assert 'type="tel"' in html
        assert 'inputmode="tel"' in html
        assert 'autocomplete="name"' in html
        assert 'autocomplete="tel"' in html
        assert 'class="btn-row"' in html
