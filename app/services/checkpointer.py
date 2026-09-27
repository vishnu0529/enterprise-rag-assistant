"""Durable checkpointing for the corrective-RAG graph.

Postgres-backed when a real Postgres DATABASE_URL is configured (docker-compose,
production), falling back to an in-memory checkpointer for local SQLite dev —
the same local-first-dev/production-shaped-deploy split already used by
app/core/db.py and app/services/vector_store.py.

This is what makes a killed-and-restarted process resume a run instead of
losing it: MemorySaver's state lives only in that process's memory and dies
with it. PostgresSaver writes each node's checkpoint to Postgres as the graph
runs, so a completely fresh process — a different Python interpreter, no
shared memory — can reconnect with the same thread_id and continue from the
last completed node. See scripts/demo_kill_and_resume.py for a live
end-to-end demonstration (two real OS processes, one SIGKILLed mid-run).
"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import settings

_checkpointer: BaseCheckpointSaver | None = None


def get_checkpointer() -> BaseCheckpointSaver:
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    if settings.DATABASE_URL.startswith("postgresql"):
        pool = ConnectionPool(
            conninfo=settings.DATABASE_URL,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
            open=True,
        )
        checkpointer = PostgresSaver(pool)
        checkpointer.setup()  # no-op if tables already exist; safe to call every boot
        _checkpointer = checkpointer
    else:
        _checkpointer = MemorySaver()

    return _checkpointer
