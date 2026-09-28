import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# Anthropic prompt caching only pays off once a system prompt is "long"
# (the API's own minimum is 1024 tokens on Sonnet 5). No tokenizer dependency
# is pinned here, so this uses a conservative chars-per-token heuristic
# (~4 chars/token for English text) as a proxy. Same pattern already proven
# in ai-business-automation-hub's provider.py (build_system_message). Erring
# toward "cache it" costs nothing on a miss, since cache_control on a short prompt
# is a no-op, not an error, so the heuristic is deliberately rounded down.
_ANTHROPIC_CACHE_THRESHOLD_CHARS = 4096


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    # 0 on every non-Anthropic provider and on any Anthropic call whose system
    # prompt didn't cross the caching threshold above; these only become
    # nonzero once a cache write or read actually happens.
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0


def _google_client():
    from google import genai
    from google.genai import types

    # Neither timeout nor retry existed before, so a hung connection could
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

    # timeout + max_retries are native httpx-transport options on this SDK,
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
        system_param = (
            [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
            if len(system) >= _ANTHROPIC_CACHE_THRESHOLD_CHARS
            else system
        )
        msg = client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=max_tokens,
            system=system_param,
            messages=[{"role": "user", "content": user}],
        )
        return LLMResult(
            text=msg.content[0].text,
            prompt_tokens=msg.usage.input_tokens,
            completion_tokens=msg.usage.output_tokens,
            cache_creation_tokens=getattr(msg.usage, "cache_creation_input_tokens", 0) or 0,
            cache_read_tokens=getattr(msg.usage, "cache_read_input_tokens", 0) or 0,
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
