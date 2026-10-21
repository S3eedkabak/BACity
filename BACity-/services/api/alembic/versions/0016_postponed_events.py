"""Withhold explicitly postponed events from fresh/stale discovery queries."""
from alembic import op

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name=='postgresql':
        op.execute("ALTER TYPE eventstatus ADD VALUE IF NOT EXISTS 'postponed'")


def downgrade():
    # PostgreSQL cannot safely remove an enum value in place. Keep the value;
    # old application versions ignore it in discovery, preserving event IDs.
    pass
