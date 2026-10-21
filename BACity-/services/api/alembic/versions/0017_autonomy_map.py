"""Candidate degradation and bounded geographic map query index."""
from alembic import op
import sqlalchemy as sa

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('ck_candidate_status','candidate_sources',type_='check')
    op.create_check_constraint('ck_candidate_status','candidate_sources',"status IN ('discovered','inspected','probation','trusted','degraded','rejected','blocked','disabled')")
    op.create_index('ix_events_map_published','events',['latitude','longitude','start_time','id'],
                    postgresql_where=sa.text("status IN ('fresh','stale') AND latitude IS NOT NULL AND longitude IS NOT NULL"))


def downgrade():
    op.drop_index('ix_events_map_published',table_name='events')
    op.execute("UPDATE candidate_sources SET status='probation' WHERE status='degraded'")
    op.drop_constraint('ck_candidate_status','candidate_sources',type_='check')
    op.create_check_constraint('ck_candidate_status','candidate_sources',"status IN ('discovered','inspected','probation','trusted','rejected','blocked','disabled')")
