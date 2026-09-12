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


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    citations: list[Citation]
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    faithfulness_score: float | None = None  # None only for the no-documents short-circuit
    retries: int = 0  # how many times the corrective loop reformulated and re-retrieved
    used_memory: bool = False  # whether a past session's exchange was recalled into context
