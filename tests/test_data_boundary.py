from unittest.mock import patch

import pytest

from app.services.data_boundary import DataBoundaryViolation, check_text, enforce

SAFE_TEXT = "Aldermere Advisory's day rate for a Senior Consultant is £1,050."
SORT_CODE_TEXT = "Please pay into account sort code 12-34-56 as agreed."
ACCOUNT_NUMBER_TEXT = "Our account number: 12345678 for this invoice."
NI_NUMBER_TEXT = "National Insurance number AB123456C is on file."


def test_check_text_finds_nothing_in_safe_text():
    assert check_text(SAFE_TEXT) == []


def test_check_text_flags_sort_code():
    findings = check_text(SORT_CODE_TEXT)
    assert any("sort code" in f for f in findings)


def test_check_text_flags_account_number():
    findings = check_text(ACCOUNT_NUMBER_TEXT)
    assert any("account number" in f for f in findings)


def test_check_text_flags_ni_number():
    findings = check_text(NI_NUMBER_TEXT)
    assert any("National Insurance" in f for f in findings)


def test_enforce_raises_in_block_mode():
    with patch("app.services.data_boundary.settings") as mock_settings:
        mock_settings.DATA_BOUNDARY_MODE = "block"
        with pytest.raises(DataBoundaryViolation):
            enforce(SORT_CODE_TEXT)


def test_enforce_does_not_raise_on_safe_text():
    with patch("app.services.data_boundary.settings") as mock_settings:
        mock_settings.DATA_BOUNDARY_MODE = "block"
        enforce(SAFE_TEXT)  # no exception


def test_enforce_warns_but_allows_in_warn_mode():
    with patch("app.services.data_boundary.settings") as mock_settings:
        mock_settings.DATA_BOUNDARY_MODE = "warn"
        enforce(SORT_CODE_TEXT)  # no exception, just a log line


def test_enforce_is_a_no_op_when_off():
    with patch("app.services.data_boundary.settings") as mock_settings:
        mock_settings.DATA_BOUNDARY_MODE = "off"
        enforce(SORT_CODE_TEXT)  # no exception even though it would match
