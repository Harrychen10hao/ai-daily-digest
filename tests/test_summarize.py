from datetime import datetime, timezone

from ai_daily_digest.models import Article
from ai_daily_digest.summarize import build_fallback_digest, validate_digest


def make_article(url: str, category: str = "ai_product") -> Article:
    return Article(
        title="AI 产品更新",
        url=url,
        summary="这是一个产品更新摘要。",
        published_at=datetime(2026, 8, 31, tzinfo=timezone.utc),
        source_name="官方博客",
        category=category,
    )


def test_validate_digest_drops_items_with_unfetched_links():
    valid = make_article("https://example.com/valid")
    digest = {
        "trend": "趋势",
        "highlights": [
            {"title": "真实", "summary": "摘要", "why": "原因", "url": valid.url},
            {"title": "伪造", "summary": "摘要", "why": "原因", "url": "https://evil.example.com"},
        ],
    }
    result = validate_digest(digest, [valid])
    assert [item["title"] for item in result["highlights"]] == ["真实"]


def test_fallback_digest_is_available_without_model_credentials():
    result = build_fallback_digest([make_article("https://example.com/1")])
    assert result["highlights"][0]["url"] == "https://example.com/1"
    assert result["ai_product"][0]["url"] == "https://example.com/1"
