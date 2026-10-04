"""Allow opaque Play tokens without exceeding indexed identifier lengths."""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("consumer_subscriptions", sa.Column("provider_purchase_token", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("consumer_subscriptions", "provider_purchase_token")
