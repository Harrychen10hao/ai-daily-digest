from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

from .config import Settings, SourceConfig
from .models import Article
from .normalize import clean_text

logger = logging.getLogger(__name__)


class FetchError(RuntimeError):
    pass


def _entry_datetime(entry: Any, fallback: datetime) -> datetime:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(key)
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
    for key in ("published", "updated", "created"):
        value = entry.get(key)
        if value:
            try:
                result = parsedate_to_datetime(value)
                return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                pass
    return fallback


class NewsFetcher:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.request_timeout, follow_redirects=True)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _get(self, url: str) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.settings.request_retries + 1):
            try:
                response = self.client.get(url, headers={"User-Agent": "ai-daily-digest/0.1"})
                response.raise_for_status()
                return response
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self.settings.request_retries:
                    time.sleep(min(4.0, 0.5 * (2**attempt)))
        raise FetchError(f"请求失败 {url}: {last_error}") from last_error

    def fetch_source(self, source: SourceConfig, now: datetime | None = None) -> list[Article]:
        now = now or datetime.now(timezone.utc)
        response = self._get(source.url)
        if source.kind == "github_search":
            return self._parse_github(response, source)
        return self._parse_rss(response.content, source, now)

    @staticmethod
    def _parse_rss(content: bytes, source: SourceConfig, now: datetime) -> list[Article]:
        parsed = feedparser.parse(content)
        articles = []
        for entry in parsed.entries:
            url = str(entry.get("link", "")).strip()
            title = clean_text(str(entry.get("title", "")), 300)
            if not url or not title:
                continue
            articles.append(Article(
                title=title,
                url=url,
                summary=clean_text(str(entry.get("summary", entry.get("description", ""))), 1000),
                published_at=_entry_datetime(entry, now),
                source_name=source.name,
                category=source.category,
                author=clean_text(str(entry.get("author", "")), 100),
            ))
        return articles

    @staticmethod
    def _parse_github(response: httpx.Response, source: SourceConfig) -> list[Article]:
        payload = response.json()
        articles = []
        for item in payload.get("items", []):
            updated = item.get("updated_at", "")
            try:
                published_at = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            except (TypeError, ValueError):
                published_at = datetime.now(timezone.utc)
            url = str(item.get("html_url", "")).strip()
            title = str(item.get("full_name", item.get("name", ""))).strip()
            if not url or not title:
                continue
            articles.append(Article(
                title=title,
                url=url,
                summary=clean_text(str(item.get("description", "")), 1000),
                published_at=published_at,
                source_name=source.name,
                category=source.category,
                author=str(item.get("owner", {}).get("login", "")),
            ))
        return articles

    def fetch_all(self, sources: list[SourceConfig], now: datetime | None = None) -> list[Article]:
        result: list[Article] = []
        for source in sources:
            if not source.enabled:
                continue
            try:
                result.extend(self.fetch_source(source, now=now))
                logger.info("来源 %s 获取 %d 条", source.name, len(result))
            except FetchError as exc:
                logger.warning("跳过来源 %s: %s", source.name, exc)
        return result
