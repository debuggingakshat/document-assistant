import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base


class SourceDocument(Base):
    """An original SEC filing that has been ingested into the corpus.

    Stores filing metadata and the full normalized Markdown content so the
    application can re-chunk or cite the original text without reaching back
    into downloaded HTML files.
    """

    __tablename__ = "source_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        init=False,
        server_default=text("gen_random_uuid()"),
    )
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    filing_type: Mapped[str] = mapped_column(String(20))
    filing_date: Mapped[str] = mapped_column(String(10))
    fiscal_year: Mapped[int] = mapped_column(Integer)
    accession_number: Mapped[str] = mapped_column(String(30), unique=True)
    source_url: Mapped[str] = mapped_column(Text)
    content_md: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        init=False,
        server_default=func.now(),
    )
