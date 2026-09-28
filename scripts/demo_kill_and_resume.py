"""Live demonstration that durable Postgres checkpointing survives a real
process kill, not two calls in the same Python process, but two genuinely
separate OS processes with no shared memory, coordinating only through
Postgres.

Requires a real Postgres DATABASE_URL (see docker-compose.yml, or run a
local Postgres and export DATABASE_URL=postgresql://... yourself).

The LLM calls are mocked (same fixtures used in tests/test_rag_graph.py) so
this demo proves the thing it claims to prove, checkpoint durability across
a process boundary, without depending on a live, quota-unblocked API key,
which is an unrelated resource. The Postgres connection, the process kill,
and the resume are all real.

What it proves:
  1. Phase A runs recall_memory -> strategize -> retrieve, then the process
     is killed with SIGKILL (not a clean exit) before draft ever runs.
  2. Phase B is a brand new Python process. It rebuilds the graph from
     scratch and resumes the SAME thread_id with input=None. Its mocks for
     strategize/retrieve raise if called. If the resume incorrectly
     restarted from the beginning instead of continuing from the
     checkpoint, this demo fails loudly instead of silently passing.

Usage:
    export DATABASE_URL=postgresql://user@localhost:5432/somedb
    ./venv/bin/python scripts/demo_kill_and_resume.py
"""

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SAMPLE_CHUNKS = [
    {
        "score": 0.9,
        "document_id": "demo-doc",
        "filename": "demo.md",
        "text": "Aldermere Advisory's professional indemnity cover is £5 million per claim.",
        "page": None,
        "chunk_index": 0,
    }
]
STRATEGIST_PLAN = {
    "sub_queries": ["professional indemnity cover"],
    "top_k": 4,
    "reasoning": "direct lookup",
}


def _run_phase_a(thread_id: str, sentinel_path: str) -> None:
    """Runs strategize + retrieve, writes a checkpoint, signals it's ready
    via a sentinel file, then blocks forever, waiting to be SIGKILLed by
    the orchestrator from the outside, before draft ever runs."""
    from app.core.config import settings

    print(f"[phase A, pid {os.getpid()}] DATABASE_URL={settings.DATABASE_URL}")
    with (
        patch("app.services.rag_graph.call_llm_json", return_value=STRATEGIST_PLAN),
        patch("app.services.rag_graph.search", return_value=SAMPLE_CHUNKS),
        patch("app.services.rag_graph.recall_relevant_memory", return_value=[]),
    ):
        from app.services.rag_graph import get_graph

        graph = get_graph()
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = {
            "original_question": "What is Aldermere's professional indemnity cover?",
            "requested_top_k": None,
            "document_id": None,
            "history": [],
            "user_id": None,
            "session_id": thread_id,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "retry_count": 0,
            "max_retries": 2,
        }
        result = graph.invoke(initial_state, config=config, interrupt_before=["draft"])
        print(f"[phase A] stopped before draft. sub_queries={result.get('sub_queries')}")
        print(f"[phase A] chunks retrieved={len(result.get('chunks', []))}")
        assert "answer" not in result or result.get("answer") is None, (
            "phase A ran draft, so the interrupt didn't work, this demo proves nothing"
        )
    # Checkpoint is committed to Postgres by this point (PostgresSaver writes
    # synchronously as each node completes). Signal the orchestrator this
    # process is now safe to kill, then block, waiting for a real SIGKILL
    # from outside, not choosing to exit itself.
    Path(sentinel_path).write_text("ready")
    sys.stdout.flush()
    time.sleep(3600)


def _run_phase_b(thread_id: str) -> None:
    """A fresh process. Resumes the same thread_id with no input. If
    strategize/retrieve get called again, the mocks raise, proving they
    were NOT re-run and the state genuinely came from Postgres."""
    from app.core.config import settings

    print(f"[phase B, pid {os.getpid()}] DATABASE_URL={settings.DATABASE_URL}")

    def _fail(*a, **k):
        raise AssertionError("strategize/retrieve ran again, so resume did not use the checkpoint")

    fake_llm_result = type(
        "R",
        (),
        {
            "text": "The cover is £5 million per claim. [Source 1]",
            "prompt_tokens": 40,
            "completion_tokens": 12,
        },
    )()

    with (
        patch("app.services.rag_graph.call_llm_json", side_effect=_fail),
        patch("app.services.rag_graph.search", side_effect=_fail),
        patch("app.services.rag_graph.call_llm", return_value=fake_llm_result),
        patch("app.services.rag_graph.score_faithfulness", return_value=0.95),
        patch("app.services.rag_graph.recall_relevant_memory", side_effect=_fail),
        patch("app.services.rag_graph.remember_exchange", return_value=None),
    ):
        from app.services.rag_graph import get_graph

        graph = get_graph()
        config = {"configurable": {"thread_id": thread_id}}
        result = graph.invoke(None, config=config)
        print(f"[phase B] resumed. sub_queries={result.get('sub_queries')}")
        print(f"[phase B] final answer: {result.get('answer')!r}")
        assert result.get("answer"), "phase B produced no answer, resume failed"
        assert result.get("sub_queries") == STRATEGIST_PLAN["sub_queries"], (
            "resumed state doesn't match what phase A wrote, so the checkpoint didn't carry over"
        )
    print("[phase B] PASS: resumed from Postgres in a fresh process, no re-run of earlier nodes.")


def main() -> None:
    from app.core.config import settings

    if not settings.DATABASE_URL.startswith("postgresql"):
        raise SystemExit(
            "This demo requires a real Postgres DATABASE_URL (got "
            f"{settings.DATABASE_URL!r}). Export DATABASE_URL=postgresql://... first. "
            "see docker-compose.yml for the same credentials it uses."
        )

    thread_id = f"demo-kill-resume-{uuid.uuid4().hex[:8]}"
    script = str(Path(__file__).resolve())
    env = {**os.environ}
    sentinel = Path(f"/tmp/demo_kill_resume_{thread_id}.ready")
    sentinel.unlink(missing_ok=True)

    print(f"=== Phase A: run partway, then get SIGKILLed from outside (thread_id={thread_id}) ===")
    proc_a = subprocess.Popen(
        [sys.executable, script, "--phase-a", thread_id, str(sentinel)], env=env
    )
    deadline = time.time() + 30
    while not sentinel.exists():
        if time.time() > deadline:
            proc_a.kill()
            raise SystemExit("Phase A never reached the checkpoint, timed out waiting for sentinel")
        time.sleep(0.1)

    print(f"[orchestrator] sentinel seen, phase A (pid {proc_a.pid}) is now blocked mid-run")
    print(f"[orchestrator] sending SIGKILL to pid {proc_a.pid}")
    proc_a.kill()  # SIGKILL, no signal handler, no cleanup, a real kill
    proc_a.wait()
    sentinel.unlink(missing_ok=True)
    print(f"[orchestrator] phase A is dead (returncode {proc_a.returncode})\n")

    print(f"=== Phase B: fresh process, resume thread_id={thread_id} ===")
    proc_b = subprocess.run([sys.executable, script, "--phase-b", thread_id], env=env)
    if proc_b.returncode != 0:
        raise SystemExit(f"Phase B failed with exit code {proc_b.returncode}")

    print("\n=== DEMO PASSED: checkpoint survived a killed process, resumed in a new one. ===")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--phase-a":
        _run_phase_a(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "--phase-b":
        _run_phase_b(sys.argv[2])
    else:
        main()
