"""Private cached post images and local OCR work queue."""
from alembic import op
revision='0029'
down_revision='0028'
branch_labels=None
depends_on=None

def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS l4_post_images (
        id VARCHAR(36) PRIMARY KEY,
        observation_id VARCHAR(36) NOT NULL REFERENCES l4_observations(id) ON DELETE CASCADE,
        source_url VARCHAR(1500) NOT NULL, source_hash VARCHAR(64) NOT NULL,
        position INTEGER NOT NULL CHECK(position BETWEEN 0 AND 2),
        state VARCHAR(20) NOT NULL CHECK(state IN ('queued','running','ready','failed')),
        preview BYTEA CHECK(length(preview)<=40000), width INTEGER, height INTEGER,
        image_hash VARCHAR(64), ocr_text TEXT NOT NULL, ocr_status VARCHAR(20) NOT NULL,
        ocr_confidence DOUBLE PRECISION NOT NULL, error VARCHAR(40), attempts INTEGER NOT NULL,
        owner_digest VARCHAR(64), lease_until DOUBLE PRECISION, next_due DOUBLE PRECISION NOT NULL,
        created DOUBLE PRECISION NOT NULL, updated DOUBLE PRECISION NOT NULL,
        CONSTRAINT uq_l4_post_image_source UNIQUE(observation_id,source_hash))''')
    op.execute('CREATE INDEX IF NOT EXISTS ix_l4_post_images_observation_id ON l4_post_images(observation_id)')

def downgrade():
    # Preserve evidence on rollback; older versions simply ignore this table.
    pass
