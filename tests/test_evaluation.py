from unittest.mock import patch

import pytest

from app.services.evaluation import (
    score_answer_relevancy,
    score_context_precision,
    score_context_recall,
    score_faithfulness,
)


def test_score_faithfulness_all_claims_supported():
    fake_response = {
        "claims": [
            {"claim": "A", "supported": True},
            {"claim": "B", "supported": True},
        ]
    }
    with patch("app.services.evaluation.call_llm_json", return_value=fake_response):
        score = score_faithfulness("A and B", ["context supporting A and B"])

    assert score == 1.0


def test_score_faithfulness_partial_hallucination():
    fake_response = {
        "claims": [
            {"claim": "A", "supported": True},
            {"claim": "fabricated claim", "supported": False},
        ]
    }
    with patch("app.services.evaluation.call_llm_json", return_value=fake_response):
        score = score_faithfulness("A and fabricated claim", ["context supporting A"])

    assert score == 0.5


def test_score_faithfulness_no_context_returns_zero():
    score = score_faithfulness("some answer", [])
    assert score == 0.0


def test_score_faithfulness_handles_judge_failure_gracefully():
    with patch("app.services.evaluation.call_llm_json", side_effect=ValueError("bad json")):
        score = score_faithfulness("answer", ["context"])

    assert score == 0.0


def test_score_answer_relevancy_high_for_on_topic_questions():
    fake_response = {
        "questions": [
            "How many annual leave days do employees get?",
            "What is the leave allowance?",
        ]
    }
    with (
        patch("app.services.evaluation.call_llm_json", return_value=fake_response),
        patch(
            "app.services.evaluation.embed_texts",
            side_effect=lambda texts: [[1.0, 0.0] for _ in texts],
        ),
    ):
        score = score_answer_relevancy("How many annual leave days do employees get?", "25 days.")

    assert score == pytest.approx(1.0)


def test_score_answer_relevancy_no_generated_questions_returns_zero():
    with patch("app.services.evaluation.call_llm_json", return_value={"questions": []}):
        score = score_answer_relevancy("question", "answer")

    assert score == 0.0


def test_score_context_precision_ranks_relevant_chunks_first():
    with patch(
        "app.services.evaluation.call_llm_json",
        side_effect=[{"relevant": True}, {"relevant": False}],
    ):
        score = score_context_precision("q", ["relevant chunk", "irrelevant chunk"])

    assert score == 1.0


def test_score_context_precision_no_relevant_chunks_is_zero():
    with patch("app.services.evaluation.call_llm_json", return_value={"relevant": False}):
        score = score_context_precision("q", ["chunk 1", "chunk 2"])

    assert score == 0.0


def test_score_context_precision_empty_contexts_is_zero():
    assert score_context_precision("q", []) == 0.0


def test_score_context_recall_all_statements_attributed():
    fake_response = {
        "statements": [
            {"statement": "X", "attributed": True},
            {"statement": "Y", "attributed": True},
        ]
    }
    with patch("app.services.evaluation.call_llm_json", return_value=fake_response):
        score = score_context_recall("X and Y", ["context with X and Y"])

    assert score == 1.0


def test_score_context_recall_without_ground_truth_is_zero():
    assert score_context_recall("", ["some context"]) == 0.0
