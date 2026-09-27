from unittest.mock import patch

from langgraph.checkpoint.memory import MemorySaver

import app.services.checkpointer as checkpointer_module
from app.services.checkpointer import get_checkpointer


def test_falls_back_to_memory_saver_for_sqlite(monkeypatch):
    checkpointer_module._checkpointer = None
    with patch.object(checkpointer_module.settings, "DATABASE_URL", "sqlite:///./sessions.db"):
        cp = get_checkpointer()
    assert isinstance(cp, MemorySaver)
    checkpointer_module._checkpointer = None


def test_caches_the_checkpointer_instance():
    checkpointer_module._checkpointer = None
    with patch.object(checkpointer_module.settings, "DATABASE_URL", "sqlite:///./sessions.db"):
        first = get_checkpointer()
        second = get_checkpointer()
    assert first is second
    checkpointer_module._checkpointer = None
