from ai_daily_digest.config import Settings


def test_empty_optional_llm_environment_values_use_defaults(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("LLM_MODEL", "")

    settings = Settings.from_env()

    assert settings.llm_base_url == "https://api.openai.com/v1"
    assert settings.llm_model == "gpt-4o-mini"
