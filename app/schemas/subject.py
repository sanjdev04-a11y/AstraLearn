# ──────────────────────────────────────────────────────────────
# app/schemas/subject.py
#
# WHY THIS FILE EXISTS:
#   Defines the Pydantic shapes for Subject data flowing in/out
#   of the API. Completely separate from the SQLAlchemy model.
#
# Schema naming pattern (consistent across all modules):
#   SubjectCreate   → fields the client sends to CREATE a subject
#   SubjectUpdate   → fields the client sends to UPDATE (all optional)
#   SubjectResponse → what we return to the client
#
# ── Why not one schema for everything? ───────────────────────
#   - Create:   client provides name/description, NOT id/user_id/timestamps
#   - Update:   all fields optional (partial update / PATCH semantics)
#   - Response: includes id, user_id, timestamps — which client never sends
#
#   Mixing these would force ugly workarounds (Optional on required fields,
#   or accidentally accepting user_id from the client, which is a security risk).
# ──────────────────────────────────────────────────────────────

import re
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


# ── Request Schemas ───────────────────────────────────────────

class SubjectCreate(BaseModel):
    """
    Body for POST /api/v1/subjects — create a new subject.

    The user_id is NOT in this schema because we get it from the
    JWT token (current_user.id), not from the client.
    Accepting user_id from the client would be a security hole —
    a student could create subjects owned by other users.
    """

    name: str = Field(
        min_length=1,
        max_length=255,
        description="Subject name, e.g. 'Data Structures'",
    )

    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional description of the subject",
    )

    color: str = Field(
        default="#6366f1",
        description="Hex color for UI display, e.g. '#6366f1'",
    )

    exam_date: date | None = Field(
        default=None,
        description="Optional exam date — used by the Planner Agent",
    )

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Subject name cannot be blank")
        return v

    @field_validator("color")
    @classmethod
    def color_must_be_valid_hex(cls, v: str) -> str:
        """Validate that color is a proper hex color code like #6366f1."""
        if not re.match(r"^#[0-9a-fA-F]{6}$", v):
            raise ValueError(
                "Color must be a valid hex code (e.g. '#6366f1')"
            )
        return v.lower()

    @field_validator("exam_date")
    @classmethod
    def exam_date_must_be_future(cls, v: date | None) -> date | None:
        """Exam date should not be in the past."""
        if v is not None and v < date.today():
            raise ValueError("Exam date cannot be in the past")
        return v


class SubjectUpdate(BaseModel):
    """
    Body for PATCH /api/v1/subjects/{id} — partial update.

    ALL fields are optional. Only the supplied fields will be updated.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    description: str | None = Field(
        default=None,
        max_length=2000,
    )

    color: str | None = Field(
        default=None,
    )

    exam_date: date | None = Field(
        default=None,
    )

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Subject name cannot be blank")
        return v

    @field_validator("color")
    @classmethod
    def color_must_be_valid_hex(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^#[0-9a-fA-F]{6}$", v):
            raise ValueError(
                "Color must be a valid hex code (e.g. '#6366f1')"
            )
        return v.lower() if v else v


# ── Response Schemas ──────────────────────────────────────────

class SubjectResponse(BaseModel):
    """
    What the API returns when representing a subject.

    Includes all fields needed by the frontend.
    """

    id: int
    user_id: int
    name: str
    description: str | None
    color: str
    exam_date: date | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubjectListResponse(BaseModel):
    """
    Wrapper for returning a list of subjects with a total count.
    """

    subjects: list[SubjectResponse]
    total: int