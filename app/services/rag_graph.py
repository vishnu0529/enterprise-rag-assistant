"""Two-agent corrective-RAG graph: a Retrieval Strategist decides how to
search, a Drafting Agent writes the answer, and a critique gate routes
back to the Strategist (not just a query rewrite) when the draft isn't
well-grounded.

    recall_memory -> strategize -> retrieve -> draft -> critique
                          ^                                  |
                          '------ retry, with feedback -------'

This is a genuine two-role split, not a renamed single function: the
Strategist (strategize_node) never sees the retrieved context or writes
prose — it only decides sub_queries (supporting real multi-hop
decomposition for comparison-style questions) and top_k. The Drafter
(draft_node) never decides search strategy — it only writes from
whatever evidence retrieve_node assembled. They communicate solely
through RagAgentState, not by calling each other directly.

Reuses existing single-pass primitives (vector_store.search,
rag_chain.build_context/SYSTEM_PROMPT) rather than duplicating them — see
docs/ARCHITECTURE.md for the full design rationale, including why
cross-session memory (memory_store.py) is deliberately separate from
LangGraph's own thread-scoped checkpointing.
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.models.schemas import Citation
from app.services.agent_state import RagAgentState
from app.services.evaluation import score_faithfulness
from app.services.llm_client import call_llm, call_llm_json
from app.services.memory_store import recall_relevant_memory, remember_exchange
from app.services.rag_chain import SYSTEM_PROMPT, build_context
from app.services.vector_store import search

MIN_FAITHFULNESS = 0.7
DEFAULT_MAX_RETRIES = 2

NO_DOCUMENTS_ANSWER = (
    "I don't have any ingested documents to answer this from yet. "
    "Upload a document first via POST /documents."
)

STRATEGIST_SYSTEM_PROMPT = (
    "You are the Retrieval Strategist for a knowledge-base assistant. You do not write "
    "answers — a separate Drafting Agent does that. Your only job is deciding how to search.\n\n"
    "Decide:\n"
    "1. One or more search queries to run. Use 2-3 only for genuine multi-hop questions "
    "(e.g. comparing two distinct things, which need separate searches); otherwise one "
    "focused query is better than several vague ones.\n"
    "2. How many chunks to retrieve per query (top_k, between 3 and 8).\n\n"
    'Respond as JSON: {"sub_queries": ["..."], "top_k": <int>, "reasoning": "<one sentence>"}'
)


def _build_strategize_prompt(state: RagAgentState) -> str:
    parts = [f"QUESTION: {state['original_question']}"]

    if state.get("critique_feedback"):
        parts.append(
            f"\nA previous attempt with different search queries produced an answer that "
            f"wasn't well-grounded: {state['critique_feedback']} "
            "Change strategy — broaden, decompose, or rephrase, don't repeat the same queries."
        )

    if state.get("requested_top_k"):
        parts.append(
            f"\nThe caller requested top_k={state['requested_top_k']}; "
            "use that unless you have good reason not to."
        )

    remembered = state.get("remembered_context") or []
    if remembered:
        mem_text = "\n".join(f"- Q: {m['question']} / A: {m['answer']}" for m in remembered)
        parts.append(f"\nPast exchanges with this user, for context only:\n{mem_text}")

    return "\n".join(parts)


def recall_memory_node(state: RagAgentState) -> dict:
    user_id = state.get("user_id")
    if not user_id:
        return {"remembered_context": []}
    try:
        remembered = recall_relevant_memory(user_id, state["original_question"])
    except Exception:
        remembered = []
    return {"remembered_context": remembered}


def strategize_node(state: RagAgentState) -> dict:
    is_retry = bool(state.get("critique_feedback"))
    prompt = _build_strategize_prompt(state)
    try:
        result = call_llm_json(STRATEGIST_SYSTEM_PROMPT, prompt)
        sub_queries = [q for q in result.get("sub_queries", []) if q and q.strip()]
        sub_queries = sub_queries or [state["original_question"]]
        top_k = int(result.get("top_k") or state.get("requested_top_k") or 4)
        reasoning = result.get("reasoning", "")
    except Exception:
        sub_queries = [state["original_question"]]
        top_k = state.get("requested_top_k") or 4
        reasoning = ""

    updates = {"sub_queries": sub_queries, "top_k": top_k, "strategist_reasoning": reasoning}
    if is_retry:
        updates["retry_count"] = state.get("retry_count", 0) + 1
    return updates


def _merge_and_dedupe(chunks: list[dict]) -> list[dict]:
    """Sub-queries can retrieve overlapping chunks; keep each chunk's
    highest score across queries rather than duplicating or discarding."""
    best: dict[tuple, dict] = {}
    for c in chunks:
        key = (c["document_id"], c["chunk_index"])
        if key not in best or c["score"] > best[key]["score"]:
            best[key] = c
    return sorted(best.values(), key=lambda c: c["score"], reverse=True)


def retrieve_node(state: RagAgentState) -> dict:
    sub_queries = state.get("sub_queries") or [state["original_question"]]
    all_chunks = []
    for q in sub_queries:
        all_chunks.extend(search(q, top_k=state.get("top_k"), document_id=state.get("document_id")))
    chunks = _merge_and_dedupe(all_chunks)
    return {"chunks": chunks, "no_documents": not chunks}


def _route_after_retrieve(state: RagAgentState) -> str:
    return "no_documents" if state.get("no_documents") else "draft"


def no_documents_node(state: RagAgentState) -> dict:
    return {
        "answer": NO_DOCUMENTS_ANSWER,
        "citations": [],
        "prompt_tokens": state.get("prompt_tokens", 0),
        "completion_tokens": state.get("completion_tokens", 0),
    }


def draft_node(state: RagAgentState) -> dict:
    """The Drafting Agent: writes the answer from whatever the Strategist's
    plan retrieved. Deliberately has no say over search strategy — it
    only sees the assembled evidence, not the sub_queries that produced it."""
    chunks = state["chunks"]
    context = build_context(chunks)

    history = state.get("history") or []
    history_text = ""
    if history:
        history_text = (
            "Conversation so far:\n"
            + "\n".join(f"{m['role']}: {m['content']}" for m in history)
            + "\n\n"
        )

    remembered = state.get("remembered_context") or []
    memory_text = ""
    if remembered:
        memory_text = (
            "Relevant exchanges from this user's earlier sessions "
            "(for continuity — don't repeat verbatim, build on it):\n"
            + "\n".join(f"Q: {m['question']}\nA: {m['answer']}" for m in remembered)
            + "\n\n"
        )

    user_prompt = (
        f"{memory_text}{history_text}Context:\n{context}\n\nQuestion: {state['original_question']}"
    )
    result = call_llm(SYSTEM_PROMPT, user_prompt)

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
        "prompt_tokens": state.get("prompt_tokens", 0) + result.prompt_tokens,
        "completion_tokens": state.get("completion_tokens", 0) + result.completion_tokens,
    }


def critique_node(state: RagAgentState) -> dict:
    contexts = [c["text"] for c in state["chunks"]]
    score = score_faithfulness(state["answer"], contexts)
    feedback = (
        ""
        if score >= MIN_FAITHFULNESS
        else f"scored {score:.2f}/1.0 on faithfulness — not well supported by the retrieved context"
    )
    return {"faithfulness_score": score, "critique_feedback": feedback}


def _should_retry(state: RagAgentState) -> str:
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", DEFAULT_MAX_RETRIES)
    if state.get("faithfulness_score", 1.0) < MIN_FAITHFULNESS and retry_count < max_retries:
        return "strategize"
    return "remember"


def remember_node(state: RagAgentState) -> dict:
    user_id = state.get("user_id")
    if user_id:
        try:
            remember_exchange(
                user_id=user_id,
                session_id=state.get("session_id", ""),
                question=state["original_question"],
                answer=state["answer"],
            )
        except Exception:
            pass
    return {}


def build_graph():
    graph = StateGraph(RagAgentState)
    graph.add_node("recall_memory", recall_memory_node)
    graph.add_node("strategize", strategize_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("no_documents", no_documents_node)
    graph.add_node("draft", draft_node)
    graph.add_node("critique", critique_node)
    graph.add_node("remember", remember_node)

    graph.set_entry_point("recall_memory")
    graph.add_edge("recall_memory", "strategize")
    graph.add_edge("strategize", "retrieve")
    graph.add_conditional_edges(
        "retrieve", _route_after_retrieve, {"no_documents": "no_documents", "draft": "draft"}
    )
    graph.add_edge("no_documents", END)
    graph.add_edge("draft", "critique")
    graph.add_conditional_edges(
        "critique", _should_retry, {"strategize": "strategize", "remember": "remember"}
    )
    graph.add_edge("remember", END)

    return graph.compile(checkpointer=MemorySaver())


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def answer_question_agentic(
    question: str,
    top_k: int | None = None,
    document_id: str | None = None,
    history: list[dict] | None = None,
    user_id: str | None = None,
    session_id: str = "",
) -> dict:
    """Drop-in replacement for rag_chain.answer_question with the same
    return shape, plus faithfulness_score/retries/sub_queries for callers
    that want to show the two-agent loop's behaviour (see routers/chat.py)."""
    import time

    start = time.perf_counter()
    graph = get_graph()
    initial_state: RagAgentState = {
        "original_question": question,
        "requested_top_k": top_k,
        "document_id": document_id,
        "history": history or [],
        "user_id": user_id,
        "session_id": session_id,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "retry_count": 0,
        "max_retries": DEFAULT_MAX_RETRIES,
    }
    config = {"configurable": {"thread_id": f"{session_id or 'no-session'}:{hash(question)}"}}
    result = graph.invoke(initial_state, config=config)
    latency_ms = (time.perf_counter() - start) * 1000

    return {
        "answer": result["answer"],
        "citations": result.get("citations", []),
        "latency_ms": latency_ms,
        "prompt_tokens": result.get("prompt_tokens", 0),
        "completion_tokens": result.get("completion_tokens", 0),
        "contexts": [c["text"] for c in result.get("chunks", [])],
        "faithfulness_score": result.get("faithfulness_score"),
        "retries": result.get("retry_count", 0),
        "used_memory": bool(result.get("remembered_context")),
        "sub_queries": result.get("sub_queries", []),
        "strategist_reasoning": result.get("strategist_reasoning", ""),
    }
