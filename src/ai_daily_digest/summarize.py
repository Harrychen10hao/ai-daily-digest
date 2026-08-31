from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

import httpx

from .config import Settings
from .models import Article
from .normalize import clean_text

logger = logging.getLogger(__name__)


class MissingCredentialError(RuntimeError):
    pass


class SummarizationError(RuntimeError):
    pass


SECTION_KEYS = ("highlights", "ai_product", "ux_design", "tech", "paper", "github")
ITEM_FIELDS = ("title", "summary", "why", "url")


def _article_payload(articles: list[Article]) -> list[dict[str, Any]]:
    return [{
        "id": index,
        "title": item.title,
        "summary": item.summary,
        "source": item.source_name,
        "category": item.category,
        "published_at": item.published_at.isoformat(),
        "url": item.url,
    } for index, item in enumerate(articles)]


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise SummarizationError(f"模型返回的不是有效 JSON: {exc}") from exc
    if not isinstance(result, dict):
        raise SummarizationError("模型返回必须是 JSON 对象")
    return result


class LLMClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.request_timeout)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def summarize(self, articles: list[Article]) -> dict[str, Any]:
        if not self.settings.llm_api_key:
            raise MissingCredentialError("未配置 LLM_API_KEY，无法调用模型；将使用降级早报。")
        system_prompt = (
            "你是一名严谨的中文 AI 产品与 UX 编辑。只使用候选文章中的事实，不编造新闻或链接。"
            "返回严格 JSON，不要 Markdown 代码块。每个摘要、观点、影响控制在 80 个汉字以内。"
        )
        schema = {
            "trend": "一句话趋势",
            "highlights": [{"title": "", "summary": "", "why": "", "url": ""}],
            "ai_product": [{"title": "", "summary": "", "why": "", "url": ""}],
            "ux_design": [{"title": "", "summary": "", "why": "", "url": ""}],
            "tech": [{"title": "", "summary": "", "why": "", "url": ""}],
            "paper": [{"title": "", "summary": "", "why": "", "url": ""}],
            "github": [{"title": "", "summary": "", "why": "", "url": ""}],
            "action_suggestions": [""],
        }
        user_prompt = (
            "请从候选文章生成早报。highlights 选最多 3 条；其他分类各选 2-4 条，"
            "没有高质量内容则返回空数组。链接必须逐字复制候选文章的 url。JSON 结构如下：\n"
            f"{json.dumps(schema, ensure_ascii=False)}\n候选文章：\n"
            f"{json.dumps(_article_payload(articles), ensure_ascii=False)}"
        )
        try:
            response = self.client.post(
                f"{self.settings.llm_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.llm_api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.settings.llm_model,
                    "temperature": 0.2,
                    "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return validate_digest(_parse_json(content), articles)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise SummarizationError(f"模型调用失败: {exc}") from exc


def _item(article: Article, reason: str) -> dict[str, str]:
    summary = clean_text(article.summary or article.title, 80)
    return {"title": clean_text(article.title, 100), "summary": summary, "why": reason, "url": article.url}


def build_fallback_digest(articles: list[Article]) -> dict[str, Any]:
    digest: dict[str, Any] = {
        "trend": "今日暂无模型总结，先从可靠来源了解 AI 产品与科技动态。" if not articles else "AI 产品与科技领域持续围绕产品能力和用户体验演进。",
        "highlights": [], "ai_product": [], "ux_design": [], "tech": [], "paper": [], "github": [],
        "action_suggestions": [],
    }
    for article in articles[:3]:
        digest["highlights"].append(_item(article, "有助于快速了解近期行业变化。"))
    reasons = {
        "ai_product": "可观察 AI 功能、Agent 或交互方式的产品落地。",
        "ux_design": "可提炼用户研究、交互和设计流程中的实践方法。",
        "tech": "可能影响产品方向、技术选择或行业判断。",
        "paper": "适合进一步阅读，了解相关研究进展。",
        "github": "可作为体验、验证或工程实践的开源参考。",
    }
    for category in reasons:
        digest[category] = [_item(article, reasons[category]) for article in articles if article.category == category][:4]
    digest["action_suggestions"] = ["选一条内容深入阅读，并记录一个可应用到当前工作的具体启发。"] if articles else []
    return digest


def validate_digest(raw: dict[str, Any], articles: list[Article]) -> dict[str, Any]:
    allowed_urls = {article.url for article in articles}
    result: dict[str, Any] = {"trend": clean_text(str(raw.get("trend", "")), 120), "action_suggestions": []}
    for key in SECTION_KEYS:
        values = raw.get(key, [])
        if not isinstance(values, list):
            values = []
        cleaned = []
        for value in values:
            if not isinstance(value, dict) or value.get("url") not in allowed_urls:
                continue
            cleaned.append({
                "title": clean_text(str(value.get("title", "")), 100),
                "summary": clean_text(str(value.get("summary", "")), 80),
                "why": clean_text(str(value.get("why", "")), 80),
                "url": str(value["url"]),
            })
        result[key] = cleaned[:4]
    suggestions = raw.get("action_suggestions", [])
    if isinstance(suggestions, list):
        result["action_suggestions"] = [clean_text(str(item), 80) for item in suggestions if str(item).strip()][:3]
    return result
