"""Single reviewed collection approval and a hard two-post limit."""
from alembic import op
revision='0028'
down_revision='0027'
branch_labels=None
depends_on=None

def upgrade():
    # Existing publishers keep their approval/paused state. No crawl is enabled
    # merely by migrating the database.
    op.execute('ALTER TABLE l4_publishers ADD COLUMN IF NOT EXISTS collection_approved BOOLEAN NOT NULL DEFAULT false')
    op.execute('UPDATE l4_publishers SET posts_per_profile=2 WHERE posts_per_profile>2')
    op.execute('ALTER TABLE l4_publishers ALTER COLUMN posts_per_profile SET DEFAULT 2')
    op.execute('ALTER TABLE l4_publishers DROP CONSTRAINT IF EXISTS ck_l4_publisher_posts_limit')
    op.execute('ALTER TABLE l4_publishers ADD CONSTRAINT ck_l4_publisher_posts_limit CHECK (posts_per_profile BETWEEN 1 AND 2)')

def downgrade():
    # Preserve explicit approvals and avoid re-enabling larger collections.
    pass
