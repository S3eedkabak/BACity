"""Private BACity+ Area Watch definitions.

Revision ID: 0010
Revises: 0009
"""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE area_watches (
            id UUID NOT NULL,
            user_id UUID NOT NULL,
            name VARCHAR(80) NOT NULL,
            center_latitude DOUBLE PRECISION NOT NULL,
            center_longitude DOUBLE PRECISION NOT NULL,
            radius_km DOUBLE PRECISION NOT NULL,
            categories JSONB NOT NULL DEFAULT '[]'::jsonb,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            last_viewed_at TIMESTAMP WITHOUT TIME ZONE,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT uq_area_watch_user_name UNIQUE (user_id, name),
            CONSTRAINT ck_area_watch_latitude CHECK (center_latitude >= 48 AND center_latitude <= 48.35),
            CONSTRAINT ck_area_watch_longitude CHECK (center_longitude >= 16.9 AND center_longitude <= 17.35),
            CONSTRAINT ck_area_watch_radius CHECK (radius_km IN (1, 2, 5))
        )
        """
    )
    op.execute("CREATE INDEX ix_area_watches_user_id ON area_watches (user_id)")
    op.execute("CREATE INDEX ix_area_watches_user_active ON area_watches (user_id, active)")
    op.execute("CREATE INDEX ix_events_area_watch_discovery ON events (created_at DESC, id DESC) WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND status IN ('fresh','stale')")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_events_area_watch_discovery")
    op.drop_table("area_watches")
