"""Structural validation for eval/golden_set.json. Runs with no API key and
no model load, so it stays in the normal CI test suite. It checks the golden
set itself is well-formed; scoring it against a live LLM is a separate,
manual step (scripts/run_golden_set.py) because that needs a real API key.
"""

import json
from pathlib import Path

import pytest

GOLDEN_SET_PATH = Path(__file__).resolve().parent.parent / "eval" / "golden_set.json"
CORPUS_DIR = Path(__file__).resolve().parent.parent / "sample_docs" / "proposal_corpus"


@pytest.fixture(scope="module")
def golden_set() -> dict:
    return json.loads(GOLDEN_SET_PATH.read_text())


def test_meta_counts_match_items(golden_set):
    items = golden_set["items"]
    meta = golden_set["_meta"]
    assert len(items) == meta["total_count"]
    assert meta["answerable_count"] + meta["trap_count"] == meta["total_count"]


def test_total_is_fifty_with_at_least_ten_traps(golden_set):
    items = golden_set["items"]
    assert len(items) == 50
    traps = [i for i in items if i["category"] == "trap"]
    assert len(traps) >= 10


def test_ids_are_unique(golden_set):
    ids = [i["id"] for i in golden_set["items"]]
    assert len(ids) == len(set(ids))


def test_answerable_items_have_answer_and_sources(golden_set):
    for item in golden_set["items"]:
        if item["category"] in ("factual", "multi_hop"):
            assert item.get("expected_answer"), f"{item['id']} missing expected_answer"
            assert item.get("source_docs"), f"{item['id']} missing source_docs"


def test_trap_items_expect_refusal(golden_set):
    for item in golden_set["items"]:
        if item["category"] == "trap":
            assert item.get("expected_behavior") == "refusal", (
                f"{item['id']} is a trap but doesn't expect a refusal"
            )
            assert item.get("notes"), f"{item['id']} trap should explain why it's unanswerable"


def test_source_docs_exist_in_corpus(golden_set):
    corpus_files = {p.name for p in CORPUS_DIR.glob("*.md")}
    for item in golden_set["items"]:
        for doc in item.get("source_docs", []):
            assert doc in corpus_files, f"{item['id']} references missing corpus file {doc}"
