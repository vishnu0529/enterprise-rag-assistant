# Contributing

This is a personal portfolio project, not an actively-maintained
open-source project looking for outside contributors. This file exists to
document the engineering standards the project holds itself to, and as a
local dev setup reference for anyone forking or reviewing it.

## Local setup

```bash
git clone https://github.com/vishnu0529/enterprise-rag-assistant.git
cd enterprise-rag-assistant

python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# set GOOGLE_API_KEY (or ANTHROPIC_API_KEY + LLM_PROVIDER=anthropic)
```

## Before committing

```bash
ruff check .            # lint
ruff format .           # format
pytest -q               # 35 tests, ~15s, no network/model download required
```

All three must be clean. CI (`.github/workflows/ci.yml`) runs the same
checks plus a Docker build on every push.

## Conventions

- **Python 3.11**, modern type hints (`X | None`, not `Optional[X]`)
- **No comments explaining *what* code does** — only *why*, when it's a
  non-obvious constraint, workaround, or invariant. Well-named code should
  speak for itself.
- **Tests mock LLM/model calls** — no network access or model downloads in
  CI. Anything that genuinely needs a live LLM call (e.g. a real evaluation
  run) is a manual step documented in [docs/EVALUATION.md](docs/EVALUATION.md),
  not part of the automated test suite.
- **New features degrade gracefully.** Phase 2's hybrid search, reranking,
  and query rewriting are each an independent config flag
  (`app/core/config.py`) that falls back to the prior, simpler behavior
  when disabled or when a dependency fails — see `app/services/rag_chain.py`.
- **Commits are staged logically**, one concern per commit, not squashed
  into a single dump — see the git history for the pattern.

## Reporting issues

Since this isn't an actively-developed shared project, issues/PRs may not
get a response. If you're evaluating this as a portfolio piece and have
feedback, reach out via the contact info on the author's GitHub profile
instead.
