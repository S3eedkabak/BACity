"""Provider-neutral consumer subscriptions and bounded entitlement grants."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base
from app.models.source import GUID
from app.core.encryption import EncryptedText


class ConsumerSubscription(Base):
    __tablename__ = "consumer_subscriptions"
    __table_args__ = (
        UniqueConstraint("provider", "external_subscription_id", name="uq_consumer_subscription_provider_external"),
        CheckConstraint(
            "current_period_start IS NULL OR current_period_end IS NULL OR current_period_end > current_period_start",
            name="ck_consumer_subscription_period",
        ),
        Index("ix_consumer_subscriptions_user_entitlement_status", "user_id", "entitlement", "status"),
    )

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entitlement = Column(String(64), nullable=False, default="bacity_plus")
    provider = Column(String(32), nullable=False)
    external_customer_id = Column(String(255))
    external_subscription_id = Column(String(255))
    # Restricted provider credential; never serialize or include in account exports.
    provider_purchase_token = Column(EncryptedText('consumer_subscriptions.provider_purchase_token'))
    product_id = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, index=True)
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    cancelled_at = Column(DateTime)
    expires_at = Column(DateTime)
    provider_updated_at = Column(DateTime)
    livemode = Column(Boolean, nullable=False, default=False)
    last_reconciled_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConsumerBillingCustomer(Base):
    """Stable provider identity for a BACity consumer account."""
    __tablename__ = "consumer_billing_customers"
    __table_args__ = (
        UniqueConstraint("provider", "user_id", name="uq_consumer_billing_customer_provider_user"),
        UniqueConstraint("provider", "external_customer_id", name="uq_consumer_billing_customer_provider_external"),
    )

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    provider = Column(String(32), nullable=False)
    external_customer_id = Column(String(255), nullable=False)
    livemode = Column(Boolean, nullable=False, default=False)
    pending_checkout_session_id = Column(String(255))
    pending_checkout_expires_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProviderEventReceipt(Base):
    """Minimal durable webhook idempotency record; raw payloads are not retained."""
    __tablename__ = "provider_event_receipts"
    __table_args__ = (
        UniqueConstraint("provider", "external_event_id", name="uq_provider_event_receipt"),
        Index("ix_provider_event_receipts_provider_created", "provider", "provider_created_at"),
    )

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    provider = Column(String(32), nullable=False)
    external_event_id = Column(String(255), nullable=False)
    event_type = Column(String(128), nullable=False)
    provider_created_at = Column(DateTime)
    outcome = Column(String(32), nullable=False)
    processed_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class EntitlementGrant(Base):
    __tablename__ = "entitlement_grants"
    __table_args__ = (
        CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="ck_entitlement_grant_validity"),
        Index("ix_entitlement_grants_user_entitlement_validity", "user_id", "entitlement", "valid_from", "valid_until"),
    )

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entitlement = Column(String(64), nullable=False)
    source = Column(String(32), nullable=False)
    reason_category = Column(String(64), nullable=False)
    valid_from = Column(DateTime, nullable=False, default=datetime.utcnow)
    valid_until = Column(DateTime)
    revoked_at = Column(DateTime)
    audit_metadata = Column("metadata", JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict)
    created_by_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
