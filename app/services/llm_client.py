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


def call_llm(system: str, user: str, max_tokens: int = 2048) -> LLMResult:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "google":
        from google import genai

        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
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
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
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
