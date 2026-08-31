from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Article:
    title: str
    url: str
    summary: str
    published_at: datetime
    source_name: str
    category: str
    author: str = ""

    def __post_init__(self) -> None:
        if self.published_at.tzinfo is None:
            object.__setattr__(self, "published_at", self.published_at.replace(tzinfo=timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["published_at"] = self.published_at.astimezone(timezone.utc).isoformat()
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Article":
        published_at = value.get("published_at")
        if isinstance(published_at, str):
            published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if not isinstance(published_at, datetime):
            published_at = datetime.now(timezone.utc)
        return cls(
            title=str(value.get("title", "")).strip(),
            url=str(value.get("url", "")).strip(),
            summary=str(value.get("summary", "")).strip(),
            published_at=published_at,
            source_name=str(value.get("source_name", "未知来源")).strip(),
            category=str(value.get("category", "tech")).strip(),
            author=str(value.get("author", "")).strip(),
        )
