from unittest.mock import patch

from app.services import hybrid_search


def _chunk(doc_id: str, idx: int, text: str) -> dict:
    return {
        "document_id": doc_id,
        "chunk_index": idx,
        "filename": "test.md",
        "page": None,
        "text": text,
        "score": 0.0,
    }


def test_search_hybrid_favors_consensus_top_result():
    """A chunk ranked #1 by both retrieval methods should outrank a chunk
    that's only strong in one — the core claim of Reciprocal Rank Fusion."""
    chunk_p = _chunk("d1", 0, "P — top in both lists")
    chunk_q = _chunk("d1", 1, "Q — good in both, but never #1")
    chunk_r = _chunk("d1", 2, "R — vector only")
    chunk_s = _chunk("d1", 3, "S — bm25 only")

    vector_results = [chunk_p, chunk_q, chunk_r]  # ranks 0, 1, 2
    bm25_results = [chunk_p, chunk_s, chunk_q]  # ranks 0, 1, 2

    with (
        patch("app.services.hybrid_search.vector_store.search", return_value=vector_results),
        patch("app.services.hybrid_search._bm25_search", return_value=bm25_results),
    ):
        results = hybrid_search.search_hybrid("test query", top_k=4)

    ordering = [(r["document_id"], r["chunk_index"]) for r in results]
    assert ordering == [("d1", 0), ("d1", 1), ("d1", 3), ("d1", 2)]
    # P appears in both lists at rank 0 -> highest fused score
    assert results[0]["score"] > results[1]["score"]


def test_search_hybrid_deduplicates_chunks_present_in_both_lists():
    chunk_a = _chunk("d1", 0, "shared chunk")
    with (
        patch("app.services.hybrid_search.vector_store.search", return_value=[chunk_a]),
        patch("app.services.hybrid_search._bm25_search", return_value=[chunk_a]),
    ):
        results = hybrid_search.search_hybrid("q", top_k=10)

    assert len(results) == 1


def test_search_hybrid_respects_top_k():
    chunks = [_chunk("d1", i, f"chunk {i}") for i in range(5)]
    with (
        patch("app.services.hybrid_search.vector_store.search", return_value=chunks),
        patch("app.services.hybrid_search._bm25_search", return_value=[]),
    ):
        results = hybrid_search.search_hybrid("q", top_k=2)

    assert len(results) == 2


def test_invalidate_clears_cached_index():
    hybrid_search._bm25_index = object()
    hybrid_search._bm25_chunks = [_chunk("d1", 0, "x")]

    hybrid_search.invalidate()

    assert hybrid_search._bm25_index is None
    assert hybrid_search._bm25_chunks == []
