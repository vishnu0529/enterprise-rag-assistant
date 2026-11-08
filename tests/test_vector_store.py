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
        self.last_query_filter = None

    def query_points(self, **kwargs):
        self.last_query_filter = kwargs.get("query_filter")
        return FakeQueryResult(self.dense_points)

    def scroll(self, **kwargs):
        self.scroll_call_count += 1
        return self.scroll_points, None


def _payload(document_id: str, chunk_index: int, text: str, owner_id: str | None = None) -> dict:
    return {
        "document_id": document_id,
        "filename": f"{document_id}.md",
        "text": text,
        "page": None,
        "chunk_index": chunk_index,
        "owner_id": owner_id,
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


def test_dense_search_filters_by_owner_id():
    """Scorecard item 11's per-tenant data isolation: a scoped search must
    tell Qdrant to filter server-side, not just trust the caller to only
    ask about its own chunks."""
    fake_client = FakeClient([FakeScoredPoint(0.9, _payload("docA", 0, "text"))], [])

    with patch.object(vector_store, "embed_query", return_value=[0.0]):
        vector_store._dense_search(fake_client, "q", limit=5, document_id=None, owner_id="alice")

    conditions = fake_client.last_query_filter.must
    assert any(c.key == "owner_id" and c.match.value == "alice" for c in conditions)


def test_dense_search_has_no_filter_when_owner_id_and_document_id_are_both_none():
    fake_client = FakeClient([], [])
    with patch.object(vector_store, "embed_query", return_value=[0.0]):
        vector_store._dense_search(fake_client, "q", limit=5, document_id=None, owner_id=None)

    assert fake_client.last_query_filter is None


def test_keyword_search_excludes_chunks_owned_by_a_different_tenant():
    # BM25's idf goes negative (and gets scored out entirely) when a term
    # appears in most/all of a tiny corpus, so the term that matters
    # ("expense") needs to stay a minority among enough filler docs to keep
    # a positive score, like test_keyword_search_surfaces_a_chunk_dense_search_missed.
    chunk_a = _payload("docA", 0, "Expense cap is set at twelve percent of fees.", owner_id="alice")
    chunk_b = _payload(
        "docB", 0, "Expense cap is set at twelve percent too, separately.", owner_id="bob"
    )
    fillers = [
        _payload(f"docFiller{i}", 0, text)
        for i, text in enumerate(
            [
                "Team roster assigns a sponsor and delivery lead for kickoff.",
                "Liability under the agreement is bounded by total fees paid.",
                "Standard payment terms are net thirty days from invoice date.",
            ]
        )
    ]
    fake_client = FakeClient(
        [],
        [FakeScrollPoint(chunk_a), FakeScrollPoint(chunk_b)]
        + [FakeScrollPoint(f) for f in fillers],
    )

    results = vector_store._keyword_search(
        fake_client, "expense cap", limit=10, document_id=None, owner_id="alice"
    )

    assert {r["document_id"] for r in results} == {"docA"}


def test_keyword_search_excludes_unowned_chunks_when_scoped_to_a_tenant():
    """Fail-closed: a chunk with no owner_id stamped (pre-isolation data,
    or an unconfigured-gate ingest) must not leak into a scoped search."""
    unowned = _payload("docA", 0, "expense cap details", owner_id=None)
    fake_client = FakeClient([], [FakeScrollPoint(unowned)])

    results = vector_store._keyword_search(
        fake_client, "expense cap", limit=10, document_id=None, owner_id="alice"
    )

    assert results == []


class FilteringFakeClient(FakeClient):
    """Unlike FakeClient, actually honors query_filter's owner_id/document_id
    conditions against its own payloads, so this test exercises real
    end-to-end isolation rather than relying on the Python-side keyword
    filter alone to carry the assertion."""

    def query_points(self, query_filter=None, **kwargs):
        self.last_query_filter = query_filter
        points = self.dense_points
        if query_filter:
            wanted = {c.key: c.match.value for c in query_filter.must}
            points = [p for p in points if all(p.payload.get(k) == v for k, v in wanted.items())]
        return FakeQueryResult(points)


def test_search_scopes_end_to_end_across_both_retrieval_methods():
    alice_chunk = _payload("docA", 0, "expense cap is twelve percent", owner_id="alice")
    bob_chunk = _payload("docB", 0, "expense cap is five percent", owner_id="bob")
    dense_points = [FakeScoredPoint(0.9, alice_chunk), FakeScoredPoint(0.8, bob_chunk)]
    scroll_points = [FakeScrollPoint(alice_chunk), FakeScrollPoint(bob_chunk)]
    fake_client = FilteringFakeClient(dense_points, scroll_points)

    with (
        patch.object(vector_store, "get_client", return_value=fake_client),
        patch.object(vector_store, "embed_query", return_value=[0.0]),
    ):
        results = search("expense cap", owner_id="alice")

    assert {r["document_id"] for r in results} == {"docA"}


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
