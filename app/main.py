from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.db import init_db
from app.core.version import CODE_VERSION
from app.routers import chat, documents, evaluate


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # NOT eager-loading the embedder here: on Render's free tier (512MB),
    # loading torch + sentence-transformers at startup was observed to OOM
    # before the app could finish booting at all (see git history / commit
    # message on the revert of this line). Lazy loading on first use is a
    # real tradeoff — it risks a slow/failed first request instead — but an
    # app that can't start is strictly worse than one that's slow once.
    # docs/DEPLOYMENT.md documents the underlying memory constraint and the
    # real fix (a lighter embedding backend or a bigger instance).
    yield


app = FastAPI(
    title="Proposal Response Assistant",
    description="Production-style RAG for bid-team proposal drafting, with citations and eval.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok", "code_version": CODE_VERSION}


app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(evaluate.router)
