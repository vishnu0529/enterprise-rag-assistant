import os
from unittest.mock import patch

from app.core.version import _resolve_code_version


def test_resolves_a_real_git_sha_by_default():
    version = _resolve_code_version()
    assert version != "unknown"
    assert len(version) == 12
    assert all(c in "0123456789abcdef" for c in version)


def test_env_override_takes_precedence_over_git():
    with patch.dict(os.environ, {"GIT_COMMIT_SHA": "deadbeef1234extra"}):
        assert _resolve_code_version() == "deadbeef1234"


def test_falls_back_to_unknown_if_git_is_unavailable():
    with patch("subprocess.run", side_effect=FileNotFoundError("no git binary")):
        assert _resolve_code_version() == "unknown"
