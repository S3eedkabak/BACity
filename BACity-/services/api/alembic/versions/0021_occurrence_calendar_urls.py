"""A calendar URL can describe several distinct events at the same time."""
from alembic import op
revision='0021'
down_revision='0020'
branch_labels=None
depends_on=None

def upgrade():
    op.drop_constraint('uq_occurrence_listing_start','event_occurrences',type_='unique')

def downgrade():
    op.create_unique_constraint('uq_occurrence_listing_start','event_occurrences',['source_url','start_time'])
