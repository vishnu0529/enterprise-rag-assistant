"""Data-boundary check for document ingestion — scorecard item 10.

This exists because of a real incident (docs/DEPLOYMENT.md): a tuition
payment letter containing bank details and a home address was uploaded to
the public demo deployment and had to be manually deleted. The shared
API-key gate stops anonymous traffic, but it does nothing to stop someone
who *has* the key from uploading a real, sensitive document — this is the
control that would have actually caught that specific incident.

These are illustrative pattern-matching heuristics, not a compliance-grade
PII scanner — they catch the shape of the problem this project already hit
once (UK bank details, UK National Insurance numbers), not every possible
category of sensitive data. The only real fix for a public deployment is
still "only ever ingest synthetic/sample documents" (see docs/DEPLOYMENT.md)
— this is a safety net behind that rule, not a replacement for it.
"""

import logging
import re

from app.core.config import settings

logger = logging.getLogger(__name__)

_PATTERNS: dict[str, re.Pattern] = {
    "UK bank sort code (NN-NN-NN)": re.compile(r"\b\d{2}-\d{2}-\d{2}\b"),
    "UK bank account number (8 digits, labelled)": re.compile(
        r"\baccount\s*(?:number|no\.?|#)?\s*[:\-]?\s*\d{8}\b", re.IGNORECASE
    ),
    "UK National Insurance number": re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]\b"),
}


class DataBoundaryViolation(Exception):
    def __init__(self, findings: list[str]):
        self.findings = findings
        super().__init__(f"Data-boundary check found: {', '.join(findings)}")


def check_text(text: str) -> list[str]:
    """Returns human-readable descriptions of every sensitive-data pattern
    found in text. An empty list means nothing was flagged."""
    return [label for label, pattern in _PATTERNS.items() if pattern.search(text)]


def enforce(text: str) -> None:
    """Raises DataBoundaryViolation if DATA_BOUNDARY_MODE is 'block' and text
    matches a sensitive-data pattern. In 'warn' mode, logs the findings but
    lets ingestion proceed. No-op in 'off' mode."""
    if settings.DATA_BOUNDARY_MODE == "off":
        return
    findings = check_text(text)
    if not findings:
        return
    if settings.DATA_BOUNDARY_MODE == "block":
        raise DataBoundaryViolation(findings)
    logger.warning("Data-boundary check found (mode=warn, ingestion allowed): %s", findings)
