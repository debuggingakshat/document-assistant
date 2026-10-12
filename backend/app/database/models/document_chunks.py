import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.database.models.base import Base


class DocumentChunk(Base):
    """A retrieval-ready passage derived from a source document.

    Each chunk carries its text, positional metadata, an embedding vector for
    semantic search, and a generated tsvector column for Postgres full-text
    search.  The tsvector is populated via a database-level generated column
    (set up in the Alembic migration, not in Python), so it is mapped as
    read-only here.
    """

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        init=False,
        server_default=text("gen_random_uuid()"),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    chunk_text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dimensions), default=None
    )
    # Populated by a Postgres generated column — read-only in Python.
    search_vector: Mapped[None] = mapped_column(
        TSVECTOR, nullable=True, init=False, insert_default=None
    )
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        init=False,
        server_default=func.now(),
    )
