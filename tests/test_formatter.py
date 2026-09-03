from datetime import datetime, timezone

from ai_daily_digest.formatter import format_digest, format_feishu_posts, split_message
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


def test_format_feishu_posts_uses_hierarchy_bold_titles_and_clickable_links():
    digest = {
        "trend": "AI 产品从聊天走向工作流。",
        "highlights": [{
            "title": "Agent 交互更新",
            "summary": "摘要",
            "why": "值得关注",
            "url": "https://example.com/agent",
        }],
        "ai_product": [],
        "ux_design": [],
        "tech": [],
        "paper": [],
        "github": [],
        "action_suggestions": ["体验一次 Agent"],
    }

    posts = format_feishu_posts(digest, datetime(2026, 9, 3, tzinfo=timezone.utc))
    payload = posts[0]
    content = payload["content"]["post"]["zh_cn"]["content"]
    flattened = [element for line in content for element in line]

    assert payload["msg_type"] == "post"
    assert payload["content"]["post"]["zh_cn"]["title"] == "AI 产品与 UX 科技早报"
    assert any(element.get("style") == ["bold"] and element["text"] == "Agent 交互更新" for element in flattened)
    assert {element["tag"] for element in flattened} >= {"text", "a"}
    assert any(element.get("href") == "https://example.com/agent" for element in flattened)
    assert all("#" not in element.get("text", "") for element in flattened)


def test_format_feishu_posts_omits_empty_sections_and_splits_items():
    item = {"title": "标题", "summary": "摘要", "why": "原因", "url": "https://example.com/a"}
    digest = {
        "trend": "趋势",
        "highlights": [item, {**item, "url": "https://example.com/b"}],
        "ai_product": [], "ux_design": [], "tech": [], "paper": [], "github": [],
        "action_suggestions": [],
    }

    posts = format_feishu_posts(digest, max_chars=100)

    assert len(posts) > 1
    assert all(post["msg_type"] == "post" for post in posts)
    assert all(post["content"]["post"]["zh_cn"]["content"] for post in posts)
    assert "AI 产品体验" not in str(posts)


def test_format_feishu_posts_does_not_emit_empty_text_elements():
    digest = {
        "trend": "趋势",
        "highlights": [],
        "ai_product": [{
            "title": "产品更新",
            "summary": "摘要",
            "why": "启发",
            "url": "https://example.com/product",
        }],
        "ux_design": [],
        "tech": [],
        "paper": [],
        "github": [],
        "action_suggestions": [],
    }

    posts = format_feishu_posts(digest)
    elements = [element for line in posts[0]["content"]["post"]["zh_cn"]["content"] for element in line]

    assert not any(element.get("tag") == "text" and element.get("text") == "" for element in elements)
