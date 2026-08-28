"""initial schema: sources, venues, events, users

Revision ID: 0001
Revises:
Create Date: 2026-08-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

source_type_enum = postgresql.ENUM(
    "venue", "club", "restaurant", "theatre", "museum", "gallery", "university",
    "community", "sports", "festival", "government", "tourism", "blog", "event_platform",
    name="sourcetype",
)
source_status_enum = postgresql.ENUM(
    "active", "paused", "disabled", "failing", name="sourcestatus"
)
event_category_enum = postgresql.ENUM(
    "Music", "Nightlife", "Culture", "Arts", "Theatre", "Sports", "Food & Drink",
    "Education", "Workshops", "Community", "Networking", "Family", "Markets",
    "Festivals", "Student", "Technology", "Comedy", "Exhibitions", "Other",
    name="eventcategory",
)
event_status_enum = postgresql.ENUM(
    "fresh", "stale", "expired", "removed", "cancelled", name="eventstatus"
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    bind = op.get_bind()
    source_type_enum.create(bind, checkfirst=True)
    source_status_enum.create(bind, checkfirst=True)
    event_category_enum.create(bind, checkfirst=True)
    event_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("domain", sa.String, nullable=False, unique=True),
        sa.Column("base_url", sa.String, nullable=False),
        sa.Column("event_url", sa.String, nullable=True),
        sa.Column("source_type", source_type_enum, nullable=False),
        sa.Column("language", sa.String, nullable=False, server_default="sk"),
        sa.Column("city", sa.String, nullable=False, server_default="Bratislava"),
        sa.Column("crawl_frequency_minutes", sa.Integer, nullable=False, server_default="720"),
        sa.Column("last_crawled", sa.DateTime, nullable=True),
        sa.Column("next_crawl", sa.DateTime, nullable=True),
        sa.Column("parser", sa.String, nullable=True),
        sa.Column("reliability_score", sa.Float, nullable=False, server_default="0.7"),
        sa.Column("status", source_status_enum, nullable=False),
        sa.Column("requires_js", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_sources_domain", "sources", ["domain"])

    op.create_table(
        "venues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("address", sa.String, nullable=True),
        sa.Column("city", sa.String, nullable=False, server_default="Bratislava"),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("website", sa.String, nullable=True),
        sa.Column("category", sa.String, nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("verified", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_venues_name", "venues", ["name"])

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("start_time", sa.DateTime, nullable=False),
        sa.Column("end_time", sa.DateTime, nullable=True),
        sa.Column("timezone", sa.String, nullable=False, server_default="Europe/Bratislava"),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("venues.id"), nullable=True),
        sa.Column("address", sa.String, nullable=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("category", event_category_enum, nullable=False),
        sa.Column("tags", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("price", sa.Float, nullable=True),
        sa.Column("currency", sa.String, nullable=True, server_default="EUR"),
        sa.Column("image_url", sa.String, nullable=True),
        sa.Column("source_url", sa.String, nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("language", sa.String, nullable=False, server_default="sk"),
        sa.Column("extraction_confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("source_reliability", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("status", event_status_enum, nullable=False),
        sa.Column("is_manual_override", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("last_verified_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_events_title", "events", ["title"])
    op.create_index("ix_events_start_time", "events", ["start_time"])
    # Speeds up bounding-box prefiltering for /events/nearby even before a
    # dedicated PostGIS geometry column is introduced.
    op.create_index("ix_events_lat_lng", "events", ["latitude", "longitude"])

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String, nullable=False, unique=True),
        sa.Column("hashed_password", sa.String, nullable=False),
        sa.Column("display_name", sa.String, nullable=True),
        sa.Column("interests", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])


def downgrade() -> None:
    op.drop_table("users")
    op.drop_table("events")
    op.drop_table("venues")
    op.drop_table("sources")
    event_status_enum.drop(op.get_bind(), checkfirst=True)
    event_category_enum.drop(op.get_bind(), checkfirst=True)
    source_status_enum.drop(op.get_bind(), checkfirst=True)
    source_type_enum.drop(op.get_bind(), checkfirst=True)
