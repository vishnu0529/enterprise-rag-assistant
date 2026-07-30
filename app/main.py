from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.db import init_db
from app.routers import chat, documents


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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
