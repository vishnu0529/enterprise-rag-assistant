import uuid

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.db import get_session
from app.models.schemas import ChatRequest, ChatResponse
from app.services.rag_chain import answer_question
from app.services.session_store import add_message, get_history, get_or_create_session

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, session: Session = Depends(get_session)):
    session_id = request.session_id or str(uuid.uuid4())
    get_or_create_session(session, session_id)
    history = get_history(session, session_id)

    result = answer_question(
        request.question,
        top_k=request.top_k,
        document_id=request.document_id,
        history=history,
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
    )


@router.get("/chat/{session_id}/history")
def chat_history(session_id: str, session: Session = Depends(get_session)):
    return get_history(session, session_id, limit=1000)
