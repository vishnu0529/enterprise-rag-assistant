from unittest.mock import MagicMock, patch

from app.services.reranker import rerank

CANDIDATES = [
    {"document_id": "d1", "chunk_index": 0, "filename": "f.md", "page": None, "text": "a"},
    {"document_id": "d1", "chunk_index": 1, "filename": "f.md", "page": None, "text": "b"},
    {"document_id": "d1", "chunk_index": 2, "filename": "f.md", "page": None, "text": "c"},
]


def test_rerank_orders_by_cross_encoder_score_descending():
    fake_model = MagicMock()
    fake_model.predict.return_value = [0.1, 9.9, 5.0]  # scores for a, b, c

    with patch("app.services.reranker._get_reranker", return_value=fake_model):
        results = rerank("query", CANDIDATES, top_k=3)

    assert [r["text"] for r in results] == ["b", "c", "a"]
    assert results[0]["score"] == 9.9


def test_rerank_respects_top_k():
    fake_model = MagicMock()
    fake_model.predict.return_value = [3.0, 1.0, 2.0]

    with patch("app.services.reranker._get_reranker", return_value=fake_model):
        results = rerank("query", CANDIDATES, top_k=2)

    assert len(results) == 2
    assert [r["text"] for r in results] == ["a", "c"]


def test_rerank_empty_candidates_returns_empty_without_loading_model():
    with patch("app.services.reranker._get_reranker") as mock_get_model:
        results = rerank("query", [], top_k=5)

    assert results == []
    mock_get_model.assert_not_called()


def test_rerank_passes_query_chunk_pairs_to_model():
    fake_model = MagicMock()
    fake_model.predict.return_value = [1.0, 2.0, 3.0]

    with patch("app.services.reranker._get_reranker", return_value=fake_model):
        rerank("my query", CANDIDATES, top_k=3)

    pairs_passed = fake_model.predict.call_args[0][0]
    assert pairs_passed == [("my query", "a"), ("my query", "b"), ("my query", "c")]
