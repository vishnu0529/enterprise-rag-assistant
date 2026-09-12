"""Local embeddings via fastembed (ONNX runtime), not sentence-transformers.

sentence-transformers pulls in torch, whose baseline memory footprint alone
was enough to OOM this app on Render's free tier (512MB) — see the git
history around the commit that reverted eager-loading it at startup.
fastembed runs the same class of small embedding models via ONNX Runtime
instead, with a much smaller resident footprint, while keeping embeddings
local and free (no per-call API cost) — same tradeoff the project already
chose, just without the torch tax.
"""

from functools import lru_cache

from fastembed import TextEmbedding

from app.core.config import settings


@lru_cache(maxsize=1)
def get_embedder() -> TextEmbedding:
    return TextEmbedding(model_name=settings.EMBEDDING_MODEL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedder()
    return [vec.tolist() for vec in model.embed(texts)]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


@lru_cache(maxsize=1)
def embedding_dim() -> int:
    return len(embed_query("dimension probe"))
