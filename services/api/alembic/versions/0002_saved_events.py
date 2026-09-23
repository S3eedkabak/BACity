"""saved_events join table (spec section 38: save/unsave events)

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("user_id", "event_id", name="uq_saved_event_user_event"),
    )
    op.create_index("ix_saved_events_user_id", "saved_events", ["user_id"])
    op.create_index("ix_saved_events_event_id", "saved_events", ["event_id"])


def downgrade() -> None:
    op.drop_table("saved_events")