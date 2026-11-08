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
and a local SQLite file (`sessions.db`). Zero external services required.

## Docker Compose (full production-shaped stack)

```bash
docker compose up --build
```

Brings up the API alongside a real Qdrant service and Postgres, wired via
`QDRANT_URL` and `DATABASE_URL` (same application code, different config,
see `docs/ARCHITECTURE.md`). Set `GOOGLE_API_KEY` in your shell environment
or a `.env` file before running; `docker-compose.yml` passes it through.

```bash
export GOOGLE_API_KEY=...
docker compose up --build
curl localhost:8000/health
```

> **Verification note:** this was developed on a machine without Docker
> installed, so `docker compose up` itself has not been executed end-to-end
> here. The compose file has been syntax-validated (see the commit that
> introduced it), and the application code it runs has been proven correct
> via direct `uvicorn`/`curl` testing. Please verify `docker compose up`
> works on your machine before relying on it, and open an issue if it
> doesn't, happy to fix promptly.

## Running the evaluation suite

```bash
python scripts/run_evaluation.py
```

Ingests every file in `sample_docs/proposal_corpus/`, runs the 6-question
fixed eval set through the real RAG pipeline, and writes results to
`docs/EVALUATION.md`. Requires a working `GOOGLE_API_KEY` (or Anthropic key)
with available quota. See `docs/EVALUATION.md` for the current status of a
live run against this project's own API key.

## Cloud deployment

**Live**, as two separate services (this app is two-tier: a FastAPI backend
plus a Streamlit dashboard that calls it over HTTP, so one PaaS deploy
alone doesn't cover both halves):

### Backend on Render

1. New Web Service → point at this repo. Render auto-detects the `Dockerfile`.
2. Environment variables: `GOOGLE_API_KEY` (or `ANTHROPIC_API_KEY` +
   `LLM_PROVIDER=anthropic`), and `API_KEY` set to a real random secret,
   see "Securing a public deployment" below. Leave `QDRANT_URL`/`DATABASE_URL`
   unset to use embedded Qdrant + SQLite (dev-mode); Render's free-tier disk
   is ephemeral, so ingested documents don't survive a redeploy or restart.
3. Confirm with `curl https://<your-service>.onrender.com/health`.

Real deployment surfaced three bugs no amount of local testing caught,
fixed in order: the Dockerfile hardcoded port 8000 instead of reading
Render's injected `PORT`; `sentence-transformers`+`torch`'s baseline memory
footprint alone OOM'd the free tier's 512MB limit (swapped to `fastembed`,
an ONNX-based embedding library with a much smaller footprint); and
`draft_node`'s LLM call had no exception handling, so a real API error
surfaced as a raw 500 instead of a clean message. All three are fixed on
`main`, mentioned here so a future "why does X work this way" has an
answer, not just "it does."

### Dashboard on Streamlit Community Cloud

1. New app → point at this repo, main file `dashboard.py`.
2. **Set the app to public** under Settings → Sharing. It defaults to
   restricted/invite-only, which silently redirects visitors to a login
   page instead of the dashboard.
3. Add `API_KEY` (same value as the backend's) to the app's **Secrets**,
   not as a regular env var, because Streamlit Cloud secrets aren't exposed to
   visitors, and the dashboard's requests to the backend happen
   server-side (Streamlit's Python process calling the FastAPI backend),
   never from the visitor's browser, so the key never reaches them either.
4. Update `dashboard.py`'s `API_BASE` constant to your deployed backend URL.

### Securing a public deployment

This app has no user accounts, but `app/core/auth.py` resolves each
request's `X-API-Key` header to a specific user identity (not just "yes/no,
this request has the secret"). Required on `/documents`, `/chat`, and
`/evaluate` (not `/health`, so platform health checks keep working). Create
`api_keys.json` at the repo root (copy `api_keys.json.example`, it's
gitignored) mapping each real key to a `user_id`; deploy it as a Render
secret file, or fall back to the single legacy `API_KEY` env var (mapped to
user_id `"default"`) if you don't need per-user attribution. Leave both
unset for local dev (the gate is a no-op when empty).

**Only ever ingest synthetic/sample documents into a public deployment.**
Per-user keys mean you can now tell *who* asked for *what* (chat sessions
and trace spans carry the resolved user_id), and the document corpus is now
scoped per owner — each ingested document is stamped with the resolved
user_id, and retrieval, listing, and deletion are all filtered to it, so one
key can no longer read or remove another key's documents. A real
tuition-payment letter with bank details and a home address was uploaded to
this deployment during testing and had to be deleted; the synthetic
documents in `sample_docs/proposal_corpus/` are the kind of thing this
should hold instead, never a real client's proposals, CVs, or rate cards.
