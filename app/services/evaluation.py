"""RAG evaluation metrics, implemented directly following the RAGAS
methodology (https://docs.ragas.io) rather than depending on the `ragas`
package — the installed `ragas==0.4.3` has a broken import against the
langchain-community version this project uses (an unrelated
langchain_community.chat_models.vertexai dependency conflict). Implementing
the metrics directly avoids that fragility and is functionally equivalent.
"""

from dataclasses import dataclass

import numpy as np

from app.services.embeddings import embed_texts
from app.services.llm_client import call_llm_json

# Deferred import: rag_graph imports score_faithfulness from this module, so
# importing rag_graph at module level here would create a circular import.
# See evaluate_question() below.


@dataclass
class EvalResult:
    question: str
    answer: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int


def _cosine(a: list[float], b: list[float]) -> float:
    a_arr, b_arr = np.array(a), np.array(b)
    denom = np.linalg.norm(a_arr) * np.linalg.norm(b_arr) + 1e-8
    return float(np.dot(a_arr, b_arr) / denom)


def score_faithfulness(answer: str, contexts: list[str]) -> float:
    """Fraction of claims in the answer that are directly supported by the
    retrieved context. Detects hallucination."""
    if not contexts:
        return 0.0
    system = (
        "You are an evaluation judge. Break the ANSWER into individual "
        "factual claims, then decide for each claim whether it is directly "
        'supported by the CONTEXT. Respond as JSON: {"claims": '
        '[{"claim": "...", "supported": true|false}, ...]}'
    )
    user = f"CONTEXT:\n{chr(10).join(contexts)}\n\nANSWER:\n{answer}"
    try:
        result = call_llm_json(system, user)
        claims = result.get("claims", [])
        if not claims:
            return 1.0
        supported = sum(1 for c in claims if c.get("supported"))
        return supported / len(claims)
    except Exception:
        return 0.0


def score_answer_relevancy(question: str, answer: str, n: int = 3) -> float:
    """Generates candidate questions the answer would address, then measures
    embedding similarity to the actual question. Detects non-answers /
    off-topic responses."""
    system = (
        f"Given the ANSWER below, generate {n} distinct questions that this "
        "answer would directly and completely address. Respond as JSON: "
        '{"questions": ["...", "...", "..."]}'
    )
    try:
        result = call_llm_json(system, f"ANSWER:\n{answer}")
        generated = [q for q in result.get("questions", []) if q.strip()]
        if not generated:
            return 0.0
        question_emb = embed_texts([question])[0]
        generated_embs = embed_texts(generated)
        sims = [_cosine(question_emb, g) for g in generated_embs]
        return max(sum(sims) / len(sims), 0.0)
    except Exception:
        return 0.0


def score_context_precision(question: str, contexts: list[str]) -> float:
    """Are relevant chunks ranked near the top? Average precision over the
    ranked retrieval list (standard RAGAS formula)."""
    if not contexts:
        return 0.0
    system = (
        "You are an evaluation judge. Given the QUESTION, decide whether the "
        "CONTEXT chunk is relevant to answering it. Respond as JSON: "
        '{"relevant": true|false}'
    )
    relevances = []
    for ctx in contexts:
        try:
            result = call_llm_json(system, f"QUESTION: {question}\n\nCONTEXT:\n{ctx}")
            relevances.append(bool(result.get("relevant", False)))
        except Exception:
            relevances.append(False)

    precisions = []
    hits = 0
    for i, rel in enumerate(relevances, start=1):
        if rel:
            hits += 1
            precisions.append(hits / i)
    return sum(precisions) / len(precisions) if precisions else 0.0


def score_context_recall(ground_truth: str, contexts: list[str]) -> float:
    """Fraction of statements in a reference (ground-truth) answer that can
    be attributed to the retrieved context. Requires a ground truth, so this
    only runs against a labelled eval set, not live production traffic."""
    if not ground_truth or not contexts:
        return 0.0
    system = (
        "You are an evaluation judge. Break the GROUND_TRUTH answer into "
        "individual factual statements, then decide for each whether it can "
        "be attributed to (found in) the CONTEXT. Respond as JSON: "
        '{"statements": [{"statement": "...", "attributed": true|false}, ...]}'
    )
    user = f"CONTEXT:\n{chr(10).join(contexts)}\n\nGROUND_TRUTH:\n{ground_truth}"
    try:
        result = call_llm_json(system, user)
        statements = result.get("statements", [])
        if not statements:
            return 0.0
        attributed = sum(1 for s in statements if s.get("attributed"))
        return attributed / len(statements)
    except Exception:
        return 0.0


def evaluate_question(
    question: str, ground_truth: str | None = None, top_k: int | None = None
) -> EvalResult:
    # Evaluation reuses the exact same path /chat uses (the corrective-RAG
    # graph), not a separate simplified path — so these metrics score real
    # production behaviour, including any reformulate-and-retry the graph did.
    from app.services.rag_graph import answer_question_agentic

    result = answer_question_agentic(question, top_k=top_k)
    contexts = result["contexts"]

    # The graph's critique node already scored faithfulness on this exact
    # (answer, contexts) pair — reuse it instead of paying for a second,
    # redundant LLM-judge call.
    faithfulness = result.get("faithfulness_score")
    if faithfulness is None:
        faithfulness = score_faithfulness(result["answer"], contexts)

    return EvalResult(
        question=question,
        answer=result["answer"],
        faithfulness=faithfulness,
        answer_relevancy=score_answer_relevancy(question, result["answer"]),
        context_precision=score_context_precision(question, contexts),
        context_recall=score_context_recall(ground_truth, contexts) if ground_truth else 0.0,
        latency_ms=result["latency_ms"],
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
    )
