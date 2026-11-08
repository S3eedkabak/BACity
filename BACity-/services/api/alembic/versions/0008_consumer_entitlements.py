"""Provider-neutral BACity+ consumer entitlements.

Revision ID: 0008
Revises: 0007
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE consumer_subscriptions (
            id UUID NOT NULL,
            user_id UUID NOT NULL,
            entitlement VARCHAR(64) NOT NULL DEFAULT 'bacity_plus',
            provider VARCHAR(32) NOT NULL,
            external_customer_id VARCHAR(255),
            external_subscription_id VARCHAR(255),
            product_id VARCHAR(255) NOT NULL,
            status VARCHAR(32) NOT NULL,
            current_period_start TIMESTAMP WITHOUT TIME ZONE,
            current_period_end TIMESTAMP WITHOUT TIME ZONE,
            cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
            cancelled_at TIMESTAMP WITHOUT TIME ZONE,
            expires_at TIMESTAMP WITHOUT TIME ZONE,
            provider_updated_at TIMESTAMP WITHOUT TIME ZONE,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT uq_consumer_subscription_provider_external
                UNIQUE (provider, external_subscription_id),
            CONSTRAINT ck_consumer_subscription_period CHECK (
                current_period_start IS NULL OR current_period_end IS NULL OR current_period_end > current_period_start
            )
        )
        """
    )
    op.execute("CREATE INDEX ix_consumer_subscriptions_user_id ON consumer_subscriptions (user_id)")
    op.execute("CREATE INDEX ix_consumer_subscriptions_status ON consumer_subscriptions (status)")
    op.execute("CREATE INDEX ix_consumer_subscriptions_user_entitlement_status ON consumer_subscriptions (user_id, entitlement, status)")

    op.execute(
        """
        CREATE TABLE entitlement_grants (
            id UUID NOT NULL,
            user_id UUID NOT NULL,
            entitlement VARCHAR(64) NOT NULL,
            source VARCHAR(32) NOT NULL,
            reason_category VARCHAR(64) NOT NULL,
            valid_from TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            valid_until TIMESTAMP WITHOUT TIME ZONE,
            revoked_at TIMESTAMP WITHOUT TIME ZONE,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_by_id UUID,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(created_by_id) REFERENCES users(id) ON DELETE SET NULL,
            CONSTRAINT ck_entitlement_grant_validity CHECK (valid_until IS NULL OR valid_until > valid_from)
        )
        """
    )
    op.execute("CREATE INDEX ix_entitlement_grants_user_id ON entitlement_grants (user_id)")
    op.execute("CREATE INDEX ix_entitlement_grants_user_entitlement_validity ON entitlement_grants (user_id, entitlement, valid_from, valid_until)")


def downgrade():
    op.drop_table("entitlement_grants")
    op.drop_table("consumer_subscriptions")
