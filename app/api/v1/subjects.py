# ──────────────────────────────────────────────────────────────
# app/api/v1/subjects.py
#
# WHY THIS FILE EXISTS:
#   HTTP route handlers for all subject operations.
#   Every route here is protected — `Depends(get_current_user)`
#   means FastAPI will reject the request with 401 if no valid
#   JWT token is present in the Authorization header.
#
#   Routes are intentionally thin:
#     1. Extract data from the request
#     2. Call the service function
#     3. Return the response schema
#
# Endpoints:
#   POST   /api/v1/subjects           → Create a subject
#   GET    /api/v1/subjects           → List current user's subjects
#   GET    /api/v1/subjects/{id}      → Get one subject by ID
#   PATCH  /api/v1/subjects/{id}      → Partial update a subject
#   DELETE /api/v1/subjects/{id}      → Delete a subject
# ──────────────────────────────────────────────────────────────

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.subject import (
    SubjectCreate,
    SubjectListResponse,
    SubjectResponse,
    SubjectUpdate,
)
from app.services import subject_service

router = APIRouter()


# ── POST / — Create a subject ─────────────────────────────────
@router.post(
    "/",
    response_model=SubjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new subject",
)
def create_subject(
    subject_data: SubjectCreate,
    current_user: User = Depends(get_current_user),  # JWT required
    db: Session = Depends(get_db),
) -> SubjectResponse:
    """
    Create a new subject for the authenticated student.

    The subject is automatically owned by the user making the request —
    `user_id` is taken from the JWT token, never from the request body.

    **Request body:**
    ```json
    {
        "name": "Data Structures",
        "description": "CS201 — Trees, graphs, sorting algorithms",
        "color": "#6366f1",
        "exam_date": "2025-05-15"
    }
    ```
    """
    subject = subject_service.create_subject(
        db=db,
        user_id=current_user.id,   # From the verified JWT — never the client
        subject_data=subject_data,
    )
    return SubjectResponse.model_validate(subject)


# ── GET / — List all subjects ─────────────────────────────────
@router.get(
    "/",
    response_model=SubjectListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all subjects for the current user",
)
def list_subjects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubjectListResponse:
    """
    Return all subjects owned by the authenticated student.

    Students only see their own subjects — this is enforced at the
    service layer by filtering on user_id.

    **Response:**
    ```json
    {
        "subjects": [...],
        "total": 3
    }
    ```
    """
    subjects = subject_service.get_subjects(db=db, user_id=current_user.id)

    return SubjectListResponse(
        subjects=[SubjectResponse.model_validate(s) for s in subjects],
        total=len(subjects),
    )


# ── GET /{id} — Get one subject ───────────────────────────────
@router.get(
    "/{subject_id}",
    response_model=SubjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a specific subject by ID",
)
def get_subject(
    subject_id: int,                              # Extracted from the URL path
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubjectResponse:
    """
    Fetch a single subject by its ID.

    Returns 404 if the subject doesn't exist OR belongs to a different user.
    We deliberately don't distinguish between these two cases for security.
    """
    subject = subject_service.get_subject_by_id(
        db=db,
        subject_id=subject_id,
        user_id=current_user.id,
    )
    return SubjectResponse.model_validate(subject)


# ── PATCH /{id} — Update a subject ───────────────────────────
@router.patch(
    "/{subject_id}",
    response_model=SubjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Partially update a subject",
)
def update_subject(
    subject_id: int,
    update_data: SubjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubjectResponse:
    """
    Update one or more fields of a subject.

    PATCH semantics: only fields included in the request body are changed.
    Omit any field you don't want to modify.

    **Example — update only the exam date:**
    ```json
    {
        "exam_date": "2025-06-01"
    }
    ```
    """
    subject = subject_service.update_subject(
        db=db,
        subject_id=subject_id,
        user_id=current_user.id,
        update_data=update_data,
    )
    return SubjectResponse.model_validate(subject)


# ── DELETE /{id} — Delete a subject ──────────────────────────
@router.delete(
    "/{subject_id}",
    status_code=status.HTTP_204_NO_CONTENT,  # 204 = success with no response body
    summary="Delete a subject and all its data",
)
def delete_subject(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Permanently delete a subject and all associated documents.

    This is irreversible. All documents, chat history, quiz attempts,
    and progress data for this subject will be deleted via cascade.

    Returns HTTP 204 No Content on success (no response body).
    """
    subject_service.delete_subject(
        db=db,
        subject_id=subject_id,
        user_id=current_user.id,
    )
    # Returning None with status_code=204 is correct FastAPI convention
