# ──────────────────────────────────────────────────────────────
# app/api/v1/documents.py
#
# WHY THIS FILE EXISTS:
#   HTTP route handlers for document operations.
#   All routes are nested under /subjects/{subject_id}/documents
#   because documents always belong to a subject.
#
# ── File upload in FastAPI ────────────────────────────────────
#   Unlike JSON endpoints, file uploads use:
#     - `UploadFile` for the file itself
#     - `Form(...)` for any accompanying text fields
#     - Content-Type: multipart/form-data (not application/json)
#
#   You CANNOT use a Pydantic schema for the request body in a
#   file upload endpoint — FastAPI handles multipart differently.
#   The route declares each field individually instead.
#
# Endpoints:
#   POST   /api/v1/subjects/{subject_id}/documents
#   GET    /api/v1/subjects/{subject_id}/documents
#   GET    /api/v1/subjects/{subject_id}/documents/{doc_id}
#   PATCH  /api/v1/subjects/{subject_id}/documents/{doc_id}
#   DELETE /api/v1/subjects/{subject_id}/documents/{doc_id}
# ──────────────────────────────────────────────────────────────

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session
from app.models.document import DocumentStatus
from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdateRequest,
)
from app.services import document_service

router = APIRouter()


# ── POST / — Upload a document ────────────────────────────────
@router.post(
    "/",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document to a subject",
)
def upload_document(
    subject_id: int,                              # From the URL path parameter
    file: UploadFile = File(...),                 # The actual file bytes
    description: str | None = Form(default=None), # Optional text field alongside file
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """
    Upload a PDF, TXT, or DOCX file to a subject.

    The file is saved to disk and recorded in the database.
    After upload, `is_processed` is `false` — the RAG pipeline
    will process it asynchronously and flip it to `true`.

    **Content-Type: multipart/form-data** (not JSON)

    **Form fields:**
    - `file`: The file to upload (required)
    - `description`: Optional note about the document

    **Supported formats:** PDF, TXT, DOCX
    **Max size:** configured in settings (default 20 MB)
    """

    # ── Step 1: Save file to disk ─────────────────────────────
    # save_upload_file validates the file type and size,
    # then writes it to uploads/{user_id}/{subject_id}/
    file_metadata = document_service.save_upload_file(
        file=file,
        user_id=current_user.id,
        subject_id=subject_id,
    )

    # ── Step 2: Record in database ────────────────────────────
    # create_document also verifies the subject exists and belongs
    # to this user (via get_subject_by_id inside get_documents)
    doc = document_service.create_document(
        db=db,
        user_id=current_user.id,
        subject_id=subject_id,
        file_metadata=file_metadata,
        description=description,
    )

    return DocumentResponse.model_validate(doc)


# ── GET / — List documents ────────────────────────────────────
@router.get(
    "/",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all documents in a subject",
)
def list_documents(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    """
    Return all documents uploaded to a subject.

    Includes a `processing_count` field showing how many documents
    are still being processed by the RAG pipeline.

    Results are ordered newest first.
    """

    docs = document_service.get_documents(
        db=db,
        subject_id=subject_id,
        user_id=current_user.id,
    )

    doc_responses = [DocumentResponse.model_validate(d) for d in docs]

    # Count how many are still awaiting RAG processing
    processing_count = sum(
    1
    for d in doc_responses
    if d.status == DocumentStatus.PROCESSING
)

    failed_count = sum(
    1
    for d in doc_responses
    if d.status == DocumentStatus.FAILED
)

    return DocumentListResponse(
    documents=doc_responses,
    total=len(doc_responses),
    processing_count=processing_count,
    failed_count=failed_count,
)


# ── GET /{doc_id} — Get one document ─────────────────────────
@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a specific document's metadata",
)
def get_document(
    subject_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """
    Fetch metadata for a single document.

    Returns 404 if:
    - Document doesn't exist
    - Document is in a different subject
    - Document belongs to a different user
    """

    doc = document_service.get_document_by_id(
        db=db,
        document_id=document_id,
        subject_id=subject_id,
        user_id=current_user.id,
    )
    return DocumentResponse.model_validate(doc)


# ── PATCH /{doc_id} — Update description ─────────────────────
@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a document's description",
)
def update_document(
    subject_id: int,
    document_id: int,
    update_data: DocumentUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """
    Update a document's description.

    File content is immutable — to change the file, delete and re-upload.

    **Request body:**
    ```json
    {
        "description": "Week 3 lecture — covers binary trees"
    }
    ```
    """

    doc = document_service.update_document(
        db=db,
        document_id=document_id,
        subject_id=subject_id,
        user_id=current_user.id,
        update_data=update_data,
    )
    return DocumentResponse.model_validate(doc)


# ── DELETE /{doc_id} — Delete a document ─────────────────────
@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
)
def delete_document(
    subject_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Permanently delete a document and its file from disk.

    Also removes the document's vector embeddings from Qdrant
    (implemented in Module 5 when RAG pipeline is built).

    Returns HTTP 204 No Content on success.
    """

    document_service.delete_document(
        db=db,
        document_id=document_id,
        subject_id=subject_id,
        user_id=current_user.id,
    )
