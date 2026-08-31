from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass(frozen=True)
class SourceConfig:
    name: str
    url: str
    category: str
    kind: str = "rss"
    enabled: bool = True
    priority: int = 1
    query: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SourceConfig":
        return cls(
            name=str(value["name"]),
            url=str(value["url"]),
            category=str(value.get("category", "tech")),
            kind=str(value.get("kind", "rss")),
            enabled=bool(value.get("enabled", True)),
            priority=int(value.get("priority", 1)),
            query=str(value.get("query", "")),
        )


@dataclass(frozen=True)
class Settings:
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    feishu_webhook_url: str = ""
    data_dir: Path = Path("data")
    sources_file: Path = Path("config/sources.yaml")
    timezone: str = "Asia/Shanghai"
    request_timeout: float = 20.0
    request_retries: int = 2
    minimum_articles: int = 8
    max_candidates: int = 30
    feishu_max_chars: int = 6000

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
            llm_base_url=os.getenv("LLM_BASE_URL", "").strip().rstrip("/") or "https://api.openai.com/v1",
            llm_model=os.getenv("LLM_MODEL", "").strip() or "gpt-4o-mini",
            feishu_webhook_url=os.getenv("FEISHU_WEBHOOK_URL", "").strip(),
            data_dir=Path(os.getenv("DATA_DIR", "data")),
            sources_file=Path(os.getenv("SOURCES_FILE", "config/sources.yaml")),
            timezone=os.getenv("TIMEZONE", "Asia/Shanghai").strip(),
            request_timeout=float(os.getenv("REQUEST_TIMEOUT", "20")),
            request_retries=int(os.getenv("REQUEST_RETRIES", "2")),
            minimum_articles=int(os.getenv("MINIMUM_ARTICLES", "8")),
            max_candidates=int(os.getenv("MAX_CANDIDATES", "30")),
            feishu_max_chars=int(os.getenv("FEISHU_MAX_CHARS", "6000")),
        )


def load_sources(path: Path) -> list[SourceConfig]:
    with path.open("r", encoding="utf-8") as file:
        document = yaml.safe_load(file) or {}
    raw_sources = document.get("sources", document) if isinstance(document, dict) else document
    if not isinstance(raw_sources, list):
        raise ValueError(f"来源配置必须是列表: {path}")
    return [SourceConfig.from_dict(item) for item in raw_sources if isinstance(item, dict)]
