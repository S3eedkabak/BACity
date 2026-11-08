"""Minimal encrypted, account-scoped privacy rights workflow."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('privacy_requests',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('kind', sa.String(32), nullable=False),
        sa.Column('status', sa.String(24), nullable=False, server_default='received'),
        sa.Column('details', sa.Text(), nullable=False),
        sa.Column('response', sa.Text(), nullable=False),
        sa.Column('identity_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('decision_code', sa.String(32)),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('due_at', sa.DateTime(), nullable=False),
        sa.Column('extended', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('closed_at', sa.DateTime()),
        sa.CheckConstraint("kind IN ('ACCESS','RECTIFICATION','ERASURE','RESTRICTION','PORTABILITY','OBJECTION','OTHER_PRIVACY_REQUEST')", name='ck_privacy_request_kind'),
        sa.CheckConstraint("status IN ('received','in_review','awaiting_information','completed','refused')", name='ck_privacy_request_status'))
    op.create_index('ix_privacy_requests_user_id', 'privacy_requests', ['user_id'])
    op.create_index('ix_privacy_requests_status_due', 'privacy_requests', ['status', 'due_at'])


def downgrade():
    op.drop_index('ix_privacy_requests_status_due', table_name='privacy_requests')
    op.drop_index('ix_privacy_requests_user_id', table_name='privacy_requests')
    op.drop_table('privacy_requests')
