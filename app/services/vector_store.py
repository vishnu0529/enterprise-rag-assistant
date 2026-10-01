import re

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from rank_bm25 import BM25Okapi

from app.core.config import settings
from app.services.embeddings import embed_query, embed_texts, embedding_dim

_client: QdrantClient | None = None

# Dense embeddings (BAAI/bge-small-en-v1.5 by default) underrank short,
# numeric, clause-style facts ("capped at 12% of professional fees")
# against topically-similar prose, because the query shares more surface
# vocabulary with a document's title/heading than with the terse clause
# itself. A keyword/BM25 pass catches exactly those cases, so search()
# fuses both rankings via reciprocal rank fusion (RRF) rather than relying
# on dense similarity alone. See docs/EVALUATION.md's gs022 section.
_RRF_K = 60  # standard RRF damping constant; not tuned, just the usual default
_TOKEN_RE = re.compile(r"[a-z0-9]+")

_bm25_index: BM25Okapi | None = None
_bm25_payloads: list[dict] | None = None


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def get_client() -> QdrantClient:
    """Embedded local mode by default (no server needed); set QDRANT_URL to
    point at a real Qdrant service (e.g. the one in docker-compose) instead."""
    global _client
    if _client is None:
        if settings.QDRANT_URL:
            _client = QdrantClient(url=settings.QDRANT_URL)
        else:
            _client = QdrantClient(path=settings.QDRANT_LOCAL_PATH)
        _ensure_collection(_client)
    return _client


def _ensure_collection(client: QdrantClient) -> None:
    existing = [c.name for c in client.get_collections().collections]
    if settings.QDRANT_COLLECTION not in existing:
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=qmodels.VectorParams(
                size=embedding_dim(), distance=qmodels.Distance.COSINE
            ),
        )


def upsert_chunks(chunks: list[dict]) -> int:
    """chunks: list of {chunk_id, document_id, filename, text, page, chunk_index}"""
    client = get_client()
    texts = [c["text"] for c in chunks]
    vectors = embed_texts(texts)
    points = [
        qmodels.PointStruct(
            id=c["chunk_id"],
            vector=vector,
            payload={
                "document_id": c["document_id"],
                "filename": c["filename"],
                "text": c["text"],
                "page": c.get("page"),
                "chunk_index": c["chunk_index"],
            },
        )
        for c, vector in zip(chunks, vectors, strict=True)
    ]
    client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)
    _invalidate_bm25_cache()
    return len(points)


def _payload_to_chunk(payload: dict) -> dict:
    return {
        "document_id": payload["document_id"],
        "filename": payload["filename"],
        "text": payload["text"],
        "page": payload.get("page"),
        "chunk_index": payload["chunk_index"],
    }


def _dense_search(
    client: QdrantClient, query: str, limit: int, document_id: str | None
) -> list[dict]:
    query_vector = embed_query(query)
    query_filter = None
    if document_id:
        query_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="document_id", match=qmodels.MatchValue(value=document_id)
                )
            ]
        )
    results = client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=query_vector,
        limit=limit,
        query_filter=query_filter,
    ).points
    return [{"score": r.score, **_payload_to_chunk(r.payload)} for r in results]


def _invalidate_bm25_cache() -> None:
    global _bm25_index, _bm25_payloads
    _bm25_index = None
    _bm25_payloads = None


def _load_bm25_index(client: QdrantClient) -> tuple[BM25Okapi | None, list[dict]]:
    """Scans the whole collection and builds an in-memory BM25 index,
    cached until the next upsert/delete/reset. Qdrant itself has no
    keyword-search mode in local/embedded mode, and this corpus is small
    enough (tens to low hundreds of chunks) that a full scan per rebuild
    is cheap; a corpus too large for that would need Qdrant's native
    sparse-vector support instead of this."""
    global _bm25_index, _bm25_payloads
    if _bm25_index is None:
        points, _ = client.scroll(
            collection_name=settings.QDRANT_COLLECTION, limit=10_000, with_payload=True
        )
        _bm25_payloads = [p.payload for p in points]
        tokenized = [_tokenize(p["text"]) for p in _bm25_payloads]
        _bm25_index = BM25Okapi(tokenized) if tokenized else None
    return _bm25_index, _bm25_payloads


def _keyword_search(
    client: QdrantClient, query: str, limit: int, document_id: str | None
) -> list[dict]:
    index, payloads = _load_bm25_index(client)
    if index is None:
        return []
    scores = index.get_scores(_tokenize(query))
    ranked = sorted(range(len(payloads)), key=lambda i: scores[i], reverse=True)
    results = []
    for i in ranked:
        if scores[i] <= 0:
            break  # `ranked` is sorted descending, so every later score is <= 0 too
        payload = payloads[i]
        if document_id and payload["document_id"] != document_id:
            continue
        results.append({"score": float(scores[i]), **_payload_to_chunk(payload)})
        if len(results) >= limit:
            break
    return results


def _fuse_rrf(result_lists: list[list[dict]], limit: int) -> list[dict]:
    """Reciprocal rank fusion: combine rankings from retrieval methods whose
    raw scores aren't on comparable scales (cosine similarity vs. BM25),
    using only each chunk's rank within each list."""
    rrf_scores: dict[tuple, float] = {}
    chunk_by_key: dict[tuple, dict] = {}
    for results in result_lists:
        for rank, chunk in enumerate(results, start=1):
            key = (chunk["document_id"], chunk["chunk_index"])
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (_RRF_K + rank)
            chunk_by_key.setdefault(key, chunk)
    ranked_keys = sorted(rrf_scores, key=lambda k: rrf_scores[k], reverse=True)[:limit]
    fused = []
    for key in ranked_keys:
        chunk = dict(chunk_by_key[key])
        chunk["score"] = rrf_scores[key]
        fused.append(chunk)
    return fused


def search(query: str, top_k: int | None = None, document_id: str | None = None) -> list[dict]:
    client = get_client()
    limit = top_k or settings.TOP_K
    # Fetch a wider pool from each method than the final limit so fusion
    # has enough from both sides to actually blend, rather than one
    # method's own top results alone determining the merged top `limit`.
    pool = max(limit * 2, limit + 5)
    dense = _dense_search(client, query, pool, document_id)
    keyword = _keyword_search(client, query, pool, document_id)
    return _fuse_rrf([dense, keyword], limit)


def reset_collection() -> None:
    """Drops and recreates the collection empty. Used by scripts/rollback.py
    to restore a known-good state in one command rather than leaving stale
    or bad chunks mixed in with a re-ingested corpus."""
    client = get_client()
    client.delete_collection(collection_name=settings.QDRANT_COLLECTION)
    _ensure_collection(client)
    _invalidate_bm25_cache()


def delete_document(document_id: str) -> None:
    client = get_client()
    client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="document_id", match=qmodels.MatchValue(value=document_id)
                    )
                ]
            )
        ),
    )
    _invalidate_bm25_cache()
