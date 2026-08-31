from datetime import datetime, timedelta, timezone

from ai_daily_digest.filtering import select_articles
from ai_daily_digest.models import Article


def make_article(hours_ago: int, title: str) -> Article:
    now = datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc)
    return Article(
        title=title,
        url=f"https://example.com/{title}",
        summary="useful summary",
        published_at=now - timedelta(hours=hours_ago),
        source_name="test",
        category="tech",
    )


def test_select_articles_expands_to_seven_days_when_last_day_is_insufficient():
    now = datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc)
    articles = [make_article(5, "fresh"), make_article(72, "older")]
    result = select_articles(articles, now=now, minimum_count=2)
    assert {item.title for item in result} == {"fresh", "older"}


def test_select_articles_discards_articles_older_than_seven_days():
    now = datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc)
    result = select_articles([make_article(200, "too old")], now=now, minimum_count=1)
    assert result == []
