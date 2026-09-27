from unittest.mock import patch

from app.core.config import settings
from app.services.llm_client import _anthropic_client, _google_client


def test_google_client_gets_explicit_timeout_and_retry_options():
    with patch.object(settings, "GOOGLE_API_KEY", "test-key"):
        client = _google_client()

    http_options = client._api_client._http_options
    assert http_options.timeout == settings.LLM_TIMEOUT_SECONDS * 1000
    retry = http_options.retry_options
    assert retry.attempts == settings.LLM_MAX_RETRIES + 1
    assert retry.exp_base == 2.0


def test_anthropic_client_gets_explicit_timeout_and_max_retries():
    with patch.object(settings, "ANTHROPIC_API_KEY", "test-key"):
        client = _anthropic_client()

    assert client.timeout == float(settings.LLM_TIMEOUT_SECONDS)
    assert client.max_retries == settings.LLM_MAX_RETRIES


def test_timeout_and_retries_are_configurable_via_settings():
    with (
        patch.object(settings, "GOOGLE_API_KEY", "test-key"),
        patch.object(settings, "LLM_TIMEOUT_SECONDS", 5),
        patch.object(settings, "LLM_MAX_RETRIES", 4),
    ):
        client = _google_client()
        http_options = client._api_client._http_options

    assert http_options.timeout == 5000
    assert http_options.retry_options.attempts == 5
