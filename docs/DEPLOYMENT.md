# Deployment

## Local development (no Docker needed)

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set GOOGLE_API_KEY (or ANTHROPIC_API_KEY + LLM_PROVIDER=anthropic)

uvicorn app.main:app --reload
# in a second terminal:
streamlit run dashboard.py
```

This mode uses Qdrant's embedded local mode (`qdrant_data/` on disk, no server)
and a local SQLite file (`sessions.db`) — zero external services required.

## Docker Compose (full production-shaped stack)

```bash
docker compose up --build
```

Brings up the API alongside a real Qdrant service and Postgres, wired via
`QDRANT_URL` and `DATABASE_URL` (same application code, different config —
see `docs/ARCHITECTURE.md`). Set `GOOGLE_API_KEY` in your shell environment
or a `.env` file before running; `docker-compose.yml` passes it through.

```bash
export GOOGLE_API_KEY=...
docker compose up --build
curl localhost:8000/health
```

> **Verification note:** this was developed on a machine without Docker
> installed, so `docker compose up` itself has not been executed end-to-end
> here — the compose file has been syntax-validated (see the commit that
> introduced it), and the application code it runs has been proven correct
> via direct `uvicorn`/`curl` testing. Please verify `docker compose up`
> works on your machine before relying on it, and open an issue if it
> doesn't — happy to fix promptly.

## Running the evaluation suite

```bash
python scripts/run_evaluation.py
```

Ingests `sample_docs/company_handbook.md`, runs the 4-question fixed eval
set through the real RAG pipeline, and writes results to
`docs/EVALUATION.md`. Requires a working `GOOGLE_API_KEY` (or Anthropic key)
with available quota — see `docs/EVALUATION.md` for the current status of a
live run against this project's own API key.

## Cloud deployment

**Not yet implemented.** The natural next step (Railway or Render, matching
`ai-resume-matcher`'s deployment) is listed in the README's Future
Improvements — deferred this round to keep the backend/evaluation/Docker/CI
scope real and fully verified rather than partially done everywhere.
