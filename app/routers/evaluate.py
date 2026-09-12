from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import require_api_key
from app.services.evaluation import evaluate_question

router = APIRouter(tags=["evaluation"], dependencies=[Depends(require_api_key)])


class EvaluateRequest(BaseModel):
    question: str
    ground_truth: str | None = None
    top_k: int | None = None


class EvaluateResponse(BaseModel):
    question: str
    answer: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int


@router.post("/evaluate", response_model=EvaluateResponse)
def evaluate(request: EvaluateRequest):
    result = evaluate_question(
        request.question, ground_truth=request.ground_truth, top_k=request.top_k
    )
    return EvaluateResponse(**result.__dict__)
