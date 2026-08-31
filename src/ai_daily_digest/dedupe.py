from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import Article

TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src"}


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_KEYS
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(sorted(query)), ""))


def normalized_title(title: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", title.casefold())


def content_fingerprint(article: Article) -> str:
    summary = re.sub(r"\s+", " ", article.summary.casefold()).strip()
    if len(summary) < 20:
        return ""
    text = summary
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def deduplicate(articles: list[Article]) -> list[Article]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    seen_fingerprints: set[str] = set()
    result: list[Article] = []
    for article in articles:
        url = canonicalize_url(article.url)
        title = normalized_title(article.title)
        fingerprint = content_fingerprint(article)
        if not url or url in seen_urls or (title and title in seen_titles) or (fingerprint and fingerprint in seen_fingerprints):
            continue
        seen_urls.add(url)
        if title:
            seen_titles.add(title)
        if fingerprint:
            seen_fingerprints.add(fingerprint)
        result.append(article)
    return result
