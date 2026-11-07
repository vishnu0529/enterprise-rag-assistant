"""Per-user API-key gate for the write/expensive endpoints.

The app has no user accounts or sessions. This resolves each request's
X-API-Key header to a *specific user identity* via a small key->user_id
store, rather than just checking "does this request carry the one shared
secret" (the old model). That's the actual access-control gap this
closes: /documents, /chat and /evaluate can now say *who* asked, not just
that *someone* with *a* key asked, and the chat graph's tracing spans
carry that identity (see app/services/rag_graph.py's "rag.user_id"
attribute). /health is deliberately left ungated so platform health
checks keep working without needing a key.

Key store: a JSON file at settings.API_KEYS_FILE (default "api_keys.json"
at the repo root), a list of {"api_key": ..., "user_id": ..., "name": ...}
objects — see api_keys.json.example. Missing/unset file falls back to the
single legacy API_KEY setting mapped to user_id "default", so existing
single-secret deployments keep working unchanged. Empty API_KEY and no
key file (the local-dev default) disables the gate entirely, matching the
project's "zero external services needed for local dev" principle.
"""

import json
from pathlib import Path

from fastapi import Header, HTTPException

from app.core.config import settings


def _load_key_store() -> dict[str, str]:
    """Not cached on purpose: this is a handful of entries read from a
    small local file, and re-reading each request keeps tests free to
    monkeypatch settings.API_KEYS_FILE / settings.API_KEY without having
    to reach into a cache to invalidate it."""
    path = Path(settings.API_KEYS_FILE) if settings.API_KEYS_FILE else None
    if path and path.exists():
        entries = json.loads(path.read_text())
        return {entry["api_key"]: entry["user_id"] for entry in entries}
    if settings.API_KEY:
        return {settings.API_KEY: "default"}
    return {}


def require_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")) -> str | None:
    """Returns the resolved user_id for a valid key, or None when no gate
    is configured at all (unchanged no-op behaviour for local dev)."""
    key_store = _load_key_store()
    if not key_store:
        return None
    if x_api_key is None or x_api_key not in key_store:
        raise HTTPException(401, "Missing or invalid X-API-Key header")
    return key_store[x_api_key]
