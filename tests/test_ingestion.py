from pathlib import Path

import pytest

from app.services.ingestion import chunk_document, load_text


def test_load_text_markdown(tmp_path: Path):
    file_path = tmp_path / "doc.md"
    file_path.write_text("# Title\n\nSome body text.")

    pages = load_text(file_path)

    assert len(pages) == 1
    assert pages[0]["page"] is None
    assert "Some body text" in pages[0]["text"]


def test_load_text_empty_file_returns_no_pages(tmp_path: Path):
    file_path = tmp_path / "empty.txt"
    file_path.write_text("   \n  ")

    pages = load_text(file_path)

    assert pages == []


def test_load_text_unsupported_extension_raises(tmp_path: Path):
    file_path = tmp_path / "doc.docx"
    file_path.write_text("irrelevant")

    with pytest.raises(ValueError, match="Unsupported file type"):
        load_text(file_path)


def test_chunk_document_produces_sequential_indices():
    long_text = "Sentence number {}. " * 200
    pages = [{"text": long_text.format(*range(200)), "page": 1}]

    chunks = chunk_document("doc-1", "big.txt", pages)

    assert len(chunks) > 1
    assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))
    assert all(c["document_id"] == "doc-1" for c in chunks)
    assert all(c["filename"] == "big.txt" for c in chunks)
    assert all(c["page"] == 1 for c in chunks)


def test_chunk_document_tracks_page_numbers_across_pages():
    pages = [
        {"text": "Page one content here.", "page": 1},
        {"text": "Page two content here.", "page": 2},
    ]

    chunks = chunk_document("doc-2", "multi.pdf", pages)

    pages_seen = {c["page"] for c in chunks}
    assert pages_seen == {1, 2}


def test_chunk_document_skips_blank_pieces():
    pages = [{"text": "   \n\n   ", "page": 1}]

    chunks = chunk_document("doc-3", "blank.txt", pages)

    assert chunks == []
