from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import Article


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def select_articles(
    articles: list[Article],
    now: datetime | None = None,
    minimum_count: int = 8,
    max_count: int = 30,
) -> list[Article]:
    now = _aware(now or datetime.now(timezone.utc))
    recent_cutoff = now - timedelta(hours=24)
    weekly_cutoff = now - timedelta(days=7)
    recent = [item for item in articles if recent_cutoff <= _aware(item.published_at) <= now]
    weekly = [item for item in articles if weekly_cutoff <= _aware(item.published_at) <= now]
    eligible = recent if len(recent) >= minimum_count else weekly
    return sorted(eligible, key=lambda item: _aware(item.published_at), reverse=True)[:max_count]
