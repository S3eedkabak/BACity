"""Consumer Stripe identity and webhook idempotency.

Revision ID: 0011
Revises: 0010
"""
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE consumer_subscriptions ADD COLUMN livemode BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE consumer_subscriptions ADD COLUMN last_reconciled_at TIMESTAMP WITHOUT TIME ZONE")
    op.execute("""
        CREATE TABLE consumer_billing_customers (
            id UUID NOT NULL, user_id UUID NOT NULL, provider VARCHAR(32) NOT NULL,
            external_customer_id VARCHAR(255) NOT NULL, livemode BOOLEAN NOT NULL DEFAULT FALSE,
            pending_checkout_session_id VARCHAR(255), pending_checkout_expires_at TIMESTAMP WITHOUT TIME ZONE,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(), PRIMARY KEY (id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE RESTRICT,
            CONSTRAINT uq_consumer_billing_customer_provider_user UNIQUE (provider, user_id),
            CONSTRAINT uq_consumer_billing_customer_provider_external UNIQUE (provider, external_customer_id)
        )
    """)
    op.execute("CREATE INDEX ix_consumer_billing_customers_user_id ON consumer_billing_customers (user_id)")
    op.execute("""
        CREATE TABLE provider_event_receipts (
            id UUID NOT NULL, provider VARCHAR(32) NOT NULL, external_event_id VARCHAR(255) NOT NULL,
            event_type VARCHAR(128) NOT NULL, provider_created_at TIMESTAMP WITHOUT TIME ZONE,
            outcome VARCHAR(32) NOT NULL, processed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id), CONSTRAINT uq_provider_event_receipt UNIQUE (provider, external_event_id)
        )
    """)
    op.execute("CREATE INDEX ix_provider_event_receipts_provider_created ON provider_event_receipts (provider, provider_created_at)")


def downgrade():
    op.drop_table("provider_event_receipts")
    op.drop_table("consumer_billing_customers")
    op.drop_column("consumer_subscriptions", "last_reconciled_at")
    op.drop_column("consumer_subscriptions", "livemode")
