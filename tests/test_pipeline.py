import json
from pathlib import Path

import pytest

from ai_daily_digest.config import Settings
from ai_daily_digest.pipeline import generate_pipeline, load_digest, send_pipeline


def test_generate_pipeline_saves_markdown_and_structured_digest(tmp_path: Path):
    settings = Settings(data_dir=tmp_path)
    text = generate_pipeline(settings, articles=[], test_mode=True)

    assert text.startswith("# ")
    assert (tmp_path / "latest_digest.md").exists()
    assert load_digest(tmp_path / "latest_digest.json")["trend"]


def test_send_pipeline_uses_structured_digest_for_feishu_posts(tmp_path: Path, monkeypatch):
    settings = Settings(data_dir=tmp_path, feishu_webhook_url="https://example.com/hook")
    digest = {
        "trend": "趋势",
        "highlights": [{
            "title": "真实标题",
            "summary": "摘要",
            "why": "原因",
            "url": "https://example.com/article",
        }],
        "ai_product": [],
        "ux_design": [],
        "tech": [],
        "paper": [],
        "github": [],
        "action_suggestions": [],
    }
    (tmp_path / "latest_digest.json").write_text(json.dumps(digest), encoding="utf-8")
    captured = []

    class FakeFeishuClient:
        def __init__(self, *args, **kwargs):
            pass

        def send_posts(self, payloads):
            captured.extend(payloads)

        def close(self):
            pass

    import ai_daily_digest.feishu
    monkeypatch.setattr(ai_daily_digest.feishu, "FeishuClient", FakeFeishuClient)

    send_pipeline(settings)

    assert captured[0]["msg_type"] == "post"
    assert "真实标题" in str(captured[0])
    assert "https://example.com/article" in str(captured[0])


def test_send_pipeline_requires_structured_digest(tmp_path: Path):
    settings = Settings(data_dir=tmp_path, feishu_webhook_url="https://example.com/hook")

    with pytest.raises(FileNotFoundError, match="latest_digest.json"):
        send_pipeline(settings)
