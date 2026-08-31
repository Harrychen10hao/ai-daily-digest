from __future__ import annotations

from .models import Article

VALID_CATEGORIES = {"ai_product", "ux_design", "tech", "paper", "github"}
LOW_QUALITY_TERMS = ("sponsored", "advertorial", "press release", "广告", "软文", "传闻", "rumor")
KEYWORDS = {
    "ai_product": ("agent", "ai product", "ai 产品", "人工智能", "模型", "copilot", "chatbot", "交互"),
    "ux_design": ("ux", "ui", "design", "user research", "usability", "可用性", "用户研究", "设计系统"),
    "paper": ("arxiv", "论文", "research paper"),
    "github": ("github", "open source", "开源", "repository"),
}


def is_low_quality(article: Article) -> bool:
    text = f"{article.title} {article.summary}".casefold()
    return any(term.casefold() in text for term in LOW_QUALITY_TERMS)


def classify(article: Article) -> str:
    if article.category in VALID_CATEGORIES:
        return article.category
    text = f"{article.title} {article.summary}".casefold()
    for category, terms in KEYWORDS.items():
        if any(term.casefold() in text for term in terms):
            return category
    return "tech"


def classify_and_filter(articles: list[Article]) -> list[Article]:
    result = []
    for article in articles:
        if is_low_quality(article):
            continue
        result.append(Article(**{**article.__dict__, "category": classify(article)}))
    return result
