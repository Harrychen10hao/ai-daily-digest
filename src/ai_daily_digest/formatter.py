from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


SECTION_NAMES = {
    "ai_product": "AI 产品体验",
    "ux_design": "UX/UI 设计经验",
    "tech": "科技资讯",
    "paper": "AI 论文",
    "github": "GitHub 开源项目",
}

WEEKDAYS = ("一", "二", "三", "四", "五", "六", "日")


def _single_line(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _text_element(text: str, bold: bool = False) -> dict[str, Any]:
    # Feishu custom-bot post elements reject the optional style field.
    return {"tag": "text", "text": text}


def _line_length(line: list[dict[str, Any]]) -> int:
    return sum(len(str(element.get("text", ""))) for element in line)


def _feishu_item_lines(item: dict[str, Any], section: str, number: str = "") -> list[list[dict[str, Any]]]:
    title = _single_line(item.get("title", "未命名")) or "未命名"
    summary = _single_line(item.get("summary", ""))
    why = _single_line(item.get("why", ""))
    url = _single_line(item.get("url", ""))
    if section == "highlights":
        summary_label = "一句话摘要"
        why_label = "为什么值得关注"
    else:
        summary_label = {
            "ai_product": "内容摘要",
            "ux_design": "核心观点",
            "tech": "发生了什么",
            "paper": "核心内容",
            "github": "项目概览",
        }.get(section, "内容摘要")
        why_label = {
            "ai_product": "对产品或 UX 设计的启发",
            "ux_design": "对设计师工作的启发",
            "tech": "可能产生的影响",
            "paper": "值得关注的原因",
            "github": "值得关注的原因",
        }.get(section, "值得关注的原因")

    title_line: list[dict[str, Any]] = []
    if number:
        title_line.append(_text_element(f"{number} "))
    title_line.append(_text_element(title, bold=True))
    lines = [title_line]
    if summary:
        lines.append([_text_element(f"{summary_label}：{summary}")])
    if why:
        lines.append([_text_element(f"{why_label}：{why}")])
    if url:
        lines.append([_text_element("🔗 "), {"tag": "a", "text": "查看原文", "href": url}])
    return lines


def _feishu_header(digest: dict[str, Any], published_at: datetime) -> list[list[dict[str, Any]]]:
    weekday = WEEKDAYS[published_at.weekday()]
    lines = [
        [_text_element("📰 AI 产品与 UX 科技早报", bold=True)],
        [_text_element(f"{published_at.year}年{published_at.month}月{published_at.day}日 · 星期{weekday}")],
        [_text_element("━" * 24)],
    ]
    trend = _single_line(digest.get("trend", ""))
    if trend:
        lines.append([_text_element(f"今日趋势：{trend}")])
    return lines


def _feishu_payload(title: str, lines: list[list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "msg_type": "post",
        "content": {"post": {"zh_cn": {"title": title, "content": lines}}},
    }


def format_feishu_posts(
    digest: dict[str, Any],
    published_at: datetime | None = None,
    max_chars: int = 6000,
) -> list[dict[str, Any]]:
    """Render a validated digest as Feishu rich-text post payloads."""
    if max_chars < 1:
        raise ValueError("max_chars 必须大于 0")
    published_at = published_at or datetime.now(ZoneInfo("Asia/Shanghai"))
    if published_at.tzinfo is not None:
        published_at = published_at.astimezone(ZoneInfo("Asia/Shanghai"))

    header = _feishu_header(digest, published_at)
    blocks: list[list[list[dict[str, Any]]]] = []
    highlights = digest.get("highlights", [])
    if highlights:
        blocks.append([[_text_element("今日重点", bold=True)]])
        circled_numbers = ("①", "②", "③")
        for index, item in enumerate(highlights[:3]):
            blocks.append(_feishu_item_lines(item, "highlights", circled_numbers[index]))

    for key, name in SECTION_NAMES.items():
        items = digest.get(key, [])
        if not items:
            continue
        blocks.append([[_text_element(name, bold=True)]])
        for item in items[:4]:
            blocks.append(_feishu_item_lines(item, key))

    actions = [_single_line(item) for item in digest.get("action_suggestions", []) if _single_line(item)]
    if actions:
        blocks.append([[_text_element("今日行动建议", bold=True)]] + [[_text_element(f"• {item}")] for item in actions[:3]])

    chunks: list[list[list[dict[str, Any]]]] = []
    current = list(header)
    current_length = sum(_line_length(line) for line in current)
    for block in blocks:
        block_length = sum(_line_length(line) for line in block)
        if current != header and current_length + block_length > max_chars:
            chunks.append(current)
            current = list(header)
            current_length = sum(_line_length(line) for line in current)
        current.extend(block)
        current_length += block_length
    if current:
        chunks.append(current)

    if not chunks:
        chunks = [header]
    total = len(chunks)
    return [
        _feishu_payload(
            "AI 产品与 UX 科技早报" if total == 1 else f"AI 产品与 UX 科技早报（{index}/{total}）",
            lines,
        )
        for index, lines in enumerate(chunks, start=1)
    ]


def _item_lines(item: dict[str, str], section: str) -> list[str]:
    if section == "highlights":
        return [
            f"### {item.get('title', '未命名')}",
            f"- 一句话摘要：{item.get('summary', '')}",
            f"- 为什么值得关注：{item.get('why', '')}",
            f"- 原文链接：{item.get('url', '')}",
        ]
    first_label = {"ai_product": "内容摘要", "ux_design": "核心观点", "tech": "发生了什么", "paper": "核心内容", "github": "项目概览"}.get(section, "内容摘要")
    second_label = {"ai_product": "对产品或 UX 设计的启发", "ux_design": "对设计师工作的启发", "tech": "可能产生的影响", "paper": "值得关注的原因", "github": "值得关注的原因"}.get(section, "值得关注的原因")
    return [
        f"### {item.get('title', '未命名')}",
        f"- {first_label}：{item.get('summary', '')}",
        f"- {second_label}：{item.get('why', '')}",
        f"- 原文链接：{item.get('url', '')}",
    ]


def format_digest(digest: dict, published_at: datetime | None = None) -> str:
    published_at = published_at or datetime.now(ZoneInfo("Asia/Shanghai"))
    if published_at.tzinfo is not None:
        published_at = published_at.astimezone(ZoneInfo("Asia/Shanghai"))
    lines = [f"# {published_at:%Y年%m月%d日} AI 产品与 UX 科技早报", "", digest.get("trend", ""), ""]
    highlights = digest.get("highlights", [])
    if highlights:
        lines.append("## 今日重点")
        lines.append("")
        for item in highlights[:3]:
            lines.extend(_item_lines(item, "highlights") + [""])
    for key, name in SECTION_NAMES.items():
        items = digest.get(key, [])
        if not items:
            continue
        lines.extend([f"## {name}", ""])
        for item in items[:4]:
            lines.extend(_item_lines(item, key) + [""])
    actions = [item for item in digest.get("action_suggestions", []) if str(item).strip()]
    if actions:
        lines.extend(["## 今日行动建议", ""])
        lines.extend(f"- {item}" for item in actions[:3])
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def split_message(text: str, max_chars: int = 6000) -> list[str]:
    if max_chars < 1:
        raise ValueError("max_chars 必须大于 0")
    if len(text) <= max_chars:
        return [text]
    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    chunks: list[str] = []
    current = ""
    for section in sections:
        if not section:
            continue
        candidate = f"{current}\n\n{section}".strip() if current else section.strip()
        if current and len(candidate) > max_chars:
            chunks.append(current.strip())
            current = section.strip()
        else:
            current = candidate
    if current:
        chunks.append(current.strip())
    final: list[str] = []
    for chunk in chunks:
        while len(chunk) > max_chars:
            final.append(chunk[:max_chars])
            chunk = chunk[max_chars:]
        if chunk:
            final.append(chunk)
    return final
