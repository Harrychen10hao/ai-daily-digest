from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .classify import classify_and_filter
from .config import Settings, load_sources
from .dedupe import deduplicate
from .fetchers import NewsFetcher
from .filtering import select_articles
from .formatter import format_digest, format_feishu_cards
from .models import Article
from .summarize import LLMClient, MissingCredentialError, SummarizationError, build_fallback_digest

logger = logging.getLogger(__name__)


def _ensure_data_dir(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)


def save_articles(articles: list[Article], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([item.to_dict() for item in articles], ensure_ascii=False, indent=2), encoding="utf-8")


def load_articles(path: Path) -> list[Article]:
    if not path.exists():
        raise FileNotFoundError(f"找不到文章文件 {path}，请先运行 fetch。")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [Article.from_dict(item) for item in payload]


def save_digest(digest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")


def load_digest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"找不到早报结构化文件 {path}，请先运行 generate。")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"早报结构化文件必须是 JSON 对象: {path}")
    return payload


def fetch_pipeline(settings: Settings, now: datetime | None = None) -> list[Article]:
    sources = load_sources(settings.sources_file)
    fetcher = NewsFetcher(settings)
    try:
        articles = fetcher.fetch_all(sources, now=now)
    finally:
        fetcher.close()
    articles = deduplicate(classify_and_filter(articles))
    articles = select_articles(articles, now=now or datetime.now(timezone.utc), minimum_count=settings.minimum_articles, max_count=settings.max_candidates)
    save_articles(articles, settings.data_dir / "latest_articles.json")
    logger.info("本次保留 %d 条文章", len(articles))
    return articles


def generate_pipeline(settings: Settings, articles: list[Article] | None = None, test_mode: bool = False) -> str:
    _ensure_data_dir(settings)
    articles = articles if articles is not None else load_articles(settings.data_dir / "latest_articles.json")
    digest: dict[str, Any]
    if test_mode:
        logger.info("测试模式：跳过模型调用，使用降级早报")
        digest = build_fallback_digest(articles)
    else:
        client = LLMClient(settings)
        try:
            try:
                digest = client.summarize(articles)
            except (MissingCredentialError, SummarizationError) as exc:
                logger.warning("%s", exc)
                digest = build_fallback_digest(articles)
        finally:
            client.close()
    save_digest(digest, settings.data_dir / "latest_digest.json")
    text = format_digest(digest)
    (settings.data_dir / "latest_digest.md").write_text(text, encoding="utf-8")
    return text


def send_pipeline(settings: Settings) -> list[dict[str, Any]]:
    if not settings.feishu_webhook_url:
        raise MissingCredentialError("未配置 FEISHU_WEBHOOK_URL，无法发送飞书消息。")
    digest = load_digest(settings.data_dir / "latest_digest.json")
    messages = format_feishu_cards(digest, max_chars=settings.feishu_max_chars)
    from .feishu import FeishuClient
    client = FeishuClient(settings.feishu_webhook_url, timeout=settings.request_timeout, retries=settings.request_retries)
    try:
        client.send_posts(messages)
    finally:
        client.close()
    return messages
