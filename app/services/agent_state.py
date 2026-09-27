from typing import TypedDict


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
    require_approval: bool  # opt-in: gate commercially-sensitive answers behind interrupt()

    # Retrieval Strategist output, consumed by retrieve_node
    sub_queries: list[str]
    top_k: int
    strategist_reasoning: str

    # retrieval output
    chunks: list[dict]
    no_documents: bool

    # Drafting Agent output (cumulative across retries)
    answer: str
    citations: list[dict]  # plain dicts, not Citation Pydantic objects — see draft_node
    prompt_tokens: int
    completion_tokens: int
    cache_creation_tokens: int  # cumulative Anthropic cache-write tokens (see llm_client.py)
    cache_read_tokens: int  # cumulative Anthropic cache-read tokens across retries
    llm_error: bool  # True if the Drafting Agent's LLM call itself raised (e.g. quota/network) —
    # signals critique/retry/remember to skip rather than retry a failure retrying can't fix

    # critique + loop control
    faithfulness_score: float | None
    critique_feedback: str
    missing_citation: bool  # answer had no [Source N] marker despite retrieved chunks existing
    retry_count: int
    max_retries: int

    # escalation (escalate_node) — set when retries are exhausted and the
    # answer is still ungrounded or uncited; the bid team must see this, not
    # silently receive a low-confidence answer that looks the same as a good one
    escalated: bool

    # human-in-the-loop (approval_gate_node) — set when require_approval=True
    # and the drafted answer quotes a commercial figure. "not_required" means
    # the gate ran but didn't need to pause; "approved"/"rejected" mean a
    # human actually decided via the /chat/{session_id}/approve endpoint.
    approval_status: str

    # cross-session memory (populated by recall_memory node)
    remembered_context: list[dict]
