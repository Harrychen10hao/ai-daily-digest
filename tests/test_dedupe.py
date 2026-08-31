from datetime import datetime, timezone

from ai_daily_digest.dedupe import canonicalize_url, deduplicate
from ai_daily_digest.models import Article


def article(title: str, url: str) -> Article:
    return Article(
        title=title,
        url=url,
        summary="summary",
        published_at=datetime(2026, 8, 31, tzinfo=timezone.utc),
        source_name="test",
        category="ai_product",
    )


def test_canonicalize_url_removes_tracking_parameters():
    assert canonicalize_url("https://Example.com/a/?utm_source=x&b=2") == "https://example.com/a?b=2"


def test_deduplicate_removes_duplicate_url_and_normalized_title():
    result = deduplicate([
        article("New AI Agent", "https://example.com/a?utm_source=x"),
        article("New AI Agent", "https://example.com/b"),
        article("Different", "https://example.com/a"),
    ])
    assert [item.title for item in result] == ["New AI Agent"]


def test_deduplicate_uses_long_content_fingerprint_for_reposts():
    first = article("Original title", "https://example.com/a")
    second = article("Rewritten title", "https://example.com/b")
    first = Article(**{**first.__dict__, "summary": "同一事件的完整报道内容，包含足够多的具体事实和上下文信息。"})
    second = Article(**{**second.__dict__, "summary": "同一事件的完整报道内容，包含足够多的具体事实和上下文信息。"})
    assert len(deduplicate([first, second])) == 1
