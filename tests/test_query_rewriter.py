from unittest.mock import patch

from app.services.llm_client import LLMResult
from app.services.query_rewriter import rewrite_query


def test_rewrite_query_without_history_skips_llm_call():
    with patch("app.services.query_rewriter.call_llm") as mock_call:
        result = rewrite_query("How many annual leave days?", history=None)

    assert result == "How many annual leave days?"
    mock_call.assert_not_called()


def test_rewrite_query_with_history_returns_llm_rewrite():
    history = [
        {"role": "user", "content": "How many annual leave days do employees get?"},
        {"role": "assistant", "content": "25 days, rising to 30 after 5 years."},
    ]
    fake_result = LLMResult(
        text='"What is the parental leave policy?"', prompt_tokens=10, completion_tokens=5
    )

    with patch("app.services.query_rewriter.call_llm", return_value=fake_result) as mock_call:
        result = rewrite_query("What about the parental leave one?", history=history)

    assert result == "What is the parental leave policy?"  # surrounding quotes stripped
    mock_call.assert_called_once()


def test_rewrite_query_falls_back_to_original_on_llm_failure():
    history = [{"role": "user", "content": "earlier question"}]

    with patch("app.services.query_rewriter.call_llm", side_effect=ValueError("quota exceeded")):
        result = rewrite_query("follow up question", history=history)

    assert result == "follow up question"


def test_rewrite_query_falls_back_when_llm_returns_empty_string():
    history = [{"role": "user", "content": "earlier question"}]
    fake_result = LLMResult(text="   ", prompt_tokens=1, completion_tokens=1)

    with patch("app.services.query_rewriter.call_llm", return_value=fake_result):
        result = rewrite_query("follow up question", history=history)

    assert result == "follow up question"
