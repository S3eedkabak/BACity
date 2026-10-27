"""Add selected Apify Actor accounting/recovery and persistent Instagram dedup."""
from alembic import op
import sqlalchemy as sa
revision='0026'
down_revision='0025'
branch_labels=None
depends_on=None
DDL=(
    """CREATE TABLE IF NOT EXISTS l4_apify_budget (
	id SERIAL NOT NULL, 
	period_start FLOAT, 
	period_end FLOAT, 
	provider_used INTEGER NOT NULL, 
	provider_limit INTEGER NOT NULL, 
	spent INTEGER NOT NULL, 
	since_sync INTEGER NOT NULL, 
	reserved INTEGER NOT NULL, 
	estimated INTEGER NOT NULL, 
	synced FLOAT, 
	price INTEGER, 
	startup INTEGER NOT NULL, 
	build VARCHAR(40), 
	blocked VARCHAR(40), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_l4_apify_budget_nonnegative CHECK (spent>=0 AND reserved>=0)
)""",
    """CREATE TABLE IF NOT EXISTS l4_apify_runs (
	id VARCHAR(36) NOT NULL, 
	dedup_key VARCHAR(64) NOT NULL, 
	state VARCHAR(24) NOT NULL, 
	actor_input JSON NOT NULL, 
	members JSON NOT NULL, 
	items JSON NOT NULL, 
	errors JSON NOT NULL, 
	owner_digest VARCHAR(64), 
	lease_until FLOAT, 
	run_id VARCHAR(32), 
	dataset_id VARCHAR(32), 
	provider_status VARCHAR(24), 
	created FLOAT NOT NULL, 
	launched FLOAT, 
	finished FLOAT, 
	next_poll FLOAT NOT NULL, 
	polls INTEGER NOT NULL, 
	"offset" INTEGER NOT NULL, 
	total INTEGER, 
	dataset_done BOOLEAN NOT NULL, 
	reservation INTEGER NOT NULL, 
	actor_cap INTEGER NOT NULL, 
	cost INTEGER, 
	cost_kind VARCHAR(32), 
	period_start FLOAT, 
	build VARCHAR(40), 
	error VARCHAR(40), 
	PRIMARY KEY (id), 
	UNIQUE (dedup_key), 
	UNIQUE (run_id)
)""",
    """CREATE INDEX IF NOT EXISTS ix_l4_apify_runs_state ON l4_apify_runs (state)""",
    """CREATE TABLE IF NOT EXISTS l4_instagram_items (
	publisher_id VARCHAR(36) NOT NULL, 
	external_id VARCHAR(200) NOT NULL, 
	content_hash VARCHAR(64) NOT NULL, 
	last_seen FLOAT NOT NULL, 
	PRIMARY KEY (publisher_id, external_id), 
	FOREIGN KEY(publisher_id) REFERENCES l4_publishers (id)
)""",
    """ALTER TABLE l4_publishers ADD COLUMN IF NOT EXISTS posts_per_profile INTEGER NOT NULL DEFAULT 1""",
    """ALTER TABLE l4_publishers ADD COLUMN IF NOT EXISTS instagram_timestamp DOUBLE PRECISION""",
    """ALTER TABLE l4_collection_jobs ADD COLUMN IF NOT EXISTS apify_run_id VARCHAR(36) REFERENCES l4_apify_runs(id)""",
    """CREATE INDEX IF NOT EXISTS ix_l4_collection_jobs_apify_run_id ON l4_collection_jobs(apify_run_id)""",
    """DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_l4_publisher_posts_limit') THEN ALTER TABLE l4_publishers ADD CONSTRAINT ck_l4_publisher_posts_limit CHECK (posts_per_profile BETWEEN 1 AND 3); END IF; END $$"""
)

def upgrade():
    for statement in DDL:op.execute(sa.text(statement))

def downgrade():
    # Preserve billing evidence and checkpoints. Old applications ignore the additions.
    pass
