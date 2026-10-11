import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base


class MessageCitation(Base):
    """A normalized citation linking an assistant message to a source chunk.

    Each citation records enough metadata for the frontend to render a
    clickable reference (company, filing, page/section, excerpt) without
    joining back to the chunk or document tables at display time.
    """

    __tablename__ = "message_citations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        init=False,
        server_default=text("gen_random_uuid()"),
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        index=True,
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
    )
    citation_index: Mapped[int] = mapped_column(Integer)
    ticker: Mapped[str | None] = mapped_column(String(10), default=None)
    filing_type: Mapped[str | None] = mapped_column(String(20), default=None)
    filing_date: Mapped[str | None] = mapped_column(String(10), default=None)
    section: Mapped[str | None] = mapped_column(String(255), default=None)
    page: Mapped[int | None] = mapped_column(Integer, default=None)
    excerpt: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        init=False,
        server_default=func.now(),
    )
