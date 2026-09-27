"""Encrypted provider credentials required for revocation."""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE oauth_identities ADD COLUMN refresh_token_encrypted TEXT")


def downgrade():
    op.execute("ALTER TABLE oauth_identities DROP COLUMN refresh_token_encrypted")
