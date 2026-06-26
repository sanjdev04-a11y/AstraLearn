from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from app.models.document import DocumentStatus


class DocumentResponse(BaseModel):
    """
    Metadata returned to the frontend for a document.

    The physical file path is intentionally hidden from the client.
    The frontend should always reference a document using its ID.
    """

    id: int
    subject_id: int
    user_id: int

    original_filename: str

    file_type: str
    file_size_bytes: int

    status: DocumentStatus
    chunk_count: int | None
    processing_error: str | None

    description: str | None

    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def file_size_display(self) -> str:
        """
        Convert bytes into a readable format.

        Example:
            1024      -> 1.0 KB
            2457600   -> 2.3 MB
        """
        size = float(self.file_size_bytes)

        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024

        return f"{size:.1f} TB"

    model_config = {
        "from_attributes": True,
    }


class DocumentListResponse(BaseModel):
    """
    Response returned when listing all documents for a subject.
    """

    documents: list[DocumentResponse]

    total: int

    processing_count: int = Field(
        default=0,
        description="Documents currently being processed",
    )

    failed_count: int = Field(
        default=0,
        description="Documents whose processing failed",
    )


class DocumentUpdateRequest(BaseModel):
    """
    Metadata update request.

    Uploaded file contents are immutable.
    Only the description can be changed.
    """

    description: str | None = Field(
        default=None,
        max_length=1000,
    )