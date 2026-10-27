"""Additive tables in the existing PostgreSQL database; no consumer role linkage."""
import time
import uuid
from sqlalchemy import (Column, String, Text, Integer, Float, Boolean, JSON,
                        ForeignKey, UniqueConstraint, CheckConstraint, Index, Uuid)
from app.database import Base
from app.models.source import GUID
from app.models.event import Event  # Register the existing canonical FK target; no writes.

SocialBase = Base

def identity():
    return str(uuid.uuid4())

class Staff(SocialBase):
    __tablename__ = 'l4_staff'
    id = Column(String(36), primary_key=True, default=identity)
    email = Column(String(254), nullable=False, unique=True)
    name = Column(String(120), nullable=False)
    role = Column(String(32), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
    created = Column(Float, nullable=False, default=time.time)
    __table_args__ = (CheckConstraint("role IN ('OWNER','SOCIAL_ADMIN','SOCIAL_EDITOR','SOCIAL_REVIEWER','SOCIAL_VIEWER')", name='ck_l4_staff_role'),)

class Credential(SocialBase):
    __tablename__ = 'l4_credentials'
    id = Column(String(1400), primary_key=True)
    staff_id = Column(String(36), ForeignKey('l4_staff.id'), nullable=False, index=True)
    public_key = Column(Text, nullable=False)
    sign_count = Column(Integer, nullable=False, default=0)
    label = Column(String(80), nullable=False)
    created = Column(Float, nullable=False, default=time.time)
    revoked = Column(Boolean, nullable=False, default=False)

class Invitation(SocialBase):
    __tablename__ = 'l4_invitations'
    digest = Column(String(64), primary_key=True)
    staff_id = Column(String(36), ForeignKey('l4_staff.id'), nullable=False)
    created_by = Column(String(36), ForeignKey('l4_staff.id'))
    expires = Column(Float, nullable=False)
    consumed = Column(Boolean, nullable=False, default=False)

class Challenge(SocialBase):
    __tablename__ = 'l4_challenges'
    digest = Column(String(64), primary_key=True)
    purpose = Column(String(20), nullable=False)
    challenge = Column(Text, nullable=False)
    staff_id = Column(String(36), ForeignKey('l4_staff.id'))
    invitation_digest = Column(String(64), ForeignKey('l4_invitations.digest'))
    session_digest = Column(String(64))
    expires = Column(Float, nullable=False, index=True)
    consumed = Column(Boolean, nullable=False, default=False)

class StaffSession(SocialBase):
    __tablename__ = 'l4_sessions'
    digest = Column(String(64), primary_key=True)
    staff_id = Column(String(36), ForeignKey('l4_staff.id'), nullable=False, index=True)
    staff_version = Column(Integer, nullable=False)
    credential_id = Column(String(1400), ForeignKey('l4_credentials.id'), nullable=False)
    created = Column(Float, nullable=False)
    last_seen = Column(Float, nullable=False)
    verified = Column(Float, nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)

class RateBucket(SocialBase):
    __tablename__ = 'l4_rate_buckets'
    key = Column(String(64), primary_key=True)
    window = Column(Integer, nullable=False)
    count = Column(Integer, nullable=False)
    expires = Column(Float, nullable=False, index=True)

class AuditHead(SocialBase):
    __tablename__ = 'l4_audit_head'
    id = Column(Integer, primary_key=True)
    sequence = Column(Integer, nullable=False, default=0)
    digest = Column(String(64), nullable=False, default='0' * 64)

class AuditEvent(SocialBase):
    __tablename__ = 'l4_audit_events'
    sequence = Column(Integer, primary_key=True)
    previous = Column(String(64), nullable=False)
    digest = Column(String(64), nullable=False, unique=True)
    record = Column(JSON, nullable=False)
    timestamp = Column(Float, nullable=False, index=True)

class Publisher(SocialBase):
    __tablename__ = 'l4_publishers'
    id = Column(String(36), primary_key=True, default=identity)
    platform = Column(String(20), nullable=False)
    url = Column(String(1024), nullable=False, unique=True)
    external_id = Column(String(200), nullable=False)
    target_type = Column(String(20), nullable=False)
    name = Column(String(160), nullable=False)
    publisher_type = Column(String(32), nullable=False, default='other')
    relevance = Column(String(500), nullable=False)
    venue_name = Column(String(200))
    address = Column(String(300))
    latitude = Column(Float)
    longitude = Column(Float)
    approval = Column(String(20), nullable=False, default='pending')
    eligibility = Column(String(32), nullable=False, default='authorization_required')
    permission_basis = Column(String(1000))
    permission_expires = Column(Float)
    method = Column(String(20), nullable=False, default='submission')
    priority = Column(Integer, nullable=False, default=50)
    interval_seconds = Column(Integer, nullable=False, default=86400)
    enabled = Column(Boolean, nullable=False, default=False)
    next_due = Column(Float, nullable=False, default=0, index=True)
    last_attempt = Column(Float)
    last_success = Column(Float)
    last_error = Column(String(40))
    failures = Column(Integer, nullable=False, default=0)
    checkpoint = Column(String(200))
    posts_per_profile = Column(Integer,nullable=False,default=1,server_default='1')
    instagram_timestamp = Column(Float)
    discovered_by = Column(String(32), nullable=False, default='staff_url')
    created_by = Column(String(36), ForeignKey('l4_staff.id'), nullable=False)
    approved_by = Column(String(36), ForeignKey('l4_staff.id'))
    created = Column(Float, nullable=False, default=time.time)
    updated = Column(Float, nullable=False, default=time.time)
    __table_args__ = (
        CheckConstraint("platform IN ('instagram','facebook','tiktok','event_url')", name='ck_l4_publisher_platform'),
        CheckConstraint("approval IN ('pending','approved','rejected','suspended')", name='ck_l4_publisher_approval'),
        CheckConstraint("eligibility IN ('authorization_required','available','blocked','unsupported','rate_limited')", name='ck_l4_publisher_access'),
        CheckConstraint('posts_per_profile BETWEEN 1 AND 3',name='ck_l4_publisher_posts_limit'),
        CheckConstraint('priority BETWEEN 0 AND 100', name='ck_l4_publisher_priority'),
        CheckConstraint('interval_seconds BETWEEN 3600 AND 604800', name='ck_l4_publisher_interval'),
        Index('ix_l4_publisher_due', 'enabled', 'approval', 'next_due'),
    )

class CollectionJob(SocialBase):
    __tablename__ = 'l4_collection_jobs'
    id = Column(String(36), primary_key=True, default=identity)
    publisher_id = Column(String(36), ForeignKey('l4_publishers.id'), nullable=False, index=True)
    apify_run_id = Column(String(36),ForeignKey('l4_apify_runs.id'),index=True)
    dedup_key = Column(String(64), nullable=False, unique=True)
    state = Column(String(24), nullable=False, default='queued', index=True)
    created = Column(Float, nullable=False, default=time.time)
    started = Column(Float)
    finished = Column(Float)
    lease_until = Column(Float)
    lease_digest = Column(String(64))
    buffered = Column(Boolean, nullable=False, default=False, server_default='false')
    attempts = Column(Integer, nullable=False, default=0)
    error = Column(String(40))
    metrics = Column(JSON, nullable=False, default=dict)
    __table_args__ = (CheckConstraint("state IN ('queued','running','success','empty','partial','unauthorized','blocked','rate_limited','failed','cancelled')", name='ck_l4_job_state'),)

class Observation(SocialBase):
    __tablename__ = 'l4_observations'
    id = Column(String(36), primary_key=True, default=identity)
    publisher_id = Column(String(36), ForeignKey('l4_publishers.id'), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey('l4_collection_jobs.id'))
    external_id = Column(String(200), nullable=False)
    source_url = Column(String(1024), nullable=False)
    content_hash = Column(String(64), nullable=False)
    caption = Column(Text, nullable=False)
    published_at = Column(String(64))
    observed = Column(Float, nullable=False, default=time.time)
    method = Column(String(24), nullable=False)
    provenance = Column(JSON, nullable=False)
    media = Column(JSON, nullable=False, default=list)
    retention_until = Column(Float, nullable=False, index=True)
    __table_args__ = (UniqueConstraint('publisher_id', 'external_id', 'content_hash', name='uq_l4_observation_version'),)

class EventCandidate(SocialBase):
    __tablename__ = 'l4_event_candidates'
    id = Column(String(36), primary_key=True, default=identity)
    observation_id = Column(String(36), ForeignKey('l4_observations.id', ondelete='CASCADE'), nullable=False, index=True)
    ordinal = Column(Integer, nullable=False)
    fields = Column(JSON, nullable=False)
    missing = Column(JSON, nullable=False)
    confidence = Column(Float, nullable=False)
    status = Column(String(32), nullable=False, default='needs_review', index=True)
    reviewed_by = Column(String(36), ForeignKey('l4_staff.id'))
    reviewed_hash = Column(String(64))
    publication_requested_by = Column(String(36), ForeignKey('l4_staff.id'))
    event_id = Column(GUID(), ForeignKey('events.id', name='fk_l4_candidate_canonical', ondelete='SET NULL'))
    created = Column(Float, nullable=False, default=time.time)
    __table_args__ = (UniqueConstraint('observation_id', 'ordinal', name='uq_l4_candidate_ordinal'),
        CheckConstraint("status IN ('needs_review','qualified','rejected','duplicate','approved','publication_queued','published')", name='ck_l4_candidate_status'))

class CandidateReview(SocialBase):
    __tablename__ = 'l4_candidate_reviews'
    id = Column(String(36), primary_key=True, default=identity)
    candidate_id = Column(String(36), ForeignKey('l4_event_candidates.id', ondelete='CASCADE'), nullable=False)
    actor = Column(String(36), ForeignKey('l4_staff.id'), nullable=False)
    decision = Column(String(32), nullable=False)
    evidence_hash = Column(String(64), nullable=False)
    note = Column(String(1000), nullable=False)
    created = Column(Float, nullable=False, default=time.time)

class Control(SocialBase):
    __tablename__ = 'l4_control'
    id = Column(Integer, primary_key=True)
    emergency_stop = Column(Boolean, nullable=False, default=False)

class ProviderBudget(SocialBase):
    __tablename__='l4_provider_budget'
    id=Column(Integer,primary_key=True)
    period_start=Column(Float)
    period_end=Column(Float)
    provider_total=Column(Integer)
    provider_remaining=Column(Integer)
    provider_used=Column(Integer,nullable=False,default=0)
    since_sync=Column(Integer,nullable=False,default=0)
    charged=Column(Integer,nullable=False,default=0)
    reserved=Column(Integer,nullable=False,default=0)
    reported_credits=Column(Integer,nullable=False,default=0)
    estimated_credits=Column(Integer,nullable=False,default=0)
    requests=Column(Integer,nullable=False,default=0)
    usage_requests=Column(Integer,nullable=False,default=0)
    synced=Column(Float)
    blocked=Column(String(40))
    __table_args__=(CheckConstraint('reserved >= 0 AND charged >= 0',name='ck_l4_provider_nonnegative'),)

class ProviderRequest(SocialBase):
    __tablename__='l4_provider_requests'
    id=Column(String(36),primary_key=True)
    job_id=Column(String(36),ForeignKey('l4_collection_jobs.id'),nullable=False,index=True)
    kind=Column(String(12),nullable=False)
    target=Column(String(1024),nullable=False)
    period_start=Column(Float)
    reserved=Column(Integer,nullable=False)
    cost=Column(Integer)
    cost_kind=Column(String(16))
    state=Column(String(16),nullable=False,default='reserved')
    created=Column(Float,nullable=False,default=time.time)
    finished=Column(Float)
    __table_args__=(CheckConstraint("kind IN ('usage','acquire')",name='ck_l4_provider_request_kind'),)

class ApifyBudget(SocialBase):
    __tablename__='l4_apify_budget'
    id=Column(Integer,primary_key=True)
    period_start=Column(Float)
    period_end=Column(Float)
    provider_used=Column(Integer,nullable=False,default=0)
    provider_limit=Column(Integer,nullable=False,default=5000000)
    spent=Column(Integer,nullable=False,default=0)
    since_sync=Column(Integer,nullable=False,default=0)
    reserved=Column(Integer,nullable=False,default=0)
    estimated=Column(Integer,nullable=False,default=0)
    synced=Column(Float)
    price=Column(Integer)
    startup=Column(Integer,nullable=False,default=0)
    build=Column(String(40))
    blocked=Column(String(40))
    __table_args__=(CheckConstraint('spent>=0 AND reserved>=0',name='ck_l4_apify_budget_nonnegative'),)

class ApifyRun(SocialBase):
    __tablename__='l4_apify_runs'
    id=Column(String(36),primary_key=True,default=identity)
    dedup_key=Column(String(64),nullable=False,unique=True)
    state=Column(String(24),nullable=False,default='planned',index=True)
    actor_input=Column(JSON,nullable=False)
    members=Column(JSON,nullable=False)
    items=Column(JSON,nullable=False,default=dict)
    errors=Column(JSON,nullable=False,default=dict)
    owner_digest=Column(String(64))
    lease_until=Column(Float)
    run_id=Column(String(32),unique=True)
    dataset_id=Column(String(32))
    provider_status=Column(String(24))
    created=Column(Float,nullable=False,default=time.time)
    launched=Column(Float)
    finished=Column(Float)
    next_poll=Column(Float,nullable=False,default=0)
    polls=Column(Integer,nullable=False,default=0)
    offset=Column(Integer,nullable=False,default=0)
    total=Column(Integer)
    dataset_done=Column(Boolean,nullable=False,default=False)
    reservation=Column(Integer,nullable=False,default=0)
    actor_cap=Column(Integer,nullable=False,default=0)
    cost=Column(Integer)
    cost_kind=Column(String(32))
    period_start=Column(Float)
    build=Column(String(40))
    error=Column(String(40))

class InstagramItem(SocialBase):
    __tablename__='l4_instagram_items'
    publisher_id=Column(String(36),ForeignKey('l4_publishers.id'),primary_key=True)
    external_id=Column(String(200),primary_key=True)
    content_hash=Column(String(64),nullable=False)
    last_seen=Column(Float,nullable=False,default=time.time)

class DeliveryReceipt(SocialBase):
    __tablename__='l4_delivery_receipts'
    id=Column(String(36),primary_key=True)
    body_hash=Column(String(64),nullable=False)
    result=Column(JSON,nullable=False)
    job_id=Column(String(36),index=True)
    created=Column(Float,nullable=False,default=time.time)
