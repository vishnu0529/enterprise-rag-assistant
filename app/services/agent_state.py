from typing import TypedDict

from app.models.schemas import Citation


class RagAgentState(TypedDict, total=False):
    """Shared state threaded through the corrective-RAG graph.

    One instance flows through retrieve -> generate -> critique -> [loop
    back via reformulate, or end]. `question` is mutated on each
    reformulation; `original_question` is kept fixed so nodes can always
    refer back to what the user actually asked.
    """

    # inputs (fixed for the whole run)
    original_question: str
    document_id: str | None
    history: list[dict]
    user_id: str | None
    session_id: str

    # mutated per retrieval attempt
    question: str
    top_k: int
    chunks: list[dict]
    no_documents: bool

    # generation output (cumulative across retries)
    answer: str
    citations: list[Citation]
    prompt_tokens: int
    completion_tokens: int

    # critique + loop control
    faithfulness_score: float
    retry_count: int
    max_retries: int

    # cross-session memory (populated by recall_memory node)
    remembered_context: list[dict]
