"""create_shared_snapshots

Revision ID: c7b1e8a9d0f2
Revises: a2a304490b43
Create Date: 2026-11-06 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c7b1e8a9d0f2"
down_revision: Union[str, Sequence[str], None] = "a2a304490b43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create shared_snapshots table for public immutable chat shares."""
    op.create_table(
        "shared_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("share_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "target_message_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "snapshot_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["chat_threads.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["profiles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_shared_snapshots_thread_id",
        "shared_snapshots",
        ["thread_id"],
        unique=False,
    )
    op.create_index(
        "ix_shared_snapshots_user_id",
        "shared_snapshots",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop shared_snapshots table."""
    op.drop_index("ix_shared_snapshots_user_id", table_name="shared_snapshots")
    op.drop_index("ix_shared_snapshots_thread_id", table_name="shared_snapshots")
    op.drop_table("shared_snapshots")

