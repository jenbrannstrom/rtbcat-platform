"""Fixture-driven tests for HTML thumbnail extraction patterns."""

from pathlib import Path

from utils.html_thumbnail import extract_image_urls_from_html, extract_primary_image_url


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "html_snippets"


def _load(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def test_extract_primary_from_basic_img_tag():
    snippet = _load("img_tag_basic.html")
    assert extract_primary_image_url(snippet) == "https://cdn.example.com/creative/main-banner.jpg"


def test_extract_primary_from_document_write_escaped():
    snippet = _load("document_write_escaped.js")
    assert extract_primary_image_url(snippet) == "https://ads.cdn.com/path/banner-728x90.png"


def test_extract_primary_from_background_image():
    snippet = _load("background_image_inline.html")
    assert extract_primary_image_url(snippet) == "https://img.example.org/assets/hero.webp"


def test_tracking_pixel_is_not_primary_when_real_image_exists():
    snippet = _load("tracking_and_main_image.html")
    urls = extract_image_urls_from_html(snippet)
    assert "https://tracker.example.com/pixel.gif?imp=1" in urls
    assert "https://cdn.example.com/ad/main-creative.png" in urls
    assert extract_primary_image_url(snippet) == "https://cdn.example.com/ad/main-creative.png"

