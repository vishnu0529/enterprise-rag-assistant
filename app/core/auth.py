"""Shared API-key gate for the write/expensive endpoints.

The app has no user accounts — this is a single shared secret, not
per-user auth. Its purpose is narrow: stop random internet traffic from
hitting a publicly-deployed instance's /documents (arbitrary uploads),
/chat and /evaluate (real, metered LLM calls this project's own Gemini
key pays for). /health is deliberately left ungated so platform health
checks keep working without needing the secret.

If API_KEY is unset (the local-dev default), the gate is a no-op — this
matches the project's existing "zero external services needed for local
dev" design principle rather than forcing a secret on every contributor.
"""

from fastapi import Header, HTTPException

from app.core.config import settings


def require_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")) -> None:
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(401, "Missing or invalid X-API-Key header")
