"""Two-stage retrieval, stage two: hybrid_search.search_hybrid() fetches a
wide candidate pool cheaply (dense + sparse retrieval, no per-candidate
model inference), and this reranker narrows it to the final top_k using a
cross-encoder that scores each (query, chunk) pair jointly — more accurate
than embedding similarity alone, but too slow to run over a full corpus,
hence only ever applied to the already-narrowed candidate pool.

Uses sentence-transformers' CrossEncoder — no new dependency, the package
is already installed for embeddings (app/services/embeddings.py).
"""

from functools import lru_cache

from sentence_transformers import CrossEncoder

from app.core.config import settings


@lru_cache(maxsize=1)
def _get_reranker() -> CrossEncoder:
    return CrossEncoder(settings.RERANKER_MODEL)


def rerank(query: str, candidates: list[dict], top_k: int) -> list[dict]:
    if not candidates:
        return []

    model = _get_reranker()
    pairs = [(query, c["text"]) for c in candidates]
    scores = model.predict(pairs)

    reranked = sorted(zip(candidates, scores, strict=True), key=lambda pair: pair[1], reverse=True)
    results = []
    for chunk, score in reranked[:top_k]:
        c = dict(chunk)
        c["score"] = float(score)
        results.append(c)
    return results
