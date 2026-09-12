"""Corrective-RAG graph: retrieve -> generate -> critique -> [reformulate
+ retrieve again if ungrounded, capped] -> end.

This reuses the existing single-pass primitives (vector_store.search,
llm_client.call_llm, rag_chain.build_context/SYSTEM_PROMPT) rather than
duplicating them — the difference from rag_chain.answer_question is that
retrieval and generation are separate graph nodes with a critique gate in
between, so the graph can loop back and try a reformulated query when the
generated answer isn't well-grounded in what was retrieved. This is the
"Corrective RAG" / "Self-RAG" pattern: instead of trusting the first
retrieval, the system's own faithfulness judge (evaluation.py's existing
score_faithfulness, already used for offline evaluation) gates whether the
answer is good enough to return, live, in the request path.

A within-run LangGraph MemorySaver checkpointer is used only so the graph
can be invoked identically from tests and production; the app's actual
cross-session memory (recalling past exchanges from a *different*
session_id) is handled separately by memory_store.py, keyed by user_id,
since LangGraph's own thread-scoped checkpointing doesn't do semantic
recall across unrelated threads.
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

REFORMULATE_PROMPT = (
    "The following search query did not retrieve context that supports a "
    "faithful answer to the user's actual question.\n\n"
    "Original question: {original_question}\n"
    "Query tried: {question}\n\n"
    "Write ONE improved search query — broader or rephrased — more likely "
    "to retrieve context that actually supports answering the original "
    'question. Respond as JSON: {{"query": "..."}}'
)


def recall_memory_node(state: RagAgentState) -> dict:
    user_id = state.get("user_id")
    if not user_id:
        return {"remembered_context": []}
    try:
        remembered = recall_relevant_memory(user_id, state["original_question"])
    except Exception:
        remembered = []
    return {"remembered_context": remembered}


def retrieve_node(state: RagAgentState) -> dict:
    chunks = search(
        state["question"], top_k=state.get("top_k"), document_id=state.get("document_id")
    )
    return {"chunks": chunks, "no_documents": not chunks}


def _route_after_retrieve(state: RagAgentState) -> str:
    return "no_documents" if state.get("no_documents") else "generate"


def no_documents_node(state: RagAgentState) -> dict:
    return {
        "answer": NO_DOCUMENTS_ANSWER,
        "citations": [],
        "prompt_tokens": state.get("prompt_tokens", 0),
        "completion_tokens": state.get("completion_tokens", 0),
    }


def generate_node(state: RagAgentState) -> dict:
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
    return {"faithfulness_score": score}


def _should_retry(state: RagAgentState) -> str:
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", DEFAULT_MAX_RETRIES)
    if state.get("faithfulness_score", 1.0) < MIN_FAITHFULNESS and retry_count < max_retries:
        return "reformulate"
    return "remember"


def reformulate_node(state: RagAgentState) -> dict:
    prompt = REFORMULATE_PROMPT.format(
        original_question=state["original_question"], question=state["question"]
    )
    try:
        result = call_llm_json("You rewrite search queries.", prompt)
        new_query = result.get("query") or state["original_question"]
    except Exception:
        new_query = state["original_question"]

    return {
        "question": new_query,
        "top_k": state.get("top_k", 4) + 2,  # broaden retrieval on retry, not just reword
        "retry_count": state.get("retry_count", 0) + 1,
    }


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
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("no_documents", no_documents_node)
    graph.add_node("generate", generate_node)
    graph.add_node("critique", critique_node)
    graph.add_node("reformulate", reformulate_node)
    graph.add_node("remember", remember_node)

    graph.set_entry_point("recall_memory")
    graph.add_edge("recall_memory", "retrieve")
    graph.add_conditional_edges(
        "retrieve", _route_after_retrieve, {"no_documents": "no_documents", "generate": "generate"}
    )
    graph.add_edge("no_documents", END)
    graph.add_edge("generate", "critique")
    graph.add_conditional_edges(
        "critique", _should_retry, {"reformulate": "reformulate", "remember": "remember"}
    )
    graph.add_edge("reformulate", "retrieve")
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
    return shape, plus faithfulness_score/retries for callers that want to
    show the corrective loop's behaviour (see routers/chat.py)."""
    import time

    start = time.perf_counter()
    graph = get_graph()
    initial_state: RagAgentState = {
        "original_question": question,
        "question": question,
        "top_k": top_k or 4,
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
    }
