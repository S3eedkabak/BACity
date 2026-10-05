"""Private rights requests. No identity documents or duplicate contact profiles."""
import uuid
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, String
from app.database import Base
from app.models.source import GUID
from app.core.encryption import EncryptedText

KINDS = ('ACCESS', 'RECTIFICATION', 'ERASURE', 'RESTRICTION', 'PORTABILITY', 'OBJECTION', 'OTHER_PRIVACY_REQUEST')
STATES = ('received', 'in_review', 'awaiting_information', 'completed', 'refused')


class PrivacyRequest(Base):
    __tablename__ = 'privacy_requests'
    __table_args__ = (
        CheckConstraint("kind IN ('ACCESS','RECTIFICATION','ERASURE','RESTRICTION','PORTABILITY','OBJECTION','OTHER_PRIVACY_REQUEST')", name='ck_privacy_request_kind'),
        CheckConstraint("status IN ('received','in_review','awaiting_information','completed','refused')", name='ck_privacy_request_status'),
        Index('ix_privacy_requests_status_due', 'status', 'due_at'),
    )
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey('users.id', ondelete='SET NULL'), index=True)
    kind = Column(String(32), nullable=False)
    status = Column(String(24), nullable=False, default='received')
    details = Column(EncryptedText('privacy_requests.details'), nullable=False, default='')
    response = Column(EncryptedText('privacy_requests.response'), nullable=False, default='')
    identity_confirmed = Column(Boolean, nullable=False, default=False)
    decision_code = Column(String(32))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    due_at = Column(DateTime, nullable=False)
    extended = Column(Boolean, nullable=False, default=False)
    closed_at = Column(DateTime)
