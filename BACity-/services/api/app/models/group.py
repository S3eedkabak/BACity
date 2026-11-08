"""Persistent, private decision sessions for BACity+ Group Match."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, text

from app.database import Base
from app.models.source import GUID


class GroupSession(Base):
    __tablename__ = "group_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('open','ready','voting','completed','expired','cancelled')", name="ck_group_session_status"),
        CheckConstraint("max_participants >= 2 AND max_participants <= 12", name="ck_group_session_participant_limit"),
        CheckConstraint("ends_at > starts_at", name="ck_group_session_window"),
        Index("ix_group_sessions_host_status", "host_id", "status"),
        Index("ix_group_sessions_expiration", "expires_at", "purge_after"),
    )

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    host_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    status = Column(String(16), nullable=False, default="open", index=True)
    target_date = Column(Date, nullable=False)
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    categories = Column(JSON, nullable=False, default=list)
    max_participants = Column(Integer, nullable=False, default=8)
    invite_token_hash = Column(String(64), unique=True)
    invite_expires_at = Column(DateTime)
    expires_at = Column(DateTime, nullable=False)
    purge_after = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class GroupParticipant(Base):
    __tablename__ = "group_participants"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_participant"),
        Index("ix_group_participants_user_group", "user_id", "group_id"),
    )

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    group_id = Column(GUID(), ForeignKey("group_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    liked_categories = Column(JSON, nullable=False, default=list)
    disliked_categories = Column(JSON, nullable=False, default=list)
    ready = Column(Boolean, nullable=False, default=False)
    joined_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class GroupMatchRound(Base):
    __tablename__ = "group_match_rounds"
    __table_args__ = (
        UniqueConstraint("group_id", "round_number", name="uq_group_match_round_number"),
        CheckConstraint("status IN ('voting','completed')", name="ck_group_match_round_status"),
        Index(
            "uq_group_match_active_round",
            "group_id",
            unique=True,
            postgresql_where=text("status = 'voting'"),
            sqlite_where=text("status = 'voting'"),
        ),
    )

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    group_id = Column(GUID(), ForeignKey("group_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    round_number = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="voting", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    revealed_at = Column(DateTime)


class GroupCandidate(Base):
    __tablename__ = "group_candidates"
    __table_args__ = (
        UniqueConstraint("round_id", "event_id", name="uq_group_candidate_event"),
        UniqueConstraint("round_id", "position", name="uq_group_candidate_position"),
    )

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    round_id = Column(GUID(), ForeignKey("group_match_rounds.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id = Column(GUID(), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    match_score = Column(Float, nullable=False)
    explanations = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class GroupVote(Base):
    __tablename__ = "group_votes"
    __table_args__ = (
        UniqueConstraint("candidate_id", "user_id", name="uq_group_vote"),
        CheckConstraint("value >= -1 AND value <= 1", name="ck_group_vote_value"),
        Index("ix_group_votes_user_candidate", "user_id", "candidate_id"),
    )

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(GUID(), ForeignKey("group_candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    value = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
