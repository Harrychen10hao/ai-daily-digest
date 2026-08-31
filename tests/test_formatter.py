from datetime import datetime, timezone

from ai_daily_digest.formatter import format_digest, split_message
from ai_daily_digest.models import Article


def test_format_digest_omits_empty_optional_sections_and_keeps_links():
    digest = {
        "trend": "AI 产品正在从聊天转向可执行工作流。",
        "highlights": [{"title": "重点", "summary": "摘要", "why": "原因", "url": "https://example.com/1"}],
        "ai_product": [],
        "ux_design": [],
        "tech": [],
        "action_suggestions": ["体验一个 AI 产品并记录关键交互"],
    }
    text = format_digest(digest, datetime(2026, 8, 31, tzinfo=timezone.utc))
    assert "# 2026年08月31日 AI 产品与 UX 科技早报" in text
    assert "## 今日重点" in text
    assert "## AI 产品体验" not in text
    assert "https://example.com/1" in text


def test_split_message_respects_limit_and_preserves_all_content():
    text = "## 第一节\n" + "甲" * 20 + "\n\n## 第二节\n" + "乙" * 20
    chunks = split_message(text, max_chars=30)
    assert len(chunks) > 1
    assert "".join(chunks).replace("\n\n", "\n")
    assert "甲" * 20 in "\n".join(chunks)
    assert "乙" * 20 in "\n".join(chunks)
