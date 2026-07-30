import time

from app.models.schemas import Citation
from app.services.llm_client import LLMResult, call_llm
from app.services.vector_store import search

SYSTEM_PROMPT = (
    "You are an enterprise knowledge assistant. Answer the user's question "
    "using ONLY the provided context. If the answer is not contained in the "
    "context, say you don't have enough information — never fabricate an "
    "answer. Be concise, and refer to sources by their number, e.g. [Source 1], "
    "when relevant."
)


def build_context(chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks, start=1):
        loc = f"p.{c['page']}" if c.get("page") else f"chunk {c['chunk_index']}"
        parts.append(f"[Source {i} — {c['filename']} ({loc})]\n{c['text']}")
    return "\n\n".join(parts)


def answer_question(
    question: str,
    top_k: int | None = None,
    document_id: str | None = None,
    history: list[dict] | None = None,
) -> dict:
    start = time.perf_counter()
    chunks = search(question, top_k=top_k, document_id=document_id)

    if not chunks:
        return {
            "answer": "I don't have any ingested documents to answer this from yet. "
            "Upload a document first via POST /documents.",
            "citations": [],
            "latency_ms": (time.perf_counter() - start) * 1000,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "contexts": [],
        }

    context = build_context(chunks)
    history_text = ""
    if history:
        history_text = (
            "Conversation so far:\n"
            + "\n".join(f"{m['role']}: {m['content']}" for m in history)
            + "\n\n"
        )
    user_prompt = f"{history_text}Context:\n{context}\n\nQuestion: {question}"

    result: LLMResult = call_llm(SYSTEM_PROMPT, user_prompt)
    latency_ms = (time.perf_counter() - start) * 1000

    citations = [
        Citation(
            document_id=c["document_id"],
            filename=c["filename"],
            page=c.get("page"),
            chunk_index=c["chunk_index"],
            score=c["score"],
            text=c["text"][:300],
        )
        for c in chunks
    ]

    return {
        "answer": result.text,
        "citations": citations,
        "latency_ms": latency_ms,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "contexts": [c["text"] for c in chunks],
    }
