"""Keep ingestion provenance and deduplication evidence.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('event_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sources.id')),
        sa.Column('source_url', sa.String, nullable=False),
        sa.Column('original_source_url', sa.String),
        sa.Column('source_name', sa.String),
        sa.Column('start_time', sa.DateTime, nullable=False),
        sa.Column('title_key', sa.String, nullable=False),
        sa.Column('reliability', sa.Float, nullable=False),
        sa.Column('dedup_confidence', sa.Float, nullable=False),
        sa.Column('last_seen_at', sa.DateTime, nullable=False),
        sa.UniqueConstraint('source_url', 'start_time', 'title_key', name='uq_event_source_occurrence'))
    op.create_index('ix_event_sources_event_id', 'event_sources', ['event_id'])
    op.create_index('ix_event_sources_last_seen_at', 'event_sources', ['last_seen_at'])
    op.create_index('ix_events_status_category_start', 'events', ['status', 'category', 'start_time'])
    op.create_index('ix_events_last_verified_at', 'events', ['last_verified_at'])
    # Preserve the canonical source of events that predate this migration.
    import re
    import unicodedata
    import uuid
    from urllib.parse import urlsplit
    bind = op.get_bind()
    rows = bind.execute(sa.text('SELECT id,source_id,source_url,title,start_time,source_reliability,COALESCE(last_verified_at,updated_at,created_at,CURRENT_TIMESTAMP) AS seen FROM events')).mappings()
    for row in rows:
        title = unicodedata.normalize('NFKD', row['title']).casefold()
        title = ''.join(c for c in title if not unicodedata.combining(c))
        title_key = ' '.join(re.findall(r'\w+', title))
        bind.execute(sa.text('INSERT INTO event_sources(id,event_id,source_id,source_url,original_source_url,source_name,start_time,title_key,reliability,dedup_confidence,last_seen_at) VALUES(:id,:event_id,:source_id,:url,:url,:name,:start,:title,:reliability,1,:seen)'),
                     {'id': uuid.uuid4(), 'event_id': row['id'], 'source_id': row['source_id'], 'url': row['source_url'],
                      'name': urlsplit(row['source_url']).hostname, 'start': row['start_time'], 'title': title_key,
                      'reliability': row['source_reliability'], 'seen': row['seen']})


def downgrade():
    op.drop_index('ix_events_last_verified_at', table_name='events')
    op.drop_index('ix_events_status_category_start', table_name='events')
    op.drop_table('event_sources')
