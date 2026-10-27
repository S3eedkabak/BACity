"""Add isolated staff, social staging and audit tables; existing tables unchanged.

Frozen PostgreSQL DDL snapshot. Runtime models are deliberately not imported.
"""
from alembic import op
import sqlalchemy as sa

revision = '0024'
down_revision = '0023'
branch_labels = None
depends_on = None

DDL = (
    """CREATE TABLE l4_audit_events (
	sequence SERIAL NOT NULL, 
	previous VARCHAR(64) NOT NULL, 
	digest VARCHAR(64) NOT NULL, 
	record JSON NOT NULL, 
	timestamp FLOAT NOT NULL, 
	PRIMARY KEY (sequence), 
	UNIQUE (digest)
)""",
    """CREATE INDEX ix_l4_audit_events_timestamp ON l4_audit_events (timestamp)""",
    """CREATE TABLE l4_audit_head (
	id SERIAL NOT NULL, 
	sequence INTEGER NOT NULL, 
	digest VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id)
)""",
    """CREATE TABLE l4_control (
	id SERIAL NOT NULL, 
	emergency_stop BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
)""",
    """CREATE TABLE l4_rate_buckets (
	key VARCHAR(64) NOT NULL, 
	"window" INTEGER NOT NULL, 
	count INTEGER NOT NULL, 
	expires FLOAT NOT NULL, 
	PRIMARY KEY (key)
)""",
    """CREATE INDEX ix_l4_rate_buckets_expires ON l4_rate_buckets (expires)""",
    """CREATE TABLE l4_staff (
	id VARCHAR(36) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	role VARCHAR(32) NOT NULL, 
	active BOOLEAN NOT NULL, 
	version INTEGER NOT NULL, 
	created FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_l4_staff_role CHECK (role IN ('OWNER','SOCIAL_ADMIN','SOCIAL_EDITOR','SOCIAL_REVIEWER','SOCIAL_VIEWER')), 
	UNIQUE (email)
)""",
    """CREATE TABLE l4_credentials (
	id VARCHAR(1400) NOT NULL, 
	staff_id VARCHAR(36) NOT NULL, 
	public_key TEXT NOT NULL, 
	sign_count INTEGER NOT NULL, 
	label VARCHAR(80) NOT NULL, 
	created FLOAT NOT NULL, 
	revoked BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(staff_id) REFERENCES l4_staff (id)
)""",
    """CREATE INDEX ix_l4_credentials_staff_id ON l4_credentials (staff_id)""",
    """CREATE TABLE l4_invitations (
	digest VARCHAR(64) NOT NULL, 
	staff_id VARCHAR(36) NOT NULL, 
	created_by VARCHAR(36), 
	expires FLOAT NOT NULL, 
	consumed BOOLEAN NOT NULL, 
	PRIMARY KEY (digest), 
	FOREIGN KEY(staff_id) REFERENCES l4_staff (id), 
	FOREIGN KEY(created_by) REFERENCES l4_staff (id)
)""",
    """CREATE TABLE l4_publishers (
	id VARCHAR(36) NOT NULL, 
	platform VARCHAR(20) NOT NULL, 
	url VARCHAR(1024) NOT NULL, 
	external_id VARCHAR(200) NOT NULL, 
	target_type VARCHAR(20) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	publisher_type VARCHAR(32) NOT NULL, 
	relevance VARCHAR(500) NOT NULL, 
	venue_name VARCHAR(200), 
	address VARCHAR(300), 
	latitude FLOAT, 
	longitude FLOAT, 
	approval VARCHAR(20) NOT NULL, 
	eligibility VARCHAR(32) NOT NULL, 
	permission_basis VARCHAR(1000), 
	permission_expires FLOAT, 
	method VARCHAR(20) NOT NULL, 
	priority INTEGER NOT NULL, 
	interval_seconds INTEGER NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	next_due FLOAT NOT NULL, 
	last_attempt FLOAT, 
	last_success FLOAT, 
	last_error VARCHAR(40), 
	failures INTEGER NOT NULL, 
	checkpoint VARCHAR(200), 
	discovered_by VARCHAR(32) NOT NULL, 
	created_by VARCHAR(36) NOT NULL, 
	approved_by VARCHAR(36), 
	created FLOAT NOT NULL, 
	updated FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_l4_publisher_platform CHECK (platform IN ('instagram','facebook','tiktok','event_url')), 
	CONSTRAINT ck_l4_publisher_approval CHECK (approval IN ('pending','approved','rejected','suspended')), 
	CONSTRAINT ck_l4_publisher_access CHECK (eligibility IN ('authorization_required','available','blocked','unsupported','rate_limited')), 
	CONSTRAINT ck_l4_publisher_priority CHECK (priority BETWEEN 0 AND 100), 
	CONSTRAINT ck_l4_publisher_interval CHECK (interval_seconds BETWEEN 3600 AND 604800), 
	UNIQUE (url), 
	FOREIGN KEY(created_by) REFERENCES l4_staff (id), 
	FOREIGN KEY(approved_by) REFERENCES l4_staff (id)
)""",
    """CREATE INDEX ix_l4_publisher_due ON l4_publishers (enabled, approval, next_due)""",
    """CREATE INDEX ix_l4_publishers_next_due ON l4_publishers (next_due)""",
    """CREATE TABLE l4_challenges (
	digest VARCHAR(64) NOT NULL, 
	purpose VARCHAR(20) NOT NULL, 
	challenge TEXT NOT NULL, 
	staff_id VARCHAR(36), 
	invitation_digest VARCHAR(64), 
	session_digest VARCHAR(64), 
	expires FLOAT NOT NULL, 
	consumed BOOLEAN NOT NULL, 
	PRIMARY KEY (digest), 
	FOREIGN KEY(staff_id) REFERENCES l4_staff (id), 
	FOREIGN KEY(invitation_digest) REFERENCES l4_invitations (digest)
)""",
    """CREATE INDEX ix_l4_challenges_expires ON l4_challenges (expires)""",
    """CREATE TABLE l4_collection_jobs (
	id VARCHAR(36) NOT NULL, 
	publisher_id VARCHAR(36) NOT NULL, 
	dedup_key VARCHAR(64) NOT NULL, 
	state VARCHAR(24) NOT NULL, 
	created FLOAT NOT NULL, 
	started FLOAT, 
	finished FLOAT, 
	lease_until FLOAT, 
	lease_digest VARCHAR(64), 
	attempts INTEGER NOT NULL, 
	error VARCHAR(40), 
	metrics JSON NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_l4_job_state CHECK (state IN ('queued','running','success','empty','partial','unauthorized','blocked','rate_limited','failed','cancelled')), 
	FOREIGN KEY(publisher_id) REFERENCES l4_publishers (id), 
	UNIQUE (dedup_key)
)""",
    """CREATE INDEX ix_l4_collection_jobs_publisher_id ON l4_collection_jobs (publisher_id)""",
    """CREATE INDEX ix_l4_collection_jobs_state ON l4_collection_jobs (state)""",
    """CREATE TABLE l4_sessions (
	digest VARCHAR(64) NOT NULL, 
	staff_id VARCHAR(36) NOT NULL, 
	staff_version INTEGER NOT NULL, 
	credential_id VARCHAR(1400) NOT NULL, 
	created FLOAT NOT NULL, 
	last_seen FLOAT NOT NULL, 
	verified FLOAT NOT NULL, 
	revoked BOOLEAN NOT NULL, 
	PRIMARY KEY (digest), 
	FOREIGN KEY(staff_id) REFERENCES l4_staff (id), 
	FOREIGN KEY(credential_id) REFERENCES l4_credentials (id)
)""",
    """CREATE INDEX ix_l4_sessions_staff_id ON l4_sessions (staff_id)""",
    """CREATE TABLE l4_observations (
	id VARCHAR(36) NOT NULL, 
	publisher_id VARCHAR(36) NOT NULL, 
	job_id VARCHAR(36), 
	external_id VARCHAR(200) NOT NULL, 
	source_url VARCHAR(1024) NOT NULL, 
	content_hash VARCHAR(64) NOT NULL, 
	caption TEXT NOT NULL, 
	published_at VARCHAR(64), 
	observed FLOAT NOT NULL, 
	method VARCHAR(24) NOT NULL, 
	provenance JSON NOT NULL, 
	media JSON NOT NULL, 
	retention_until FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_l4_observation_version UNIQUE (publisher_id, external_id, content_hash), 
	FOREIGN KEY(publisher_id) REFERENCES l4_publishers (id), 
	FOREIGN KEY(job_id) REFERENCES l4_collection_jobs (id)
)""",
    """CREATE INDEX ix_l4_observations_publisher_id ON l4_observations (publisher_id)""",
    """CREATE INDEX ix_l4_observations_retention_until ON l4_observations (retention_until)""",
    """CREATE TABLE l4_event_candidates (
	id VARCHAR(36) NOT NULL, 
	observation_id VARCHAR(36) NOT NULL, 
	ordinal INTEGER NOT NULL, 
	fields JSON NOT NULL, 
	missing JSON NOT NULL, 
	confidence FLOAT NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	reviewed_by VARCHAR(36), 
	reviewed_hash VARCHAR(64), 
	publication_requested_by VARCHAR(36), 
	event_id UUID, 
	created FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_l4_candidate_ordinal UNIQUE (observation_id, ordinal), 
	CONSTRAINT ck_l4_candidate_status CHECK (status IN ('needs_review','qualified','rejected','duplicate','approved','publication_queued','published')), 
	FOREIGN KEY(observation_id) REFERENCES l4_observations (id) ON DELETE CASCADE, 
	FOREIGN KEY(reviewed_by) REFERENCES l4_staff (id), 
	FOREIGN KEY(publication_requested_by) REFERENCES l4_staff (id)
)""",
    """CREATE INDEX ix_l4_event_candidates_observation_id ON l4_event_candidates (observation_id)""",
    """CREATE INDEX ix_l4_event_candidates_status ON l4_event_candidates (status)""",
    """CREATE TABLE l4_candidate_reviews (
	id VARCHAR(36) NOT NULL, 
	candidate_id VARCHAR(36) NOT NULL, 
	actor VARCHAR(36) NOT NULL, 
	decision VARCHAR(32) NOT NULL, 
	evidence_hash VARCHAR(64) NOT NULL, 
	note VARCHAR(1000) NOT NULL, 
	created FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES l4_event_candidates (id) ON DELETE CASCADE, 
	FOREIGN KEY(actor) REFERENCES l4_staff (id)
)""",
)


def upgrade():
    for statement in DDL:
        op.execute(sa.text(statement.replace('CREATE TABLE ', 'CREATE TABLE IF NOT EXISTS ', 1).replace('CREATE INDEX ', 'CREATE INDEX IF NOT EXISTS ', 1)))
    op.execute("""DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_l4_candidate_canonical') THEN
            ALTER TABLE l4_event_candidates ADD CONSTRAINT fk_l4_candidate_canonical FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE SET NULL;
        END IF;
    END $$""")
    op.execute("""CREATE OR REPLACE FUNCTION l4_reject_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'L4 audit records are append-only'; END; $$""")
    op.execute("""DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='l4_audit_immutable') THEN
            CREATE TRIGGER l4_audit_immutable BEFORE UPDATE OR DELETE ON l4_audit_events
            FOR EACH ROW EXECUTE FUNCTION l4_reject_audit_mutation();
        END IF;
    END $$""")
    op.execute("""CREATE OR REPLACE FUNCTION l4_reject_observation_edit() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'L4 observations are immutable; stage a new content hash'; END; $$""")
    op.execute("""DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='l4_observation_immutable') THEN
            CREATE TRIGGER l4_observation_immutable BEFORE UPDATE ON l4_observations
            FOR EACH ROW EXECUTE FUNCTION l4_reject_observation_edit();
        END IF;
    END $$""")


def downgrade():
    # Older applications ignore these isolated tables. Preserve staff/audit data.
    # upgrade() is deliberately idempotent so an upgrade after rollback is safe.
    pass
