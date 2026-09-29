from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.services import llm_client
from app.services.llm_client import _anthropic_client, _google_client, call_llm


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


def _mock_anthropic_response(cache_creation_input_tokens=0, cache_read_input_tokens=0):
    response = MagicMock()
    response.content = [MagicMock(text="answer")]
    response.usage.input_tokens = 10
    response.usage.output_tokens = 5
    response.usage.cache_creation_input_tokens = cache_creation_input_tokens
    response.usage.cache_read_input_tokens = cache_read_input_tokens
    return response


def test_anthropic_short_system_prompt_is_not_cached():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response()

    with (
        patch.object(settings, "LLM_PROVIDER", "anthropic"),
        patch("app.services.llm_client._anthropic_client", return_value=mock_client),
    ):
        call_llm("short system prompt", "question")

    kwargs = mock_client.messages.create.call_args.kwargs
    assert kwargs["system"] == "short system prompt"


def test_anthropic_long_system_prompt_gets_cache_control():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response()
    long_prompt = "x" * 4096

    with (
        patch.object(settings, "LLM_PROVIDER", "anthropic"),
        patch("app.services.llm_client._anthropic_client", return_value=mock_client),
    ):
        call_llm(long_prompt, "question")

    kwargs = mock_client.messages.create.call_args.kwargs
    assert kwargs["system"] == [
        {"type": "text", "text": long_prompt, "cache_control": {"type": "ephemeral"}}
    ]


def test_anthropic_cache_usage_is_read_from_the_response():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response(
        cache_creation_input_tokens=123, cache_read_input_tokens=456
    )

    with (
        patch.object(settings, "LLM_PROVIDER", "anthropic"),
        patch("app.services.llm_client._anthropic_client", return_value=mock_client),
    ):
        result = call_llm("short system prompt", "question")

    assert result.cache_creation_tokens == 123
    assert result.cache_read_tokens == 456


def test_anthropic_cache_usage_defaults_to_zero_when_absent():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response()

    with (
        patch.object(settings, "LLM_PROVIDER", "anthropic"),
        patch("app.services.llm_client._anthropic_client", return_value=mock_client),
    ):
        result = call_llm("short system prompt", "question")

    assert result.cache_creation_tokens == 0
    assert result.cache_read_tokens == 0


def test_calls_are_not_paced_when_the_interval_is_zero():
    """The default must not slow interactive /chat down at all."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response()

    with (
        patch.object(settings, "LLM_PROVIDER", "anthropic"),
        patch.object(settings, "LLM_MIN_INTERVAL_SECONDS", 0.0),
        patch("app.services.llm_client._anthropic_client", return_value=mock_client),
        patch("app.services.llm_client.time.sleep") as mock_sleep,
    ):
        call_llm("short system prompt", "question")
        call_llm("short system prompt", "question")

    mock_sleep.assert_not_called()


def test_a_second_call_waits_out_the_configured_interval():
    """The free Gemini tier caps requests per minute, which the SDK's own
    backoff cannot ride out. Spacing the calls keeps the rate under the cap."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response()

    llm_client._last_call_started_at = 0.0
    with (
        patch.object(settings, "LLM_PROVIDER", "anthropic"),
        patch.object(settings, "LLM_MIN_INTERVAL_SECONDS", 5.0),
        patch("app.services.llm_client._anthropic_client", return_value=mock_client),
        patch("app.services.llm_client.time.sleep") as mock_sleep,
        patch("app.services.llm_client.time.monotonic", side_effect=[100.0, 100.0, 101.5, 101.5]),
    ):
        call_llm("short system prompt", "question")  # sets the clock to 100.0
        call_llm("short system prompt", "question")  # 1.5s later, owes 3.5s

    mock_sleep.assert_called_once()
    assert mock_sleep.call_args[0][0] == pytest.approx(3.5)


def test_no_wait_when_more_than_the_interval_has_already_passed():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response()

    llm_client._last_call_started_at = 0.0
    with (
        patch.object(settings, "LLM_PROVIDER", "anthropic"),
        patch.object(settings, "LLM_MIN_INTERVAL_SECONDS", 5.0),
        patch("app.services.llm_client._anthropic_client", return_value=mock_client),
        patch("app.services.llm_client.time.sleep") as mock_sleep,
        patch("app.services.llm_client.time.monotonic", side_effect=[200.0, 200.0, 260.0, 260.0]),
    ):
        call_llm("short system prompt", "question")
        call_llm("short system prompt", "question")

    mock_sleep.assert_not_called()
