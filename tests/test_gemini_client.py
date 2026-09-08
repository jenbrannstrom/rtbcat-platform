"""Regression checks for Gemini transport settings and truncated responses."""

import sys
from types import SimpleNamespace

import pytest

from services.gemini_client import generate_gemini_content


@pytest.fixture
def fake_genai(monkeypatch):
    captured = {}

    def generate_content(**kwargs):
        captured["request"] = kwargs
        return captured.get("response", SimpleNamespace(text="지금 다운로드", candidates=[]))

    def client(**kwargs):
        captured["client"] = kwargs
        return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))

    types = SimpleNamespace(HttpOptions=SimpleNamespace, GenerateContentConfig=SimpleNamespace)
    genai = SimpleNamespace(Client=client, types=types)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", types)
    import google
    monkeypatch.setattr(google, "genai", genai, raising=False)
    monkeypatch.setenv("CATSCAN_GEMINI_MODEL", "gemini-2.5-flash")
    return captured


@pytest.mark.parametrize("seconds,milliseconds", [(12.0, 12000), (20.0, 20000), (0.5, 500)])
def test_timeout_seconds_are_converted_to_sdk_milliseconds(fake_genai, seconds, milliseconds):
    assert generate_gemini_content("Read text", "test-key", timeout=seconds) == "지금 다운로드"
    assert fake_genai["client"]["http_options"].timeout == milliseconds


def test_language_json_can_disable_thinking_without_changing_other_callers(fake_genai):
    generate_gemini_content("Read text", "test-key", max_output_tokens=512, thinking_budget=0, response_mime_type="application/json")
    config = fake_genai["request"]["config"]
    assert config.thinkingConfig == {"thinkingBudget": 0}
    assert config.maxOutputTokens == 512
    assert config.responseMimeType == "application/json"

    generate_gemini_content("Analyze markets", "test-key")
    assert not hasattr(fake_genai["request"]["config"], "thinkingConfig")


def test_model_without_flash_budget_support_does_not_receive_zero_budget(fake_genai, monkeypatch):
    monkeypatch.setenv("CATSCAN_GEMINI_MODEL", "gemini-2.5-pro")
    generate_gemini_content("Read text", "test-key", thinking_budget=0)
    assert not hasattr(fake_genai["request"]["config"], "thinkingConfig")


def test_truncated_response_is_reported_before_reading_partial_text(fake_genai):
    fake_genai["response"] = SimpleNamespace(text="{", candidates=[SimpleNamespace(finish_reason="MAX_TOKENS")])
    with pytest.raises(RuntimeError, match="truncated.*MAX_TOKENS"):
        generate_gemini_content("Read text", "test-key")
