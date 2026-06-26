# ──────────────────────────────────────────────────────────────
# app/models/subject.py
#
# WHY THIS FILE EXISTS:
#   Defines the `Subject` ORM model — each subject is a learning
#   area a student is studying (e.g. "Data Structures", "Calculus").
#
#   A subject BELONGS TO a user via a foreign key (user_id).
#   This is a classic one-to-many relationship:
#     One User → Many Subjects
#
# ── Foreign Key vs Relationship — What's the difference? ─────
#   Foreign Key (user_id column):
#     Lives in the DATABASE. PostgreSQL uses it to enforce that
#     every subject row points to a real user row.
#     Written as: ForeignKey("users.id")
#
#   Relationship (user attribute):
#     Lives in PYTHON only. SQLAlchemy uses it so you can write
#     subject.user and get back the full User object without
#     writing a JOIN query yourself.
#     Written as: relationship("User", back_populates="subjects")
#
#   You need BOTH — the FK enforces data integrity in the DB,
#   the relationship gives you convenient Python access.
# ──────────────────────────────────────────────────────────────

from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Subject(Base):
    """
    Represents a row in the `subjects` table.

    Each subject is owned by exactly one user.

    Inherits from Base:
      - id          (Integer, primary key, auto-increment)
      - created_at  (DateTime, set on insert)
      - updated_at  (DateTime, updated on change)
    """

    __tablename__ = "subjects"

    # ── Ownership ─────────────────────────────────────────────
    # This column stores the `id` of the User who owns this subject.
    # ForeignKey("users.id") tells PostgreSQL:
    #   "This value MUST exist as an id in the users table."
    # ondelete="CASCADE" means: if the user is deleted, all their
    # subjects are automatically deleted too (DB-level cascade).
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Subject Details ───────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Hex color string for UI display (e.g. "#6366f1" for indigo)
    color: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        default="#6366f1",
    )

    # Optional exam date used by the Planner Agent
    exam_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    # ── Relationships ─────────────────────────────────────────

    # subject.user → returns the User who owns this subject
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User",
        back_populates="subjects",
    )

    # subject.documents → returns all uploaded documents
    # (Document model will be created in a later module)
    documents: Mapped[list["Document"]] = relationship(  # type: ignore[name-defined]
        "Document",
        back_populates="subject",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Subject id={self.id} "
            f"name={self.name!r} "
            f"user_id={self.user_id}>"
        )