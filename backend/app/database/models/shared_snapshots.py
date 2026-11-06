import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base


class SharedSnapshot(Base):
    """An immutable public snapshot of a single turn or complete research thread."""

    __tablename__ = "shared_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        init=False,
        server_default=text("gen_random_uuid()"),
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"),
        index=True,
    )
    share_type: Mapped[str] = mapped_column(String(30))  # 'single_turn' or 'full_thread'
    title: Mapped[str] = mapped_column(String(500))
    snapshot_payload: Mapped[dict] = mapped_column(JSONB)
    target_message_id: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        init=False,
        server_default=func.now(),
    )

