from __future__ import annotations

import re
from html import unescape


def clean_text(value: str, limit: int = 1000) -> str:
    value = unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit]
