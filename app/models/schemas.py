from datetime import datetime

from pydantic import BaseModel
from sqlmodel import Field, SQLModel

# --- Persisted tables (SQLModel) ---


class Document(SQLModel, table=True):
    id: str = Field(primary_key=True)
    filename: str
    num_chunks: int
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class ChatSession(SQLModel, table=True):
    id: str = Field(primary_key=True)
    user_id: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="chatsession.id", index=True)
    role: str  # "user" | "assistant"
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- API request/response models (Pydantic) ---


class DocumentOut(BaseModel):
    id: str
    filename: str
    num_chunks: int
    uploaded_at: datetime


class IngestResponse(BaseModel):
    document_id: str
    filename: str
    num_chunks: int


class Citation(BaseModel):
    document_id: str
    filename: str
    page: int | None = None
    chunk_index: int
    score: float
    text: str


class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None
    document_id: str | None = None
    top_k: int | None = None
    user_id: str | None = None  # optional: enables cross-session memory recall
    require_approval: bool = False  # gate commercially-sensitive answers behind interrupt()


class ApprovalRequest(BaseModel):
    approved: bool
    reason: str | None = None  # required in spirit if approved=False; not enforced, just recorded


class ChatResponse(BaseModel):
    session_id: str
    answer: str | None  # None only while pending_approval is True — nothing has been released yet
    citations: list[Citation]
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    faithfulness_score: float | None = None  # None only for the no-documents short-circuit
    retries: int = 0  # how many times the critique sent the Strategist back to re-plan
    escalated: bool = False  # retries exhausted and still ungrounded/uncited — needs human review
    used_memory: bool = False  # whether a past session's exchange was recalled into context
    sub_queries: list[str] = []  # the Retrieval Strategist's actual search plan for this answer
    strategist_reasoning: str = ""  # the Strategist's one-sentence rationale for that plan
    pending_approval: bool = False  # True: paused at approval_gate_node, call POST .../approve
    approval_status: str = "not_required"  # not_required | approved | rejected
    approval_reason: str = ""  # why approval was needed, only set when pending_approval is True
    draft_answer: str | None = None  # the un-released draft, only set when pending_approval is True
    code_version: str = ""  # git commit that produced this answer — see app/core/version.py
    cost_usd: float = 0.0  # illustrative token-cost estimate — see app/core/cost.py
