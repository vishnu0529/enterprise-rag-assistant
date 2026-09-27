import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int
    completion_tokens: int


def _google_client():
    from google import genai
    from google.genai import types

    # Neither timeout nor retry existed before — a hung connection could
    # hang a /chat request indefinitely. Uses the SDK's own retry transport
    # (exponential backoff, jittered) rather than a hand-rolled loop.
    http_options = types.HttpOptions(
        timeout=settings.LLM_TIMEOUT_SECONDS * 1000,  # genai takes milliseconds
        retry_options=types.HttpRetryOptions(
            attempts=settings.LLM_MAX_RETRIES + 1,  # attempts includes the first try
            initial_delay=1.0,
            max_delay=10.0,
            exp_base=2.0,
            jitter=0.5,
        ),
    )
    return genai.Client(api_key=settings.GOOGLE_API_KEY, http_options=http_options)


def _anthropic_client():
    import anthropic

    # timeout + max_retries are native httpx-transport options on this SDK —
    # same exponential-backoff-with-jitter behaviour as the Google branch,
    # just configured through the vendor's own mechanism instead of ours.
    return anthropic.Anthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=float(settings.LLM_TIMEOUT_SECONDS),
        max_retries=settings.LLM_MAX_RETRIES,
    )


def call_llm(system: str, user: str, max_tokens: int = 2048) -> LLMResult:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "google":
        client = _google_client()
        prompt = f"{system}\n\n{user}"
        response = client.models.generate_content(
            model=settings.LLM_MODEL,
            contents=prompt,
        )
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        completion_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
        return LLMResult(
            text=response.text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    elif provider == "anthropic":
        client = _anthropic_client()
        msg = client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return LLMResult(
            text=msg.content[0].text,
            prompt_tokens=msg.usage.input_tokens,
            completion_tokens=msg.usage.output_tokens,
        )
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


def call_llm_json(system: str, user: str, max_tokens: int = 2048) -> dict[str, Any]:
    result = call_llm(
        system,
        user + "\n\nRespond ONLY with valid JSON. No markdown, no prose.",
        max_tokens,
    )
    cleaned = re.sub(r"^```(?:json)?\s*", "", result.text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("JSON parse failed. Raw response:\n%s", result.text)
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc
