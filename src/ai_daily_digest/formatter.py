from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo


SECTION_NAMES = {
    "ai_product": "AI 产品体验",
    "ux_design": "UX/UI 设计经验",
    "tech": "科技资讯",
    "paper": "AI 论文",
    "github": "GitHub 开源项目",
}


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
