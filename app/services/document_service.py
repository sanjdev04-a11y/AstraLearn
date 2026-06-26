

import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document, DocumentStatus
from app.schemas.document import DocumentUpdateRequest
from app.services.subject_service import get_subject_by_id

# ── Allowed file types ────────────────────────────────────────
# Maps MIME type → file extension label
# Only these types are accepted for upload.
ALLOWED_MIME_TYPES: dict[str, str] = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
}

# ── Max file size in bytes ────────────────────────────────────
# Computed once from settings so we don't repeat the calculation
MAX_FILE_SIZE_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


# ── Private helpers ───────────────────────────────────────────

def _build_upload_dir(user_id: int, subject_id: int) -> Path:
    """
    Build and ensure the upload directory path exists.

    Structure: {UPLOAD_DIR}/{user_id}/{subject_id}/

    Uses pathlib.Path for cross-platform path handling
    (works on Windows, macOS, Linux).

    Returns a Path object pointing to the directory.
    """
    upload_dir = Path(settings.UPLOAD_DIR) / str(user_id) / str(subject_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    # parents=True  → creates intermediate dirs (uploads/7/ first, then uploads/7/12/)
    # exist_ok=True → doesn't raise an error if the dir already exists
    return upload_dir


def _validate_upload_file(file: UploadFile, file_bytes: bytes) -> None:
    """
    Validate file type and size before saving.

    We validate AFTER reading the bytes (not just from the header)
    because the Content-Type header can be spoofed by clients.
    We only trust the MIME type they declare here for routing to
    the correct text extractor — actual content validation happens
    during RAG processing in Module 5.

    Raises:
        HTTPException 400: If file type not allowed or file too large
    """
    # ── Check file type ───────────────────────────────────────
    if file.content_type not in ALLOWED_MIME_TYPES:
        allowed = ", ".join(ALLOWED_MIME_TYPES.keys())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File type '{file.content_type}' is not supported. "
                f"Allowed types: {allowed}"
            ),
        )

    # ── Check file size ───────────────────────────────────────
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB} MB. "
                f"Your file is {len(file_bytes) / (1024*1024):.1f} MB."
            ),
        )

    # ── Check file is not empty ───────────────────────────────
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot upload an empty file.",
        )


# ── Public service functions ──────────────────────────────────

def save_upload_file(
    file: UploadFile,
    user_id: int,
    subject_id: int,
) -> dict:
    """
    Write an uploaded file to disk and return its saved metadata.

    Steps:
      1. Read all bytes from the UploadFile into memory
      2. Validate type and size
      3. Generate a UUID filename to prevent collisions/attacks
      4. Write bytes to the correct directory
      5. Return a dict of metadata to be stored in the DB

    Args:
        file:       FastAPI UploadFile object from the request
        user_id:    Owner's user ID (for directory structure)
        subject_id: Subject ID (for directory structure)

    Returns:
        Dict containing: original_filename, stored_filename,
                         file_path, file_type, file_size_bytes
    """

    # ── Step 1: Read file content into memory ─────────────────
    # We read ALL bytes first so we can:
    #   a) Know the exact file size
    #   b) Validate before touching the filesystem
    file_bytes = file.file.read()

    if not isinstance(file_bytes, bytes):
        raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unable to read uploaded file.",
    )

    # ── Step 2: Validate ──────────────────────────────────────
    _validate_upload_file(file=file, file_bytes=file_bytes)

    # ── Step 3: Generate safe stored filename ─────────────────
    # uuid4() generates a random UUID: "a3f92b1c-4d5e-4f6a-8b9c-0d1e2f3a4b5c"
    # We append the original extension so the RAG pipeline knows the file type
    original_filename = file.filename or "upload"
    file_extension = Path(original_filename).suffix.lower()  # e.g. ".pdf"
    stored_filename = f"{uuid.uuid4()}{file_extension}"      # e.g. "a3f9...b5c.pdf"

    # ── Step 4: Write to disk ─────────────────────────────────
    # ── Step 4: Write to disk ─────────────────────────────────
    upload_dir = _build_upload_dir(
        user_id=user_id,
        subject_id=subject_id,
    )

    file_path = upload_dir / stored_filename

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    if not file_path.exists():
        raise HTTPException(
            status_code=500,
            detail="File could not be saved."
        )

    # ── Step 5: Return metadata ───────────────────────────────
    return {
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "file_path": str(file_path),       # Store as string in DB
        "file_type": file.content_type,
        "file_size_bytes": len(file_bytes),
    }


def create_document(
    db: Session,
    user_id: int,
    subject_id: int,
    file_metadata: dict,
    description: str | None = None,
) -> Document:
    """
    Record an uploaded document in the database.

    This is called AFTER save_upload_file() succeeds.
    If DB insert fails, the file is already on disk — in a production
    system you'd want a cleanup job for orphaned files. For Phase 1,
    this is acceptable.

    Args:
        db:            Active database session
        user_id:       Owner's user ID
        subject_id:    Subject this document belongs to
        file_metadata: Dict returned by save_upload_file()
        description:   Optional description from the request form

    Returns:
        The newly created Document ORM object
    """

    new_doc = Document(
        user_id=user_id,
        subject_id=subject_id,
        original_filename=file_metadata["original_filename"],
        stored_filename=file_metadata["stored_filename"],
        file_path=file_metadata["file_path"],
        file_type=file_metadata["file_type"],
        file_size_bytes=file_metadata["file_size_bytes"],
        description=description,
        status=DocumentStatus.UPLOADED,
        chunk_count=None,
        processing_error=None,
    )

    db.add(new_doc)

    try:
        db.commit()
        db.refresh(new_doc)
    except Exception:
        db.rollback()
        raise
    return new_doc

def get_documents(
    db: Session,
    subject_id: int,
    user_id: int,
) -> list[Document]:
    """
    List all documents for a subject, with ownership check.

    First verifies the subject belongs to this user (raises 404 if not),
    then returns all documents for that subject.

    Args:
        db:         Active database session
        subject_id: The subject to list documents for
        user_id:    Authenticated user (ownership check)

    Returns:
        List of Document ORM objects, ordered by upload date (newest first)
    """
    # This raises 404 if subject doesn't exist or doesn't belong to user
    get_subject_by_id(db=db, subject_id=subject_id, user_id=user_id)

    return (
        db.query(Document)
        .filter(
            Document.subject_id == subject_id,
            Document.user_id == user_id,
        )
        .order_by(Document.created_at.desc())  # Newest first
        .all()
    )


def get_document_by_id(
    db: Session,
    document_id: int,
    subject_id: int,
    user_id: int,
) -> Document:
    """
    Fetch a single document by ID with full ownership check.

    Filters by document_id AND subject_id AND user_id — all three
    must match. This prevents:
      - Accessing documents from a different subject (even your own)
      - Accessing another user's documents

    Args:
        db:          Active database session
        document_id: The document's integer ID
        subject_id:  Must match the document's subject_id
        user_id:     Must match the document's user_id

    Returns:
        Document ORM object

    Raises:
        HTTPException 404: If not found or ownership check fails
    """

    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.subject_id == subject_id,
            Document.user_id == user_id,
        )
        .first()
    )

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with id {document_id} not found in this subject",
        )

    return doc


def delete_document(
    db: Session,
    document_id: int,
    subject_id: int,
    user_id: int,
) -> None:
    """
    Delete a document: remove the DB record AND the file from disk.

    Order matters:
      1. Fetch first (raises 404 if not found / not owned)
      2. Delete from DB
      3. Delete from disk (after DB success)

    Why DB first?
      If disk deletion fails, the DB record is already gone, which
      means the file becomes an orphan. This is acceptable for Phase 1.
      In production: use a background job to clean up orphaned files,
      or wrap both operations in a transaction with compensating actions.

    Args:
        db:          Active database session
        document_id: Document to delete
        subject_id:  Ownership check
        user_id:     Ownership check
    """

    doc = get_document_by_id(
        db=db,
        document_id=document_id,
        subject_id=subject_id,
        user_id=user_id,
    )

    file_path = doc.file_path   # Save path before deleting the record

    # ── Delete DB record first ────────────────────────────────
    db.delete(doc)
    db.commit()

    # ── Delete file from disk ─────────────────────────────────
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            parent_dir = Path(file_path).parent

            try:
                if parent_dir.exists() and not any(parent_dir.iterdir()):
                    parent_dir.rmdir()
            except OSError:
                pass
    except OSError as e:
        # Log the error but don't raise — the DB record is already gone.
        # A background cleanup job can handle orphaned files.
        print(f"Warning: Could not delete file {file_path}: {e}")


def update_document(
    db: Session,
    document_id: int,
    subject_id: int,
    user_id: int,
    update_data: DocumentUpdateRequest,
) -> Document:
    """
    Update a document's description (the only editable metadata field).

    File content is immutable after upload. To change the file,
    the student must delete it and re-upload.

    Args:
        db:          Active database session
        document_id: Document to update
        subject_id:  Ownership check
        user_id:     Ownership check
        update_data: Validated DocumentUpdateRequest

    Returns:
        The updated Document ORM object
    """

    doc = get_document_by_id(
        db=db,
        document_id=document_id,
        subject_id=subject_id,
        user_id=user_id,
    )

    changes = update_data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(doc, field, value)

    try:
        db.commit()
        db.refresh(doc)
    except Exception:
        db.rollback()
        raise
    return doc

def mark_document_processing(
    db: Session,
    document_id: int,
) -> Document:
    """
    Mark a document as currently being processed by the RAG pipeline.
    """

    doc = db.query(Document).filter(Document.id == document_id).first()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    doc.status = DocumentStatus.PROCESSING

    db.commit()
    db.refresh(doc)

    return doc
