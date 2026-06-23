# ──────────────────────────────────────────────────────────────
# app/services/subject_service.py
#
# WHY THIS FILE EXISTS:
#   All subject business logic lives here. Routes stay thin —
#   they just call these functions and return the results.
#
# ── Ownership enforcement — the core security rule ────────────
#   Every single query in this file filters by BOTH:
#     - The resource ID  (which subject?)
#     - The user ID      (does this student own it?)
#
#   This means:
#     - Student A cannot read Student B's subjects
#     - Student A cannot update Student B's subjects
#     - Student A cannot delete Student B's subjects
#
#   We return 404 (not 403) when a user tries to access a subject
#   they don't own. This is deliberate — we don't want to reveal
#   that the subject exists at all. (403 would confirm it exists.)
#
# Functions:
#   create_subject()      → Create a new subject for the current user
#   get_subjects()        → List all subjects owned by a user
#   get_subject_by_id()   → Fetch one subject (ownership enforced)
#   update_subject()      → Partial update (ownership enforced)
#   delete_subject()      → Delete a subject (ownership enforced)
# ──────────────────────────────────────────────────────────────

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.subject import Subject
from app.schemas.subject import SubjectCreate, SubjectUpdate


def create_subject(
    db: Session,
    user_id: int,
    subject_data: SubjectCreate,
) -> Subject:
    """
    Create a new subject owned by the given user.

    The user_id comes from the authenticated JWT token (extracted
    in the route handler via get_current_user). The client never
    sends user_id directly — it's always taken from the token.

    Args:
        db:           Active database session
        user_id:      ID of the authenticated user (from JWT)
        subject_data: Validated SubjectCreate schema

    Returns:
        The newly created Subject ORM object
    """

    new_subject = Subject(
        user_id=user_id,  # Always from the token — never the client
        name=subject_data.name.strip(),
        description=subject_data.description,
        color=subject_data.color,
        exam_date=subject_data.exam_date,
    )

    db.add(new_subject)
    db.commit()
    db.refresh(new_subject)

    return new_subject


def get_subjects(
    db: Session,
    user_id: int,
) -> list[Subject]:
    """
    Return all subjects belonging to a specific user.

    This query always filters by user_id — a student can ONLY
    see their own subjects, never another student's.

    Results are ordered by creation date (oldest first).

    Args:
        db:      Active database session
        user_id: ID of the authenticated user

    Returns:
        List of Subject ORM objects (may be empty)
    """

    return (
        db.query(Subject)
        .filter(Subject.user_id == user_id)
        .order_by(Subject.created_at.asc())
        .all()
    )


def get_subject_by_id(
    db: Session,
    subject_id: int,
    user_id: int,
) -> Subject:
    """
    Fetch a single subject by ID, enforcing ownership.

    We filter by BOTH subject_id AND user_id in one query.
    If the subject doesn't exist, OR belongs to another user,
    we return a 404.

    Args:
        db:         Active database session
        subject_id: Subject ID
        user_id:    Authenticated user ID

    Returns:
        Subject ORM object

    Raises:
        HTTPException(404)
    """

    subject = (
        db.query(Subject)
        .filter(
            Subject.id == subject_id,
            Subject.user_id == user_id,
        )
        .first()
    )

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with id {subject_id} not found",
        )

    return subject


def update_subject(
    db: Session,
    subject_id: int,
    user_id: int,
    update_data: SubjectUpdate,
) -> Subject:
    """
    Partially update a subject.

    Steps:
      1. Fetch subject (ownership enforced)
      2. Update only supplied fields
      3. Commit changes

    Args:
        db: Active database session
        subject_id: Subject to update
        user_id: Authenticated user
        update_data: SubjectUpdate schema

    Returns:
        Updated Subject ORM object
    """

    subject = get_subject_by_id(
        db=db,
        subject_id=subject_id,
        user_id=user_id,
    )

    changes = update_data.model_dump(exclude_unset=True)

    if not changes:
        return subject

    for field, value in changes.items():
        setattr(subject, field, value)

    db.commit()
    db.refresh(subject)

    return subject


def delete_subject(
    db: Session,
    subject_id: int,
    user_id: int,
) -> None:
    """
    Delete a subject and all associated data.

    Because Subject.documents uses:
        cascade="all, delete-orphan"

    deleting the subject automatically deletes all related
    documents as well.

    In future modules we'll also remove embeddings from
    Qdrant here.

    Args:
        db: Active database session
        subject_id: Subject to delete
        user_id: Authenticated user

    Raises:
        HTTPException(404)
    """

    subject = get_subject_by_id(
        db=db,
        subject_id=subject_id,
        user_id=user_id,
    )

    db.delete(subject)
    db.commit()

    # Route returns HTTP 204 No Content