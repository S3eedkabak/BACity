"""Durable scheduled maintenance reports and archived child records."""
from alembic import op
import sqlalchemy as sa

revision='0023'
down_revision='0022'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('event_maintenance_runs',
        sa.Column('id',sa.UUID(),primary_key=True),
        sa.Column('started_at',sa.DateTime(),nullable=False),
        sa.Column('finished_at',sa.DateTime(),nullable=False),
        sa.Column('reconciled_aliases',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('expired_events',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('expired_occurrences',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('archived_occurrences',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('archived_offers',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('diagnostics',sa.JSON(),nullable=False))
    op.create_index('ix_event_maintenance_runs_started_at','event_maintenance_runs',['started_at'])
    op.create_table('event_maintenance_archives',
        sa.Column('id',sa.UUID(),primary_key=True),
        sa.Column('kind',sa.String(length=32),nullable=False),
        sa.Column('record_id',sa.UUID(),nullable=False),
        sa.Column('event_id',sa.UUID(),sa.ForeignKey('events.id'),nullable=False),
        sa.Column('snapshot',sa.JSON(),nullable=False),
        sa.Column('archived_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('kind','record_id',name='uq_maintenance_archive_record'))
    op.create_index('ix_event_maintenance_archives_event_id','event_maintenance_archives',['event_id'])


def downgrade():
    op.drop_table('event_maintenance_archives')
    op.drop_table('event_maintenance_runs')
