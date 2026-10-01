from unittest.mock import patch

from app.services import vector_store
from app.services.vector_store import _fuse_rrf, _invalidate_bm25_cache, _tokenize, search


class FakeScoredPoint:
    def __init__(self, score: float, payload: dict):
        self.score = score
        self.payload = payload


class FakeQueryResult:
    def __init__(self, points: list[FakeScoredPoint]):
        self.points = points


class FakeScrollPoint:
    def __init__(self, payload: dict):
        self.payload = payload


class FakeClient:
    """Stands in for QdrantClient: dense hits come from query_points,
    keyword hits are computed by BM25Okapi (the real library, not mocked)
    over whatever scroll() returns."""

    def __init__(self, dense_points: list[FakeScoredPoint], scroll_points: list[FakeScrollPoint]):
        self.dense_points = dense_points
        self.scroll_points = scroll_points
        self.scroll_call_count = 0

    def query_points(self, **kwargs):
        return FakeQueryResult(self.dense_points)

    def scroll(self, **kwargs):
        self.scroll_call_count += 1
        return self.scroll_points, None


def _payload(document_id: str, chunk_index: int, text: str) -> dict:
    return {
        "document_id": document_id,
        "filename": f"{document_id}.md",
        "text": text,
        "page": None,
        "chunk_index": chunk_index,
    }


def setup_function():
    _invalidate_bm25_cache()


def teardown_function():
    _invalidate_bm25_cache()


def test_tokenize_lowercases_and_splits_on_non_alphanumerics():
    assert _tokenize("Expense Cap: 12%!") == ["expense", "cap", "12"]


def test_fuse_rrf_combines_rankings_from_multiple_lists():
    a = {"document_id": "docA", "chunk_index": 0, "text": "a"}
    b = {"document_id": "docB", "chunk_index": 0, "text": "b"}
    c = {"document_id": "docC", "chunk_index": 0, "text": "c"}

    # a ranks 1st in both lists; b only appears in the second list but at
    # rank 1 there; c trails in both. a should still come out on top, but
    # b should beat c despite c appearing in list one and b not.
    fused = _fuse_rrf([[a, c], [b, a]], limit=3)

    keys = [(r["document_id"], r["chunk_index"]) for r in fused]
    assert keys[0] == ("docA", 0)
    assert ("docB", 0) in keys
    assert len(fused) == 3


def test_fuse_rrf_respects_limit():
    chunks = [{"document_id": f"doc{i}", "chunk_index": 0, "text": str(i)} for i in range(5)]
    fused = _fuse_rrf([chunks], limit=2)
    assert len(fused) == 2


def test_keyword_search_surfaces_a_chunk_dense_search_missed():
    """The exact gs022 failure mode: a chunk holding a short numeric/clause
    fact ranks too low in dense similarity to make the pool, but contains
    an exact keyword match the dense ranking can't see past. Hybrid search
    must still surface it."""
    chunk_a = _payload("docA", 0, "Team roster assigns a sponsor and delivery lead for kickoff.")
    chunk_b = _payload("docB", 0, "Expense cap is set at twelve percent of professional fees.")
    chunk_c = _payload("docC", 0, "Liability under the agreement is bounded by total fees paid.")

    # Dense search "finds" A and C but never surfaces B at all, mirroring
    # B's chunk ranking outside the dense top_k pool in production.
    dense_points = [FakeScoredPoint(0.9, chunk_a), FakeScoredPoint(0.85, chunk_c)]
    scroll_points = [FakeScrollPoint(chunk_a), FakeScrollPoint(chunk_b), FakeScrollPoint(chunk_c)]
    fake_client = FakeClient(dense_points, scroll_points)

    with (
        patch.object(vector_store, "get_client", return_value=fake_client),
        patch.object(vector_store, "embed_query", return_value=[0.0]),
    ):
        results = search("expense cap", top_k=2)

    keys = {(r["document_id"], r["chunk_index"]) for r in results}
    assert ("docB", 0) in keys, "keyword match should rescue the chunk dense search missed"


def test_bm25_index_is_cached_until_invalidated():
    chunk = _payload("docA", 0, "some text")
    fake_client = FakeClient([], [FakeScrollPoint(chunk)])

    index1, _ = vector_store._load_bm25_index(fake_client)
    index2, _ = vector_store._load_bm25_index(fake_client)
    assert index1 is index2
    assert fake_client.scroll_call_count == 1

    _invalidate_bm25_cache()
    vector_store._load_bm25_index(fake_client)
    assert fake_client.scroll_call_count == 2
