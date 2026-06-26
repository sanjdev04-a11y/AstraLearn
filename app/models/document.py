from enum import Enum

from sqlalchemy import (
    BigInteger,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class DocumentStatus(str, Enum):
    """
    Processing lifecycle of a document.

    UPLOADED   -> File saved to disk
    PROCESSING -> RAG pipeline currently running
    PROCESSED  -> Successfully embedded into Qdrant
    FAILED     -> Processing failed
    """

    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class Document(Base):
    """
    Represents a document uploaded by a student.

    Relationships

    User
      └── Subjects
              └── Documents

    Every document belongs to exactly one user and one subject.
    """

    __tablename__ = "documents"

    # --------------------------------------------------
    # Ownership
    # --------------------------------------------------

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------
    # File Information
    # --------------------------------------------------

    original_filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    stored_filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
    )

    file_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    file_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # --------------------------------------------------
    # RAG Processing
    # --------------------------------------------------

    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus),
        nullable=False,
        default=DocumentStatus.UPLOADED,
    )

    chunk_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=None,
    )

    processing_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # --------------------------------------------------
    # Relationships
    # --------------------------------------------------

    subject: Mapped["Subject"] = relationship(  # type: ignore[name-defined]
        "Subject",
        back_populates="documents",
    )

    def __repr__(self) -> str:
        return (
            f"<Document("
            f"id={self.id}, "
            f"filename={self.original_filename!r}, "
            f"subject_id={self.subject_id}, "
            f"status={self.status}"
            f")>"
        )