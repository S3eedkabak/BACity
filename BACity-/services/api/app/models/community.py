"""Trust, identity and contribution records are independent of permissions."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, JSON, ForeignKey, UniqueConstraint
from app.database import Base
from app.models.source import GUID


class Record:
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Submission(Record, Base):
    __tablename__ = 'submissions'
    user_id = Column(GUID(), ForeignKey('users.id'), nullable=False, index=True)
    kind = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    state = Column(String, nullable=False, default='pending', index=True)
    risk_flags = Column(JSON, nullable=False, default=list)
    published_id = Column(String)
    decision_reason = Column(Text)
    reviewer_id = Column(GUID(), ForeignKey('users.id'))
    appeal = Column(Text)


class AuditLog(Record, Base):
    __tablename__ = 'audit_logs'
    actor_id = Column(GUID(), ForeignKey('users.id'))
    action = Column(String, nullable=False, index=True)
    target_type = Column(String, nullable=False)
    target_id = Column(String, nullable=False, index=True)
    details = Column(JSON, nullable=False, default=dict)


class Follow(Record, Base):
    __tablename__ = 'follows'
    __table_args__ = (UniqueConstraint('user_id', 'target_type', 'target_id', name='uq_follow'),)
    user_id = Column(GUID(), ForeignKey('users.id'), nullable=False, index=True)
    target_type = Column(String, nullable=False)
    target_id = Column(String, nullable=False, index=True)


class UserBlock(Record, Base):
    __tablename__ = 'user_blocks'
    __table_args__ = (UniqueConstraint('user_id', 'blocked_id', name='uq_block'),)
    user_id = Column(GUID(), ForeignKey('users.id'), nullable=False, index=True)
    blocked_id = Column(GUID(), ForeignKey('users.id'), nullable=False, index=True)


class Report(Record, Base):
    __tablename__ = 'reports'
    user_id = Column(GUID(), ForeignKey('users.id'), nullable=False)
    target_type = Column(String, nullable=False)
    target_id = Column(String, nullable=False, index=True)
    reason = Column(Text, nullable=False)
    state = Column(String, nullable=False, default='pending', index=True)
    decision = Column(Text)


class Organization(Record, Base):
    __tablename__ = 'organizations'
    name = Column(String, nullable=False, index=True)
    description = Column(Text)
    website = Column(String)
    venue_id = Column(GUID(), ForeignKey('venues.id'))
    verified = Column(Boolean, nullable=False, default=False)
    tier = Column(String, nullable=False, default='free')
    stripe_customer_id = Column(String, unique=True)
    stripe_subscription_id = Column(String, unique=True)


class OrganizationMember(Record, Base):
    __tablename__ = 'organization_members'
    __table_args__ = (UniqueConstraint('organization_id', 'user_id', name='uq_organization_member'),)
    organization_id = Column(GUID(), ForeignKey('organizations.id'), nullable=False, index=True)
    user_id = Column(GUID(), ForeignKey('users.id'), nullable=False, index=True)
    role = Column(String, nullable=False, default='owner')


class Place(Record, Base):
    __tablename__ = 'places'
    name = Column(String, nullable=False, index=True)
    description = Column(Text)
    category = Column(String, nullable=False, default='Other')
    address = Column(String, nullable=False)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    neighborhood = Column(String)
    website = Column(String)
    accessibility = Column(JSON, nullable=False, default=dict)
    operational_status = Column(String, nullable=False, default='unknown')
    last_confirmed_at = Column(DateTime)
    trust_level = Column(String, nullable=False, default='Community')
    contributor_id = Column(GUID(), ForeignKey('users.id'))


class CityUtility(Record, Base):
    __tablename__ = 'city_utilities'
    kind = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    address = Column(String)
    opening_hours = Column(String)
    free = Column(Boolean)
    fee = Column(Float)
    wheelchair_accessible = Column(Boolean)
    changing_table = Column(Boolean)
    cleanliness = Column(Integer)
    operational_status = Column(String, nullable=False, default='unknown')
    last_confirmed_at = Column(DateTime, index=True)
    contributor_id = Column(GUID(), ForeignKey('users.id'))
    source_url = Column(String)


class UtilityConfirmation(Record, Base):
    __tablename__ = 'utility_confirmations'
    utility_id = Column(GUID(), ForeignKey('city_utilities.id'), nullable=False, index=True)
    user_id = Column(GUID(), ForeignKey('users.id'), nullable=False)
    operational_status = Column(String, nullable=False)
    cleanliness = Column(Integer)


class Review(Record, Base):
    __tablename__ = 'reviews'
    __table_args__ = (UniqueConstraint('user_id', 'target_type', 'target_id', name='uq_review'),)
    user_id = Column(GUID(), ForeignKey('users.id'), nullable=False, index=True)
    target_type = Column(String, nullable=False)
    target_id = Column(String, nullable=False, index=True)
    body = Column(Text, nullable=False)
    dimensions = Column(JSON, nullable=False)
    state = Column(String, nullable=False, default='visible')
    attendance_verified = Column(Boolean, nullable=False, default=False)


class ReviewRevision(Record, Base):
    __tablename__ = 'review_revisions'
    review_id = Column(GUID(), ForeignKey('reviews.id'), nullable=False, index=True)
    body = Column(Text, nullable=False)
    dimensions = Column(JSON, nullable=False)


class HelpfulVote(Record, Base):
    __tablename__ = 'helpful_votes'
    __table_args__ = (UniqueConstraint('review_id', 'user_id', name='uq_helpful'),)
    review_id = Column(GUID(), ForeignKey('reviews.id'), nullable=False, index=True)
    user_id = Column(GUID(), ForeignKey('users.id'), nullable=False)


class Collection(Record, Base):
    __tablename__ = 'collections'
    user_id = Column(GUID(), ForeignKey('users.id'), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    neighborhood = Column(String)
    items = Column(JSON, nullable=False, default=list)
    public = Column(Boolean, nullable=False, default=False)


class Comment(Record, Base):
    __tablename__ = 'comments'
    event_id = Column(GUID(), ForeignKey('events.id'), nullable=False, index=True)
    user_id = Column(GUID(), ForeignKey('users.id'), nullable=False)
    body = Column(Text, nullable=False)
    state = Column(String, nullable=False, default='visible')


class Message(Record, Base):
    __tablename__ = 'messages'
    sender_id = Column(GUID(), ForeignKey('users.id'), nullable=False, index=True)
    recipient_id = Column(GUID(), ForeignKey('users.id'), nullable=False, index=True)
    body = Column(Text, nullable=False)
    read_at = Column(DateTime)


class Notification(Record, Base):
    __tablename__ = 'notifications'
    user_id = Column(GUID(), ForeignKey('users.id'), nullable=False, index=True)
    kind = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    target_id = Column(String)
    read_at = Column(DateTime)


class Promotion(Record, Base):
    __tablename__ = 'promotions'
    organization_id = Column(GUID(), ForeignKey('organizations.id'), nullable=False)
    event_id = Column(GUID(), ForeignKey('events.id'), nullable=False)
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    label = Column(String, nullable=False, default='Sponsored')


class ActionToken(Record, Base):
    __tablename__ = 'action_tokens'
    user_id = Column(GUID(), ForeignKey('users.id'), nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True)
    purpose = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime)


class MailOutbox(Record, Base):
    __tablename__ = 'mail_outbox'
    recipient = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    sent_at = Column(DateTime)
    error = Column(Text)


class RateBucket(Base):
    __tablename__ = 'rate_buckets'
    key = Column(String, primary_key=True)
    window = Column(Integer, primary_key=True)
    count = Column(Integer, nullable=False, default=0)


class BillingReceipt(Base):
    __tablename__ = 'billing_receipts'
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
