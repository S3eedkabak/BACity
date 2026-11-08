"""OAuth provider identities.

Revision ID: 0005
Revises: 0004
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE oauth_identities (
            id UUID NOT NULL,
            user_id UUID NOT NULL,
            provider VARCHAR(20) NOT NULL,
            subject VARCHAR(255) NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT uq_oauth_provider_subject UNIQUE (provider, subject),
            CONSTRAINT uq_oauth_provider_user UNIQUE (provider, user_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_oauth_identities_user_id ON oauth_identities (user_id)")


def downgrade():
    op.drop_table("oauth_identities")
