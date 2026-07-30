"""Hybrid search: combines the existing dense vector search
(app/services/vector_store.py) with a sparse BM25 index, fused via
Reciprocal Rank Fusion (RRF) — the standard technique for combining
differently-scaled retrieval scores without needing calibration.

The BM25 index is built in-memory from whatever's currently in Qdrant (via
vector_store.get_all_chunks()). Qdrant stays the single source of truth;
nothing is duplicated to a second persisted store. The cached index is
rebuilt the next time it's needed after invalidate() is called (wired into
the ingestion endpoint, so newly-uploaded documents show up in BM25 results).
"""

from rank_bm25 import BM25Okapi

from app.services import vector_store

_bm25_index: BM25Okapi | None = None
_bm25_chunks: list[dict] = []


def invalidate() -> None:
    """Call after ingesting a new document so the next search rebuilds the
    cached (no document_id filter) BM25 index against the current corpus."""
    global _bm25_index, _bm25_chunks
    _bm25_index = None
    _bm25_chunks = []


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def _ensure_cached_index() -> None:
    global _bm25_index, _bm25_chunks
    if _bm25_index is not None:
        return
    chunks = vector_store.get_all_chunks()
    _bm25_chunks = chunks
    tokenized = [_tokenize(c["text"]) for c in chunks]
    _bm25_index = BM25Okapi(tokenized) if tokenized else None


def _bm25_search(query: str, top_k: int, document_id: str | None) -> list[dict]:
    if document_id:
        # Filtered searches don't hit the shared cache — cheap enough to
        # rebuild for a single document at demo scale, and avoids the
        # complexity of a per-document cache.
        chunks = vector_store.get_all_chunks(document_id=document_id)
        if not chunks:
            return []
        index = BM25Okapi([_tokenize(c["text"]) for c in chunks])
        scores = index.get_scores(_tokenize(query))
    else:
        _ensure_cached_index()
        if _bm25_index is None or not _bm25_chunks:
            return []
        chunks = _bm25_chunks
        scores = _bm25_index.get_scores(_tokenize(query))

    ranked = sorted(zip(chunks, scores, strict=True), key=lambda pair: pair[1], reverse=True)[
        :top_k
    ]
    return [{**chunk, "score": float(score)} for chunk, score in ranked]


def _rrf_key(chunk: dict) -> tuple:
    return (chunk["document_id"], chunk["chunk_index"])


def search_hybrid(
    query: str,
    top_k: int = 20,
    document_id: str | None = None,
    rrf_k: int = 60,
) -> list[dict]:
    """Returns up to top_k chunks ranked by Reciprocal Rank Fusion of dense
    vector search and sparse BM25 search: score = sum(1 / (rrf_k + rank))
    across whichever lists a chunk appears in."""
    pool = max(top_k * 2, 20)
    vector_results = vector_store.search(query, top_k=pool, document_id=document_id)
    bm25_results = _bm25_search(query, pool, document_id)

    rrf_scores: dict = {}
    chunk_by_key: dict = {}

    for rank, chunk in enumerate(vector_results):
        key = _rrf_key(chunk)
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)
        chunk_by_key[key] = chunk

    for rank, chunk in enumerate(bm25_results):
        key = _rrf_key(chunk)
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)
        chunk_by_key.setdefault(key, chunk)

    ranked_keys = sorted(rrf_scores, key=lambda k: rrf_scores[k], reverse=True)[:top_k]
    results = []
    for key in ranked_keys:
        chunk = dict(chunk_by_key[key])
        chunk["score"] = rrf_scores[key]
        results.append(chunk)
    return results
