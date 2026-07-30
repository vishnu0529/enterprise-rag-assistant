import uuid
from pathlib import Path

import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt"}


def load_text(file_path: Path) -> list[dict]:
    """Returns one entry per page for PDFs ({"text", "page"}), or a single
    entry with page=None for markdown/plain text."""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        pages = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append({"text": text, "page": i})
        return pages
    if suffix in {".md", ".txt"}:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        return [{"text": text, "page": None}] if text.strip() else []
    raise ValueError(f"Unsupported file type: {suffix}")


def chunk_document(document_id: str, filename: str, pages: list[dict]) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
    )
    chunks = []
    chunk_index = 0
    for page in pages:
        for piece in splitter.split_text(page["text"]):
            if not piece.strip():
                continue
            chunks.append(
                {
                    "chunk_id": str(uuid.uuid4()),
                    "document_id": document_id,
                    "filename": filename,
                    "text": piece,
                    "page": page["page"],
                    "chunk_index": chunk_index,
                }
            )
            chunk_index += 1
    return chunks
