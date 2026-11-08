"""Atomic acknowledgements for independently buffered collector deliveries."""
from alembic import op
revision='0027'
down_revision='0026'
branch_labels=None
depends_on=None

def upgrade():
    op.execute("ALTER TABLE l4_collection_jobs ADD COLUMN IF NOT EXISTS buffered BOOLEAN NOT NULL DEFAULT false")
    op.execute('''CREATE TABLE IF NOT EXISTS l4_delivery_receipts (
        id VARCHAR(36) PRIMARY KEY, body_hash VARCHAR(64) NOT NULL,
        result JSON NOT NULL, job_id VARCHAR(36),
        created DOUBLE PRECISION NOT NULL)''')
    op.execute('CREATE INDEX IF NOT EXISTS ix_l4_delivery_receipts_job_id ON l4_delivery_receipts(job_id)')

def downgrade():
    # Retain acknowledgements; dropping them could cause unsafe delivery replays.
    pass
