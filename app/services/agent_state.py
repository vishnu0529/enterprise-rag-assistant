from typing import TypedDict

from app.models.schemas import Citation


class RagAgentState(TypedDict, total=False):
    """Shared state threaded through the two-agent corrective-RAG graph.

    Two distinct agent roles collaborate via this state: the Retrieval
    Strategist (strategize_node) decides sub_queries/top_k, and the
    Drafting Agent (draft_node) writes the answer from whatever the
    Strategist's plan retrieved. Neither node knows the other's prompt —
    they only communicate through these fields.
    """

    # inputs (fixed for the whole run)
    original_question: str
    document_id: str | None
    history: list[dict]
    user_id: str | None
    session_id: str
    requested_top_k: int | None  # caller-supplied hint, the Strategist may honor or override

    # Retrieval Strategist output, consumed by retrieve_node
    sub_queries: list[str]
    top_k: int
    strategist_reasoning: str

    # retrieval output
    chunks: list[dict]
    no_documents: bool

    # Drafting Agent output (cumulative across retries)
    answer: str
    citations: list[Citation]
    prompt_tokens: int
    completion_tokens: int
    llm_error: bool  # True if the Drafting Agent's LLM call itself raised (e.g. quota/network) —
    # signals critique/retry/remember to skip rather than retry a failure retrying can't fix

    # critique + loop control
    faithfulness_score: float | None
    critique_feedback: str
    retry_count: int
    max_retries: int

    # cross-session memory (populated by recall_memory node)
    remembered_context: list[dict]
