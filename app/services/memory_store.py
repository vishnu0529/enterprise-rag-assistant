"""Cross-session semantic memory, per user.

The existing session_store.py only persists messages within a single
session_id — a returning user starting a fresh session has no continuity
with what they asked before. This adds a second Qdrant collection
(separate from the document-chunks collection in vector_store.py) that
embeds and stores every question/answer exchange keyed by user_id, so a
later session can semantically recall relevant prior exchanges even
though it's a different session_id, or even a different process/deploy —
this is what makes the memory cross-session rather than just
longer-context-within-one-conversation.

user_id is caller-supplied (e.g. a login identity or a stable client-side
ID) and optional throughout the API — omitting it just means no
cross-session recall, matching the existing anonymous-session behaviour.
"""

import uuid

from qdrant_client.http import models as qmodels

from app.services.embeddings import embed_query, embed_texts, embedding_dim
from app.services.vector_store import get_client

MEMORY_COLLECTION = "user_memory"


def _ensure_memory_collection() -> None:
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]
    if MEMORY_COLLECTION not in existing:
        client.create_collection(
            collection_name=MEMORY_COLLECTION,
            vectors_config=qmodels.VectorParams(
                size=embedding_dim(), distance=qmodels.Distance.COSINE
            ),
        )


def remember_exchange(user_id: str, session_id: str, question: str, answer: str) -> None:
    _ensure_memory_collection()
    client = get_client()
    text = f"Q: {question}\nA: {answer}"
    vector = embed_texts([text])[0]
    client.upsert(
        collection_name=MEMORY_COLLECTION,
        points=[
            qmodels.PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "user_id": user_id,
                    "session_id": session_id,
                    "question": question,
                    "answer": answer,
                },
            )
        ],
    )


def recall_relevant_memory(user_id: str, question: str, k: int = 3) -> list[dict]:
    _ensure_memory_collection()
    client = get_client()
    query_vector = embed_query(question)
    results = client.query_points(
        collection_name=MEMORY_COLLECTION,
        query=query_vector,
        limit=k,
        query_filter=qmodels.Filter(
            must=[qmodels.FieldCondition(key="user_id", match=qmodels.MatchValue(value=user_id))]
        ),
    ).points
    return [
        {"question": r.payload["question"], "answer": r.payload["answer"], "score": r.score}
        for r in results
    ]
