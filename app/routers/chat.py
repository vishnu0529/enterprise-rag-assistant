import uuid

from fastapi import APIRouter

from app.models.schemas import ChatRequest, ChatResponse
from app.services.rag_chain import answer_question

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    result = answer_question(
        request.question, top_k=request.top_k, document_id=request.document_id
    )
    return ChatResponse(
        session_id=session_id,
        answer=result["answer"],
        citations=result["citations"],
        latency_ms=result["latency_ms"],
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
    )
