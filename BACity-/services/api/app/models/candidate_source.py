"""Compact mirror/control surface for the durable crawler candidate queue."""
from sqlalchemy import Column, String, Integer, Float, Boolean, JSON, CheckConstraint, Index
from app.database import Base


class CandidateSource(Base):
    __tablename__ = 'candidate_sources'
    __table_args__ = (
        CheckConstraint("status IN ('discovered','inspected','probation','trusted','rejected','blocked','disabled')", name='ck_candidate_status'),
        Index('ix_candidate_status_inspected', 'status', 'inspected'),
    )
    domain = Column(String(255), primary_key=True)
    url = Column(String(2048), nullable=False)
    origin = Column(String(2048), nullable=False)
    status = Column(String(32), nullable=False, default='discovered')
    enabled = Column(Boolean, nullable=False, default=True)
    discovered = Column(Float, nullable=False)
    inspected = Column(Float)
    attempts = Column(Integer, nullable=False, default=0)
    good_runs = Column(Integer, nullable=False, default=0)
    failures = Column(Integer, nullable=False, default=0)
    reason = Column(String(100))
    metrics = Column(JSON, nullable=False, default=dict)
