import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

from app.core.db import get_session
from app.models.schemas import Document, DocumentOut, IngestResponse
from app.services.ingestion import SUPPORTED_EXTENSIONS, chunk_document, load_text
from app.services.vector_store import delete_document, upsert_chunks

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = Path("uploaded_docs")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("", response_model=IngestResponse)
async def ingest_document(file: UploadFile = File(...), session: Session = Depends(get_session)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported file type '{suffix}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    document_id = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{document_id}{suffix}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    pages = load_text(dest)
    if not pages:
        raise HTTPException(400, "No extractable text found in document")

    chunks = chunk_document(document_id, file.filename, pages)
    if not chunks:
        raise HTTPException(400, "Document produced no usable chunks")

    upsert_chunks(chunks)

    doc = Document(id=document_id, filename=file.filename, num_chunks=len(chunks))
    session.add(doc)
    session.commit()

    return IngestResponse(document_id=document_id, filename=file.filename, num_chunks=len(chunks))


@router.get("", response_model=list[DocumentOut])
def list_documents(session: Session = Depends(get_session)):
    return session.exec(select(Document)).all()


@router.delete("/{document_id}")
def remove_document(document_id: str, session: Session = Depends(get_session)):
    doc = session.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    delete_document(document_id)
    session.delete(doc)
    session.commit()
    return {"deleted": document_id}
