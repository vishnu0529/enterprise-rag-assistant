from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from app.models.schemas import Document
from app.routers.documents import list_documents, remove_document


def _memory_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed(session: Session, doc_id: str, owner_id: str | None) -> None:
    session.add(Document(id=doc_id, filename=f"{doc_id}.txt", num_chunks=1, owner_id=owner_id))
    session.commit()


def test_list_documents_scopes_to_the_authenticated_tenant():
    session = _memory_session()
    _seed(session, "doc-alice", owner_id="alice")
    _seed(session, "doc-bob", owner_id="bob")

    result = list_documents(session=session, user_id="alice")

    assert [d.id for d in result] == ["doc-alice"]


def test_list_documents_returns_everything_when_no_gate_is_configured():
    """Unauthenticated/local-dev (user_id is None): unchanged behaviour,
    single-tenant deployments still see every document."""
    session = _memory_session()
    _seed(session, "doc-alice", owner_id="alice")
    _seed(session, "doc-bob", owner_id="bob")

    result = list_documents(session=session, user_id=None)

    assert {d.id for d in result} == {"doc-alice", "doc-bob"}


def test_remove_document_rejects_a_non_owner_with_404_not_403():
    """Doesn't leak that another tenant's document exists."""
    session = _memory_session()
    _seed(session, "doc-bob", owner_id="bob")

    with pytest.raises(HTTPException) as exc_info:
        remove_document("doc-bob", session=session, user_id="alice")

    assert exc_info.value.status_code == 404


def test_remove_document_allows_the_owner():
    session = _memory_session()
    _seed(session, "doc-alice", owner_id="alice")

    with patch("app.routers.documents.delete_document") as mock_delete:
        result = remove_document("doc-alice", session=session, user_id="alice")

    mock_delete.assert_called_once_with("doc-alice")
    assert result == {"deleted": "doc-alice"}
    assert session.get(Document, "doc-alice") is None


def test_remove_document_allows_any_caller_when_no_gate_is_configured():
    session = _memory_session()
    _seed(session, "doc-alice", owner_id="alice")

    with patch("app.routers.documents.delete_document"):
        result = remove_document("doc-alice", session=session, user_id=None)

    assert result == {"deleted": "doc-alice"}
