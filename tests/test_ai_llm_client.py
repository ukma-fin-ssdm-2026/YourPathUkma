"""
Тести для src/ai/llm_client.py (REL-001, PERF-001).

Використання ШІ: файл створено за допомогою Antigravity (Google DeepMind):
тести покривають обробку відсутності API-ключа, конфігурацію, успішні запити,
повторні спроби (retry) при помилках 5xx та мережевих помилках, та негайне завершення при 4xx.
Перевірено: pytest tests/test_ai_llm_client.py, ruff check tests/test_ai_llm_client.py.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.ai.llm_client import LLMError, _get_config, generate


def test_get_config_defaults(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LLM_MAX_RETRIES", raising=False)

    cfg = _get_config()
    assert cfg["api_key"] == ""
    assert cfg["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert cfg["model"] == "gemini-2.0-flash"
    assert cfg["timeout"] == 300
    assert cfg["max_retries"] == 2


def test_get_config_custom_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key-123")
    monkeypatch.setenv("LLM_API_BASE_URL", "https://custom.api/v1/")
    monkeypatch.setenv("LLM_MODEL", "gemini-pro")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "120")
    monkeypatch.setenv("LLM_MAX_RETRIES", "4")

    cfg = _get_config()
    assert cfg["api_key"] == "test-key-123"
    assert cfg["base_url"] == "https://custom.api/v1"
    assert cfg["model"] == "gemini-pro"
    assert cfg["timeout"] == 120
    assert cfg["max_retries"] == 4


def test_generate_missing_api_key_raises_llm_error(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(LLMError) as exc_info:
        generate("system", "user")
    assert "LLM_API_KEY не задано" in str(exc_info.value)
    assert exc_info.value.attempts == 0


def test_generate_success_first_try(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "dummy-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"plan": []}'}}],
    }

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        content, attempts = generate("sys", "user")
        assert content == '{"plan": []}'
        assert attempts == 1


def test_generate_retries_on_500_then_succeeds(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "dummy-key")
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")

    mock_resp_fail = MagicMock()
    mock_resp_fail.status_code = 503
    mock_resp_fail.text = "Service Unavailable"

    mock_resp_success = MagicMock()
    mock_resp_success.status_code = 200
    mock_resp_success.json.return_value = {
        "choices": [{"message": {"content": '{"plan": []}'}}],
    }

    with patch("httpx.Client") as mock_client_cls, patch("time.sleep") as mock_sleep:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.side_effect = [mock_resp_fail, mock_resp_success]
        mock_client_cls.return_value = mock_client

        content, attempts = generate("sys", "user")
        assert content == '{"plan": []}'
        assert attempts == 2
        mock_sleep.assert_called_once_with(2)


def test_generate_non_retryable_400_raises_immediately(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "dummy-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "Bad Request: Invalid prompt"

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        with pytest.raises(LLMError) as exc_info:
            generate("sys", "user")
        assert "400" in str(exc_info.value)
        assert exc_info.value.attempts == 1


def test_generate_exhausts_retries_raises_llm_error(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "dummy-key")
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")

    mock_resp = MagicMock()
    mock_resp.status_code = 502
    mock_resp.text = "Bad Gateway"

    with patch("httpx.Client") as mock_client_cls, patch("time.sleep"):
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        with pytest.raises(LLMError) as exc_info:
            generate("sys", "user")
        assert exc_info.value.attempts == 3  # 1 initial + 2 retries


def test_generate_network_error_retries(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "dummy-key")
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")

    mock_resp_success = MagicMock()
    mock_resp_success.status_code = 200
    mock_resp_success.json.return_value = {
        "choices": [{"message": {"content": '{"plan": []}'}}],
    }

    with patch("httpx.Client") as mock_client_cls, patch("time.sleep"):
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.side_effect = [
            httpx.ConnectError("Network unreachable"),
            mock_resp_success,
        ]
        mock_client_cls.return_value = mock_client

        content, attempts = generate("sys", "user")
        assert content == '{"plan": []}'
        assert attempts == 2
