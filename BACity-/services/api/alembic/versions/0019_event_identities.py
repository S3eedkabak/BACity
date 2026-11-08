"""Retain aliases and evidence while separating identities, sessions and offers."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision='0019'
down_revision='0018'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('events',sa.Column('merged_into_id',UUID(),sa.ForeignKey('events.id')))
    op.add_column('events',sa.Column('identity_kind',sa.String(),nullable=False,server_default='single'))
    op.create_index('ix_events_merged_into_id','events',['merged_into_id'])
    op.create_table('event_occurrences',sa.Column('id',UUID(),primary_key=True),sa.Column('event_id',UUID(),sa.ForeignKey('events.id'),nullable=False),sa.Column('source_url',sa.String(),nullable=False),sa.Column('start_time',sa.DateTime(),nullable=False),sa.Column('end_time',sa.DateTime()),sa.Column('status',sa.String(),nullable=False),sa.Column('publisher_event_id',sa.String()),sa.UniqueConstraint('source_url','start_time',name='uq_occurrence_listing_start'))
    for col in ('event_id','start_time','publisher_event_id'):op.create_index('ix_event_occurrences_'+col,'event_occurrences',[col])
    op.create_table('event_offers',sa.Column('id',UUID(),primary_key=True),sa.Column('event_id',UUID(),sa.ForeignKey('events.id'),nullable=False),sa.Column('source_url',sa.String(),nullable=False),sa.Column('label',sa.String(),nullable=False),sa.Column('price',sa.Float()),sa.Column('currency',sa.String()),sa.Column('valid_from',sa.DateTime()),sa.Column('valid_until',sa.DateTime()),sa.UniqueConstraint('event_id','source_url',name='uq_offer_event_url'))
    op.create_index('ix_event_offers_event_id','event_offers',['event_id'])
    op.create_table('event_reconciliations',sa.Column('id',UUID(),primary_key=True),sa.Column('root_id',UUID(),sa.ForeignKey('events.id'),nullable=False),sa.Column('alias_id',UUID(),sa.ForeignKey('events.id'),nullable=False,unique=True),sa.Column('reason',sa.String(),nullable=False),sa.Column('confidence',sa.Float(),nullable=False),sa.Column('before',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False))
    op.create_index('ix_event_reconciliations_root_id','event_reconciliations',['root_id'])


def downgrade():
    connection=op.get_bind()
    if connection.scalar(sa.text('SELECT count(*) FROM event_reconciliations')):
        raise RuntimeError('Reconciliation evidence exists; restore the verified pre-reconciliation backup before downgrade')
    for table in ('event_reconciliations','event_offers','event_occurrences'):op.drop_table(table)
    op.drop_index('ix_events_merged_into_id',table_name='events')
    op.drop_column('events','identity_kind')
    op.drop_column('events','merged_into_id')
