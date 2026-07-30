from unittest.mock import patch

from app.services.llm_client import LLMResult
from app.services.rag_chain import answer_question, build_context

SAMPLE_CHUNKS = [
    {
        "score": 0.9,
        "document_id": "doc-1",
        "filename": "handbook.md",
        "text": "Employees get 25 days of annual leave.",
        "page": None,
        "chunk_index": 0,
    },
    {
        "score": 0.7,
        "document_id": "doc-1",
        "filename": "handbook.md",
        "text": "Leave rises to 30 days after 5 years.",
        "page": None,
        "chunk_index": 1,
    },
]


def test_build_context_includes_source_labels_and_locations():
    context = build_context(SAMPLE_CHUNKS)

    assert "[Source 1 — handbook.md" in context
    assert "[Source 2 — handbook.md" in context
    assert "25 days of annual leave" in context


def test_build_context_uses_page_number_when_present():
    chunks = [{**SAMPLE_CHUNKS[0], "page": 3}]

    context = build_context(chunks)

    assert "p.3" in context


def test_answer_question_with_no_retrieved_chunks_short_circuits():
    # No history -> rewrite_query's no-op fast path applies, no LLM call
    # made for rewriting; retrieve() is mocked directly (the pipeline's
    # unified entry point) rather than the individual hybrid/rerank stages.
    with patch("app.services.rag_chain.retrieve", return_value=[]):
        result = answer_question("Anything?")

    assert result["citations"] == []
    assert result["prompt_tokens"] == 0
    assert "don't have any ingested documents" in result["answer"]


def test_answer_question_returns_citations_and_metrics():
    fake_llm_result = LLMResult(
        text="Employees get 25 days, rising to 30 after 5 years. [Source 1]",
        prompt_tokens=120,
        completion_tokens=18,
    )

    with (
        patch("app.services.rag_chain.retrieve", return_value=SAMPLE_CHUNKS),
        patch("app.services.rag_chain.call_llm", return_value=fake_llm_result) as mock_call_llm,
    ):
        result = answer_question("How many annual leave days?")

    assert result["answer"] == fake_llm_result.text
    assert len(result["citations"]) == 2
    assert result["citations"][0].filename == "handbook.md"
    assert result["prompt_tokens"] == 120
    assert result["completion_tokens"] == 18
    assert result["latency_ms"] >= 0
    assert result["contexts"] == [c["text"] for c in SAMPLE_CHUNKS]
    mock_call_llm.assert_called_once()


def test_answer_question_passes_history_into_prompt():
    fake_llm_result = LLMResult(text="ok", prompt_tokens=1, completion_tokens=1)
    history = [{"role": "user", "content": "earlier question"}]

    with (
        # History is present, so rewrite_query would otherwise attempt a
        # real LLM call — mock it directly to keep this test fast and
        # network-free (query_rewriter's own no-op/fallback behavior is
        # covered by tests/test_query_rewriter.py).
        patch("app.services.rag_chain.rewrite_query", return_value="follow up question"),
        patch("app.services.rag_chain.retrieve", return_value=SAMPLE_CHUNKS),
        patch("app.services.rag_chain.call_llm", return_value=fake_llm_result) as mock_call_llm,
    ):
        answer_question("follow up question", history=history)

    _, user_prompt = mock_call_llm.call_args[0]
    assert "earlier question" in user_prompt


def test_retrieve_disables_hybrid_and_reranking_gracefully():
    """When both Phase 2 flags are off, retrieve() falls back to plain
    vector search — the prior round's behavior — rather than breaking."""
    from app.core.config import settings
    from app.services.rag_chain import retrieve

    original_hybrid, original_rerank = (
        settings.ENABLE_HYBRID_SEARCH,
        settings.ENABLE_RERANKING,
    )
    settings.ENABLE_HYBRID_SEARCH = False
    settings.ENABLE_RERANKING = False
    try:
        with patch("app.services.rag_chain.search", return_value=SAMPLE_CHUNKS) as mock_search:
            result = retrieve("How many annual leave days?", top_k=2)
    finally:
        settings.ENABLE_HYBRID_SEARCH = original_hybrid
        settings.ENABLE_RERANKING = original_rerank

    mock_search.assert_called_once()
    assert result == SAMPLE_CHUNKS
