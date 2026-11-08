"""Separate uncertain publisher dates from timed occurrence observations."""
from alembic import op
import sqlalchemy as sa
revision='0020'
down_revision='0019'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('event_occurrences',sa.Column('start_precision',sa.String(),nullable=False,server_default='time'))
    op.create_unique_constraint('uq_occurrence_identity_start','event_occurrences',['event_id','start_time'])

def downgrade():
    op.drop_constraint('uq_occurrence_identity_start','event_occurrences',type_='unique')
    op.drop_column('event_occurrences','start_precision')
