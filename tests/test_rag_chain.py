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
    with patch("app.services.rag_chain.search", return_value=[]):
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
        patch("app.services.rag_chain.search", return_value=SAMPLE_CHUNKS),
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
        patch("app.services.rag_chain.search", return_value=SAMPLE_CHUNKS),
        patch("app.services.rag_chain.call_llm", return_value=fake_llm_result) as mock_call_llm,
    ):
        answer_question("follow up question", history=history)

    _, user_prompt = mock_call_llm.call_args[0]
    assert "earlier question" in user_prompt
