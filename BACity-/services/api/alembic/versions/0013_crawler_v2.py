"""Candidate source controls and compact observed event/quality evidence."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('candidate_sources',
        sa.Column('domain', sa.String(255), primary_key=True),
        sa.Column('url', sa.String(2048), nullable=False), sa.Column('origin', sa.String(2048), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='discovered'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('discovered', sa.Float(), nullable=False), sa.Column('inspected', sa.Float()),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('good_runs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failures', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reason', sa.String(100)), sa.Column('metrics', sa.JSON(), nullable=False, server_default='{}'),
        sa.CheckConstraint("status IN ('discovered','inspected','probation','trusted','rejected','blocked','disabled')", name='ck_candidate_status'))
    op.create_index('ix_candidate_status_inspected', 'candidate_sources', ['status','inspected'])
    op.add_column('event_sources', sa.Column('facts', JSONB(), nullable=False, server_default='{}'))
    for table in ('sources','crawler_runs'):
        op.add_column(table, sa.Column('quality_metrics', sa.JSON(), nullable=False, server_default='{}'))


def downgrade():
    for table in ('sources','crawler_runs'):
        op.drop_column(table,'quality_metrics')
    op.drop_column('event_sources','facts')
    op.drop_index('ix_candidate_status_inspected', table_name='candidate_sources')
    op.drop_table('candidate_sources')
