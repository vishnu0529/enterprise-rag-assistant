from unittest.mock import patch

from app.routers.evaluate import EvaluateRequest, evaluate
from app.services.evaluation import EvalResult


def test_evaluate_router_scopes_retrieval_to_the_authenticated_user():
    """The router resolves an identity via require_api_key but was passing
    it nowhere — evaluate_question() ran retrieval unscoped, so a
    tenant-scoped key hitting /evaluate could retrieve another tenant's
    documents through this endpoint even though /chat and /documents are
    isolated. owner_id must reach evaluate_question."""
    fake_result = EvalResult(
        question="q",
        answer="a",
        faithfulness=1.0,
        answer_relevancy=1.0,
        context_precision=1.0,
        context_recall=0.0,
        latency_ms=1.0,
        prompt_tokens=1,
        completion_tokens=1,
    )
    with patch("app.routers.evaluate.evaluate_question", return_value=fake_result) as mock_evaluate:
        evaluate(EvaluateRequest(question="q"), user_id="alice")

    assert mock_evaluate.call_args.kwargs["owner_id"] == "alice"
