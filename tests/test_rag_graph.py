from contextlib import ExitStack
from unittest.mock import patch

from app.services.llm_client import LLMResult
from app.services.rag_graph import (
    DEFAULT_MAX_RETRIES,
    NO_DOCUMENTS_ANSWER,
    answer_question_agentic,
)

SAMPLE_CHUNKS = [
    {
        "score": 0.9,
        "document_id": "doc-1",
        "filename": "handbook.md",
        "text": "Employees get 25 days of annual leave.",
        "page": None,
        "chunk_index": 0,
    },
]

FAKE_LLM_RESULT = LLMResult(
    text="You get 25 days of annual leave. [Source 1]", prompt_tokens=100, completion_tokens=15
)

DEFAULTS = {
    "search": lambda *a, **k: SAMPLE_CHUNKS,
    "call_llm": lambda *a, **k: FAKE_LLM_RESULT,
    "score_faithfulness": lambda *a, **k: 0.9,
    "call_llm_json": lambda *a, **k: {
        "sub_queries": ["annual leave days"],
        "top_k": 4,
        "reasoning": "direct lookup",
    },
    "recall_relevant_memory": lambda *a, **k: [],
    "remember_exchange": lambda *a, **k: None,
}


def apply_patches(stack: ExitStack, **overrides) -> dict:
    """Patches every module-level name rag_graph's nodes call out to, with
    sane defaults overridable per test. Returns the mocks by name so tests
    can assert on call counts/args."""
    values = {**DEFAULTS, **overrides}
    return {
        name: stack.enter_context(patch(f"app.services.rag_graph.{name}", side_effect=fn))
        for name, fn in values.items()
    }


def test_no_documents_short_circuits_without_calling_the_llm():
    with ExitStack() as stack:
        mocks = apply_patches(stack, search=lambda *a, **k: [])
        result = answer_question_agentic("Anything?")

    assert result["answer"] == NO_DOCUMENTS_ANSWER
    assert result["citations"] == []
    mocks["call_llm"].assert_not_called()


def test_strategist_runs_before_retrieval_and_plan_is_returned():
    with ExitStack() as stack:
        mocks = apply_patches(stack)
        result = answer_question_agentic("How many annual leave days?")

    assert result["sub_queries"] == ["annual leave days"]
    assert result["strategist_reasoning"] == "direct lookup"
    mocks["call_llm_json"].assert_called_once()  # strategist ran exactly once (no retry needed)


def test_answers_without_retry_when_faithful_first_time():
    with ExitStack() as stack:
        mocks = apply_patches(stack, score_faithfulness=lambda *a, **k: 0.9)
        result = answer_question_agentic("How many annual leave days?")

    assert result["answer"] == FAKE_LLM_RESULT.text
    assert result["faithfulness_score"] == 0.9
    assert result["retries"] == 0
    mocks["call_llm"].assert_called_once()  # drafting agent ran exactly once
    mocks["call_llm_json"].assert_called_once()  # strategist ran exactly once, not re-planning


def test_retries_send_strategist_back_to_replan_until_it_passes():
    scores = iter([0.3, 0.3, 0.9])
    with ExitStack() as stack:
        mocks = apply_patches(stack, score_faithfulness=lambda *a, **k: next(scores))
        result = answer_question_agentic("How many annual leave days?")

    assert result["retries"] == 2
    assert result["faithfulness_score"] == 0.9
    assert mocks["call_llm"].call_count == 3  # drafting agent: 1 initial + 2 retries
    assert mocks["call_llm_json"].call_count == 3  # strategist: 1 initial + 2 re-plans


def test_stops_at_max_retries_even_if_never_faithful():
    with ExitStack() as stack:
        mocks = apply_patches(stack, score_faithfulness=lambda *a, **k: 0.1)
        result = answer_question_agentic("How many annual leave days?")

    assert result["retries"] == DEFAULT_MAX_RETRIES
    assert mocks["call_llm"].call_count == DEFAULT_MAX_RETRIES + 1  # doesn't loop forever


def test_multi_hop_sub_queries_are_merged_and_deduped():
    chunk_a = {**SAMPLE_CHUNKS[0], "score": 0.6}
    chunk_b = {
        "score": 0.8,
        "document_id": "doc-1",
        "filename": "handbook.md",
        "text": "Leave rises to 30 days after 5 years.",
        "page": None,
        "chunk_index": 1,
    }
    duplicate_of_a_higher_score = {
        **chunk_a,
        "score": 0.95,
    }  # same (document_id, chunk_index) as chunk_a

    def fake_search(query, top_k=None, document_id=None):
        return {
            "leave policy": [chunk_a, chunk_b],
            "leave increase over time": [duplicate_of_a_higher_score],
        }[query]

    with ExitStack() as stack:
        mocks = apply_patches(
            stack,
            search=fake_search,
            call_llm_json=lambda *a, **k: {
                "sub_queries": ["leave policy", "leave increase over time"],
                "top_k": 4,
                "reasoning": "comparison across two sub-topics",
            },
        )
        result = answer_question_agentic("How does leave work and how does it change over time?")

    # 3 chunks retrieved across 2 sub-queries, but chunk_a and its duplicate share a
    # (document_id, chunk_index) key — deduped down to 2, keeping the higher score.
    assert len(result["contexts"]) == 2
    assert mocks["search"].call_count == 2


def test_memory_skipped_when_no_user_id():
    with ExitStack() as stack:
        mocks = apply_patches(stack)
        result = answer_question_agentic("How many annual leave days?", user_id=None)

    assert result["used_memory"] is False
    mocks["recall_relevant_memory"].assert_not_called()
    mocks["remember_exchange"].assert_not_called()


def test_memory_recalled_and_remembered_when_user_id_given():
    past = [{"question": "What's the sick leave policy?", "answer": "10 days.", "score": 0.8}]
    with ExitStack() as stack:
        mocks = apply_patches(stack, recall_relevant_memory=lambda *a, **k: past)
        result = answer_question_agentic(
            "How many annual leave days?", user_id="user-42", session_id="session-1"
        )

    assert result["used_memory"] is True
    mocks["recall_relevant_memory"].assert_called_once()
    mocks["remember_exchange"].assert_called_once()
    _, kwargs = mocks["remember_exchange"].call_args
    assert kwargs["user_id"] == "user-42"
    assert kwargs["session_id"] == "session-1"


def _raise_call_llm(*a, **k):
    raise RuntimeError("simulated quota/network failure")


def test_llm_failure_in_draft_returns_clean_message_without_retry_or_memory_write():
    """Regression test: draft_node's call_llm previously had no exception
    handling at all (unlike every other LLM call in the graph), so a real
    quota/network error surfaced as a raw 500 all the way through the API —
    caught via manual testing against the live Render deployment, not by
    this suite, since it existed before this test did."""
    with ExitStack() as stack:
        mocks = apply_patches(stack, call_llm=_raise_call_llm)
        result = answer_question_agentic("How many annual leave days?", user_id="user-42")

    assert "RuntimeError" in result["answer"]
    assert result["citations"] == []
    assert result["retries"] == 0  # didn't burn retries on a failure retrying can't fix
    assert result["faithfulness_score"] is None  # critique never called score_faithfulness
    assert mocks["call_llm"].call_count == 1  # failed once, didn't retry
    mocks["remember_exchange"].assert_not_called()  # didn't pollute memory with an error message
