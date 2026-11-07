import json

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from app.core.auth import require_api_key
from app.core.config import settings
from app.models.schemas import ChatRequest
from app.routers.chat import chat


@pytest.fixture(autouse=True)
def _reset_key_settings(monkeypatch):
    """Every test starts from the local-dev default (no gate configured),
    overriding only what it needs."""
    monkeypatch.setattr(settings, "API_KEY", "")
    monkeypatch.setattr(settings, "API_KEYS_FILE", "")


def test_no_key_store_configured_is_a_noop():
    assert require_api_key(None) is None
    assert require_api_key("anything") is None


def test_legacy_single_key_resolves_to_default_user(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "shared-secret")
    assert require_api_key("shared-secret") == "default"


def test_invalid_key_is_rejected_once_a_gate_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "shared-secret")
    with pytest.raises(HTTPException) as exc_info:
        require_api_key("wrong-key")
    assert exc_info.value.status_code == 401


def test_missing_key_is_rejected_once_a_gate_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "shared-secret")
    with pytest.raises(HTTPException) as exc_info:
        require_api_key(None)
    assert exc_info.value.status_code == 401


def test_key_file_resolves_each_key_to_its_own_user(tmp_path, monkeypatch):
    key_file = tmp_path / "api_keys.json"
    key_file.write_text(
        json.dumps(
            [
                {"api_key": "key-a", "user_id": "alice", "name": "Alice"},
                {"api_key": "key-b", "user_id": "bob", "name": "Bob"},
            ]
        )
    )
    monkeypatch.setattr(settings, "API_KEYS_FILE", str(key_file))

    assert require_api_key("key-a") == "alice"
    assert require_api_key("key-b") == "bob"
    with pytest.raises(HTTPException):
        require_api_key("key-c")


def test_key_file_takes_priority_over_the_legacy_single_key(tmp_path, monkeypatch):
    key_file = tmp_path / "api_keys.json"
    key_file.write_text(json.dumps([{"api_key": "key-a", "user_id": "alice"}]))
    monkeypatch.setattr(settings, "API_KEYS_FILE", str(key_file))
    monkeypatch.setattr(settings, "API_KEY", "shared-secret")

    assert require_api_key("key-a") == "alice"
    with pytest.raises(HTTPException):
        # The legacy shared secret no longer works once a key file exists.
        require_api_key("shared-secret")


def _memory_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_chat_trusts_the_authenticated_identity_over_a_client_supplied_user_id():
    """The real access-control proof-point: before this change, any caller
    could read/write another user's session memory just by setting
    user_id in the request body. Once a key resolves an identity, that
    identity wins over whatever the client claims."""
    session = _memory_session()
    request = ChatRequest(question="Anything?", user_id="attacker-claimed-id")

    response = chat(request, session=session, authenticated_user="demo-bid-director")

    from app.models.schemas import ChatSession

    stored = session.get(ChatSession, response.session_id)
    assert stored.user_id == "demo-bid-director"


def test_chat_falls_back_to_client_supplied_user_id_when_unauthenticated():
    """Unauthenticated (no gate configured, local dev) keeps the old
    behaviour unchanged."""
    session = _memory_session()
    request = ChatRequest(question="Anything?", user_id="local-dev-user")

    response = chat(request, session=session, authenticated_user=None)

    from app.models.schemas import ChatSession

    stored = session.get(ChatSession, response.session_id)
    assert stored.user_id == "local-dev-user"
