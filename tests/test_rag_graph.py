from contextlib import ExitStack
from unittest.mock import patch

import pytest

import tests.test_rag_graph as _this_module
from app.services.llm_client import LLMResult
from app.services.rag_graph import (
    DEFAULT_MAX_RETRIES,
    NO_DOCUMENTS_ANSWER,
    answer_question_agentic,
    resume_approval,
)


@pytest.fixture(autouse=True)
def _unique_thread_per_test(request, monkeypatch):
    """thread_id is session-scoped now (see rag_graph.py, durable
    checkpointing only means anything if a resumed run continues the same
    conversation). Real callers always pass a fresh UUID session_id per
    conversation (chat.py), so this collision can't happen in production,
    but most of these tests predate that change and never pass session_id,
    so without this they'd all silently share one "no-session" thread and
    resume each other's checkpoints instead of starting fresh. Give every
    test its own thread via its own name; a test that explicitly passes
    session_id (e.g. the approval-gate resume tests, which need two calls
    on the *same* thread) is left alone."""

    def _auto_session_id(fn):
        def wrapper(*args, **kwargs):
            kwargs.setdefault("session_id", request.node.name)
            return fn(*args, **kwargs)

        return wrapper

    monkeypatch.setattr(
        _this_module, "answer_question_agentic", _auto_session_id(answer_question_agentic)
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


def test_cache_tokens_are_surfaced_in_the_final_result():
    cached_llm_result = LLMResult(
        text="You get 25 days of annual leave. [Source 1]",
        prompt_tokens=100,
        completion_tokens=15,
        cache_creation_tokens=50,
        cache_read_tokens=200,
    )
    with ExitStack() as stack:
        apply_patches(stack, call_llm=lambda *a, **k: cached_llm_result)
        result = answer_question_agentic("How many annual leave days?")

    assert result["cache_creation_tokens"] == 50
    assert result["cache_read_tokens"] == 200


def test_cache_tokens_accumulate_across_retries():
    results = iter(
        [
            LLMResult(text="draft 1", prompt_tokens=10, completion_tokens=5, cache_read_tokens=100),
            LLMResult(text="draft 2", prompt_tokens=10, completion_tokens=5, cache_read_tokens=100),
            LLMResult(text="draft 3", prompt_tokens=10, completion_tokens=5, cache_read_tokens=100),
        ]
    )
    scores = iter([0.3, 0.3, 0.9])
    with ExitStack() as stack:
        apply_patches(
            stack,
            call_llm=lambda *a, **k: next(results),
            score_faithfulness=lambda *a, **k: next(scores),
        )
        result = answer_question_agentic("How many annual leave days?")

    assert result["retries"] == 2
    assert result["cache_read_tokens"] == 300  # accumulated across 1 initial + 2 retries


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
    # (document_id, chunk_index) key, deduped down to 2, keeping the higher score.
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


UNCITED_LLM_RESULT = LLMResult(
    text="You get 25 days of annual leave.", prompt_tokens=100, completion_tokens=12
)


def test_missing_citation_triggers_a_retry_even_when_faithful():
    with ExitStack() as stack:
        mocks = apply_patches(
            stack,
            call_llm=lambda *a, **k: UNCITED_LLM_RESULT,
            score_faithfulness=lambda *a, **k: 0.9,
        )
        result = answer_question_agentic("How many annual leave days?")

    # Faithfulness alone would have passed on attempt 1; it's the missing
    # [Source N] marker that forces the retry loop to run to its cap.
    assert result["retries"] == DEFAULT_MAX_RETRIES
    assert mocks["call_llm"].call_count == DEFAULT_MAX_RETRIES + 1


def test_escalation_banner_added_when_retries_exhausted_still_ungrounded():
    with ExitStack() as stack:
        apply_patches(stack, score_faithfulness=lambda *a, **k: 0.1)
        result = answer_question_agentic("How many annual leave days?")

    assert result["escalated"] is True
    assert "bid-director review" in result["answer"]
    assert FAKE_LLM_RESULT.text in result["answer"]  # original answer still present, not replaced


def test_escalation_banner_added_when_retries_exhausted_still_uncited():
    with ExitStack() as stack:
        apply_patches(stack, call_llm=lambda *a, **k: UNCITED_LLM_RESULT)
        result = answer_question_agentic("How many annual leave days?")

    assert result["escalated"] is True
    assert "no source citation" in result["answer"]


def test_no_escalation_when_faithful_and_cited_first_time():
    with ExitStack() as stack:
        apply_patches(stack)
        result = answer_question_agentic("How many annual leave days?")

    assert result["escalated"] is False
    assert "bid-director review" not in result["answer"]


def test_refusal_answers_are_not_flagged_for_missing_citation():
    refusal_result = LLMResult(
        text="The corpus doesn't cover this, it needs sign-off from the bid director.",
        prompt_tokens=80,
        completion_tokens=20,
    )
    with ExitStack() as stack:
        mocks = apply_patches(
            stack, call_llm=lambda *a, **k: refusal_result, score_faithfulness=lambda *a, **k: 1.0
        )
        result = answer_question_agentic("What's our litigation-support day rate?")

    assert result["escalated"] is False
    assert mocks["call_llm"].call_count == 1  # no retry burned on a correct refusal


def test_llm_failure_in_draft_returns_clean_message_without_retry_or_memory_write():
    """Regression test: draft_node's call_llm previously had no exception
    handling at all (unlike every other LLM call in the graph), so a real
    quota/network error surfaced as a raw 500 all the way through the API,
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


PRICEY_LLM_RESULT = LLMResult(
    text="The day rate for a Senior Consultant is £1,050. [Source 1]",
    prompt_tokens=100,
    completion_tokens=15,
)


def test_approval_not_required_by_default_even_with_a_price_in_the_answer():
    with ExitStack() as stack:
        apply_patches(stack, call_llm=lambda *a, **k: PRICEY_LLM_RESULT)
        result = answer_question_agentic(
            "What is the day rate?", session_id="test-approval-default"
        )

    assert result["pending_approval"] is False
    assert result["approval_status"] == "not_required"
    assert result["answer"] == PRICEY_LLM_RESULT.text


def test_approval_required_pauses_on_a_priced_answer():
    with ExitStack() as stack:
        apply_patches(stack, call_llm=lambda *a, **k: PRICEY_LLM_RESULT)
        result = answer_question_agentic(
            "What is the day rate?", session_id="test-approval-pause", require_approval=True
        )

    assert result["pending_approval"] is True
    assert result["answer"] is None  # not released yet
    assert result["draft_answer"] == PRICEY_LLM_RESULT.text
    assert "monetary figure" in result["approval_reason"]


def test_approval_required_does_not_pause_without_a_price():
    with ExitStack() as stack:
        apply_patches(stack)  # default FAKE_LLM_RESULT has no £ figure
        result = answer_question_agentic(
            "How many annual leave days?",
            session_id="test-approval-no-price",
            require_approval=True,
        )

    assert result["pending_approval"] is False
    assert result["approval_status"] == "not_required"


def test_approval_gate_exempts_refusals_even_with_require_approval():
    refusal = LLMResult(
        text="The corpus doesn't cover this, it needs sign-off from the bid director.",
        prompt_tokens=80,
        completion_tokens=20,
    )
    with ExitStack() as stack:
        apply_patches(stack, call_llm=lambda *a, **k: refusal)
        result = answer_question_agentic(
            "What's our litigation rate?", session_id="test-approval-refusal", require_approval=True
        )

    assert result["pending_approval"] is False


def test_resume_approval_approved_releases_the_original_answer():
    session_id = "test-approval-approve"
    with ExitStack() as stack:
        apply_patches(stack, call_llm=lambda *a, **k: PRICEY_LLM_RESULT)
        paused = answer_question_agentic(
            "What is the day rate?", session_id=session_id, require_approval=True
        )
        assert paused["pending_approval"] is True

        result = resume_approval(session_id, approved=True)

    assert result["pending_approval"] is False
    assert result["approval_status"] == "approved"
    assert result["answer"] == PRICEY_LLM_RESULT.text


def test_resume_approval_rejected_replaces_the_answer_with_a_banner():
    session_id = "test-approval-reject"
    with ExitStack() as stack:
        apply_patches(stack, call_llm=lambda *a, **k: PRICEY_LLM_RESULT)
        paused = answer_question_agentic(
            "What is the day rate?", session_id=session_id, require_approval=True
        )
        assert paused["pending_approval"] is True

        result = resume_approval(session_id, approved=False, reason="Rate under renegotiation")

    assert result["pending_approval"] is False
    assert result["approval_status"] == "rejected"
    assert "Not released" in result["answer"]
    assert "Rate under renegotiation" in result["answer"]
    assert PRICEY_LLM_RESULT.text not in result["answer"]


def test_resume_approval_raises_when_nothing_is_actually_paused():
    """A thread whose most recent turn already finished, whether or not
    that turn ever paused, must reject a resume attempt. Without the
    interrupts check in resume_approval(), Command(resume=...) on a
    finished thread doesn't error: LangGraph just replays the checkpoint at
    END and hands back the old answer as if the resume "worked", which
    would let a client silently re-post the same answer for an unrelated
    or already-resolved turn."""
    session_id = "test-approval-nothing-pending"
    with ExitStack() as stack:
        apply_patches(
            stack,
            call_llm=lambda *a, **k: LLMResult(
                text="No price here. [Source 1]", prompt_tokens=1, completion_tokens=1
            ),
        )
        finished = answer_question_agentic(
            "How many annual leave days?", session_id=session_id, require_approval=False
        )
        assert finished["pending_approval"] is False

        with pytest.raises(KeyError):
            resume_approval(session_id, approved=True)


def test_resume_approval_raises_for_a_session_that_never_existed():
    with pytest.raises(KeyError):
        resume_approval("session-that-never-ran-anything", approved=True)
