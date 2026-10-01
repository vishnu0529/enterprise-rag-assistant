import re
import uuid
from pathlib import Path

import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt"}

_MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s.*$", re.MULTILINE)


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
        # The splitter has no notion of markdown structure, so a heading can
        # land at the very end of one piece and its body text at the start
        # of the next, leaving that next chunk's embedding with no idea what
        # section it's from. Track the most recently seen heading per page
        # and re-attach it to any piece that doesn't already open with one.
        current_heading = None
        for piece in splitter.split_text(page["text"]):
            if not piece.strip():
                continue
            needs_heading = current_heading is not None and not piece.lstrip().startswith("#")
            headings_in_piece = _MARKDOWN_HEADING_RE.findall(piece)
            if headings_in_piece:
                current_heading = headings_in_piece[-1]
            if needs_heading:
                piece = f"{current_heading}\n\n{piece}"
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
