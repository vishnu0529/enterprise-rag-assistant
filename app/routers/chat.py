import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.auth import require_api_key
from app.core.db import get_session
from app.core.version import CODE_VERSION
from app.models.schemas import ApprovalRequest, ChatRequest, ChatResponse, Document
from app.services.rag_graph import NO_DOCUMENTS_ANSWER, answer_question_agentic, resume_approval
from app.services.session_store import add_message, get_history, get_or_create_session

router = APIRouter(tags=["chat"], dependencies=[Depends(require_api_key)])


def _to_response(session_id: str, result: dict) -> ChatResponse:
    return ChatResponse(
        session_id=session_id,
        answer=result.get("answer"),
        citations=result.get("citations", []),
        latency_ms=result.get("latency_ms", 0.0),
        prompt_tokens=result.get("prompt_tokens", 0),
        completion_tokens=result.get("completion_tokens", 0),
        cache_creation_tokens=result.get("cache_creation_tokens", 0),
        cache_read_tokens=result.get("cache_read_tokens", 0),
        faithfulness_score=result.get("faithfulness_score"),
        retries=result.get("retries", 0),
        escalated=result.get("escalated", False),
        used_memory=result.get("used_memory", False),
        sub_queries=result.get("sub_queries", []),
        strategist_reasoning=result.get("strategist_reasoning", ""),
        pending_approval=result.get("pending_approval", False),
        approval_status=result.get("approval_status", "not_required"),
        approval_reason=result.get("approval_reason", ""),
        draft_answer=result.get("draft_answer"),
        code_version=CODE_VERSION,
        cost_usd=result.get("cost_usd", 0.0),
    )


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, session: Session = Depends(get_session)):
    session_id = request.session_id or str(uuid.uuid4())
    get_or_create_session(session, session_id, user_id=request.user_id)
    history = get_history(session, session_id)

    # Cheap DB check before spending a Strategist LLM call on a corpus
    # that's empty anyway — the graph would reach the same no_documents
    # short-circuit itself, just after retrieval instead of before it.
    if session.exec(select(Document)).first() is None:
        add_message(session, session_id, "user", request.question)
        add_message(session, session_id, "assistant", NO_DOCUMENTS_ANSWER)
        return ChatResponse(
            session_id=session_id,
            answer=NO_DOCUMENTS_ANSWER,
            citations=[],
            latency_ms=0.0,
            prompt_tokens=0,
            completion_tokens=0,
            code_version=CODE_VERSION,
        )

    result = answer_question_agentic(
        request.question,
        top_k=request.top_k,
        document_id=request.document_id,
        history=history,
        user_id=request.user_id,
        session_id=session_id,
        require_approval=request.require_approval,
    )

    add_message(session, session_id, "user", request.question)
    # A paused run has no answer yet (result["answer"] is None) — nothing to
    # record until POST .../approve resolves it one way or the other.
    if not result.get("pending_approval"):
        add_message(session, session_id, "assistant", result["answer"])

    return _to_response(session_id, result)


@router.post("/chat/{session_id}/approve", response_model=ChatResponse)
def approve(session_id: str, request: ApprovalRequest, session: Session = Depends(get_session)):
    """Resumes a run paused by approval_gate_node (see rag_graph.py) — the
    human-in-the-loop boundary before a commercially-sensitive answer is
    released. session_id must be a session that's actually paused; there's
    no way to distinguish "never existed" from "already resolved" from
    LangGraph's own error here, so both surface as the same 409."""
    try:
        result = resume_approval(session_id, approved=request.approved, reason=request.reason)
    except KeyError as e:
        raise HTTPException(409, f"No pending approval for session {session_id!r} ({e})") from e

    if not result.get("pending_approval"):
        add_message(session, session_id, "assistant", result["answer"])

    return _to_response(session_id, result)


@router.get("/chat/{session_id}/history")
def chat_history(session_id: str, session: Session = Depends(get_session)):
    return get_history(session, session_id, limit=1000)
