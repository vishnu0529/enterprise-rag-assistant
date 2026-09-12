from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.db import init_db
from app.routers import chat, documents, evaluate
from app.services.embeddings import get_embedder


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Loads (and on a fresh instance, downloads) the embedding model now,
    # not on the first real request — on a cold PaaS instance, doing this
    # lazily on the first /chat or /documents call can take long enough to
    # exceed the platform's proxy timeout and return a 502 while the
    # container is still alive and working in the background.
    get_embedder()
    yield


app = FastAPI(
    title="Enterprise Knowledge Assistant",
    description="Production-style RAG system with citations and evaluation.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(evaluate.router)
