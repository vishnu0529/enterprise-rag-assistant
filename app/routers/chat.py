import uuid

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.core.auth import require_api_key
from app.core.db import get_session
from app.models.schemas import ChatRequest, ChatResponse, Document
from app.services.rag_graph import NO_DOCUMENTS_ANSWER, answer_question_agentic
from app.services.session_store import add_message, get_history, get_or_create_session

router = APIRouter(tags=["chat"], dependencies=[Depends(require_api_key)])


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
        )

    result = answer_question_agentic(
        request.question,
        top_k=request.top_k,
        document_id=request.document_id,
        history=history,
        user_id=request.user_id,
        session_id=session_id,
    )

    add_message(session, session_id, "user", request.question)
    add_message(session, session_id, "assistant", result["answer"])

    return ChatResponse(
        session_id=session_id,
        answer=result["answer"],
        citations=result["citations"],
        latency_ms=result["latency_ms"],
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
        faithfulness_score=result.get("faithfulness_score"),
        retries=result.get("retries", 0),
        used_memory=result.get("used_memory", False),
        sub_queries=result.get("sub_queries", []),
        strategist_reasoning=result.get("strategist_reasoning", ""),
    )


@router.get("/chat/{session_id}/history")
def chat_history(session_id: str, session: Session = Depends(get_session)):
    return get_history(session, session_id, limit=1000)
