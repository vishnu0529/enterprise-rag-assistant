from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import settings
from app.services.embeddings import embed_query, embed_texts, embedding_dim

_client: QdrantClient | None = None


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
        for c, vector in zip(chunks, vectors)
    ]
    client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)
    return len(points)


def search(
    query: str, top_k: int | None = None, document_id: str | None = None
) -> list[dict]:
    client = get_client()
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
        limit=top_k or settings.TOP_K,
        query_filter=query_filter,
    ).points
    return [
        {
            "score": r.score,
            "document_id": r.payload["document_id"],
            "filename": r.payload["filename"],
            "text": r.payload["text"],
            "page": r.payload.get("page"),
            "chunk_index": r.payload["chunk_index"],
        }
        for r in results
    ]


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
