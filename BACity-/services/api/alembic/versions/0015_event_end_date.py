"""Preserve explicit inclusive end dates without inventing closing times."""
from alembic import op
import sqlalchemy as sa

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('events',sa.Column('end_date',sa.Date(),nullable=True))


def downgrade():
    op.drop_column('events','end_date')
