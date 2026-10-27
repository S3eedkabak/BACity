"""Add private ScrapingAnt credit reservations; preserve all existing L4 data."""
from alembic import op
import sqlalchemy as sa
revision='0025'
down_revision='0024'
branch_labels=None
depends_on=None
DDL=(
    """CREATE TABLE IF NOT EXISTS l4_provider_budget (
	id SERIAL NOT NULL, 
	period_start FLOAT, 
	period_end FLOAT, 
	provider_total INTEGER, 
	provider_remaining INTEGER, 
	provider_used INTEGER NOT NULL,
	since_sync INTEGER NOT NULL, 
	charged INTEGER NOT NULL, 
	reserved INTEGER NOT NULL, 
	reported_credits INTEGER NOT NULL, 
	estimated_credits INTEGER NOT NULL, 
	requests INTEGER NOT NULL, 
	usage_requests INTEGER NOT NULL, 
	synced FLOAT, 
	blocked VARCHAR(40), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_l4_provider_nonnegative CHECK (reserved >= 0 AND charged >= 0)
)""",
    """CREATE TABLE IF NOT EXISTS l4_provider_requests (
	id VARCHAR(36) NOT NULL, 
	job_id VARCHAR(36) NOT NULL, 
	kind VARCHAR(12) NOT NULL, 
	target VARCHAR(1024) NOT NULL, 
	period_start FLOAT, 
	reserved INTEGER NOT NULL, 
	cost INTEGER, 
	cost_kind VARCHAR(16), 
	state VARCHAR(16) NOT NULL, 
	created FLOAT NOT NULL, 
	finished FLOAT, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_l4_provider_request_kind CHECK (kind IN ('usage','acquire')), 
	FOREIGN KEY(job_id) REFERENCES l4_collection_jobs (id)
)""",
    """CREATE INDEX IF NOT EXISTS ix_l4_provider_requests_job_id ON l4_provider_requests (job_id)"""
)

def upgrade():
    for statement in DDL:op.execute(sa.text(statement))

def downgrade():
    # Preserve the accounting ledger; old applications ignore it.
    pass
