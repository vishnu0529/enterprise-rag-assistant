"""One-command rollback — scorecard item 13.

Wipes the vector store and the documents table, then re-ingests
sample_docs/proposal_corpus/ from either the current working tree or a
specific git ref, restoring a known-good state in a single command. This is
the answer to "the last deploy's corpus/config regressed something — put it
back" without hand-reconstructing what was ingested.

Usage:
    ./venv/bin/python scripts/rollback.py                # current working tree
    ./venv/bin/python scripts/rollback.py 96bf20e         # a specific commit/tag
"""

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select

from app.core.db import engine, init_db
from app.models.schemas import Document
from app.services.ingestion import chunk_document, load_text
from app.services.vector_store import reset_collection, upsert_chunks

ROOT = Path(__file__).resolve().parent.parent
CORPUS_RELATIVE = "sample_docs/proposal_corpus"


def _corpus_dir_for_ref(ref: str | None) -> Path:
    if ref is None:
        return ROOT / CORPUS_RELATIVE

    listing = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref, "--", CORPUS_RELATIVE],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if not listing:
        raise SystemExit(f"No files found under {CORPUS_RELATIVE} at ref '{ref}'.")

    tmp_dir = Path(tempfile.mkdtemp(prefix="rollback-corpus-"))
    for rel_path in listing.splitlines():
        content = subprocess.run(
            ["git", "show", f"{ref}:{rel_path}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        (tmp_dir / Path(rel_path).name).write_text(content)
    return tmp_dir


def _wipe_documents_table() -> None:
    with Session(engine) as session:
        docs = session.exec(select(Document)).all()
        for doc in docs:
            session.delete(doc)
        session.commit()
        print(f"Wiped {len(docs)} row(s) from the documents table.")


def main() -> None:
    ref = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"Rolling back to corpus at: {ref or 'current working tree'}")

    init_db()
    corpus_dir = _corpus_dir_for_ref(ref)

    print("Resetting vector store...")
    reset_collection()

    _wipe_documents_table()

    print(f"Re-ingesting corpus from {corpus_dir}...")
    total_chunks = 0
    with Session(engine) as session:
        for i, doc_path in enumerate(sorted(corpus_dir.glob("*.md"))):
            document_id = f"rollback-doc-{i}"
            pages = load_text(doc_path)
            chunks = chunk_document(document_id, doc_path.name, pages)
            upsert_chunks(chunks)
            # /chat short-circuits to "no documents" based on this table, not
            # the vector store directly — skipping this row would silently
            # break chat even though the corpus was correctly re-ingested.
            session.add(Document(id=document_id, filename=doc_path.name, num_chunks=len(chunks)))
            total_chunks += len(chunks)
            print(f"  {doc_path.name}: {len(chunks)} chunks")
        session.commit()

    print(f"\nRollback complete: {total_chunks} chunks re-ingested from a known-good corpus.")


if __name__ == "__main__":
    main()
