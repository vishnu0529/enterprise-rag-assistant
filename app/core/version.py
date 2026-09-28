"""Answers to "which config/prompt version produced this past answer?"
(scorecard item 12). The honest signal for that here is the exact git
commit of the running code, not a hand-maintained version number. Prompts
(SYSTEM_PROMPT, STRATEGIST_SYSTEM_PROMPT) and settings live as code/env,
not a separately-versioned prompt-management system, so the commit SHA
*is* the prompt version. Inventing a second, parallel version number would
just be one more thing to forget to bump.

CODE_VERSION resolves once per process, in order:
1. GIT_COMMIT_SHA env var: set this at deploy time (Render/Docker build arg)
   where the .git directory usually isn't shipped in the image.
2. `git rev-parse HEAD`: works in local dev and CI, where .git exists.
3. "unknown": never raises; a missing version is a documentation gap, not
   a reason to fail a chat request.
"""

import os
import subprocess
from pathlib import Path


def _resolve_code_version() -> str:
    env_sha = os.environ.get("GIT_COMMIT_SHA")
    if env_sha:
        return env_sha[:12]
    try:
        repo_root = Path(__file__).resolve().parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout.strip()[:12]
    except Exception:
        return "unknown"


CODE_VERSION = _resolve_code_version()
