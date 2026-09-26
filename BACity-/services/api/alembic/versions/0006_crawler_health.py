"""Crawler source health and bounded run history."""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    for statement in (
        "ALTER TABLE sources ADD COLUMN last_attempt_at TIMESTAMP WITHOUT TIME ZONE",
        "ALTER TABLE sources ADD COLUMN last_success_at TIMESTAMP WITHOUT TIME ZONE",
        "ALTER TABLE sources ADD COLUMN crawl_status VARCHAR NOT NULL DEFAULT 'never_run'",
        "ALTER TABLE sources ADD COLUMN pages_processed INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE sources ADD COLUMN items_processed INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE sources ADD COLUMN accepted_events INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE sources ADD COLUMN rejected_events INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE sources ADD COLUMN extraction_errors INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE sources ADD COLUMN consecutive_failures INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE sources ADD COLUMN last_error VARCHAR",
        "ALTER TABLE sources ADD COLUMN last_skip_reasons JSON NOT NULL DEFAULT '{}'::json",
    ):
        op.execute(statement)
    op.execute("""
        CREATE TABLE crawler_runs (
            id UUID NOT NULL, source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            started_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            finished_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            success BOOLEAN NOT NULL, status VARCHAR NOT NULL,
            pages_processed INTEGER NOT NULL DEFAULT 0, items_processed INTEGER NOT NULL DEFAULT 0,
            accepted_events INTEGER NOT NULL DEFAULT 0, rejected_events INTEGER NOT NULL DEFAULT 0,
            extraction_errors INTEGER NOT NULL DEFAULT 0, skip_reasons JSON NOT NULL DEFAULT '{}'::json,
            error VARCHAR, created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(), PRIMARY KEY (id)
        )
    """)
    op.execute("CREATE INDEX ix_crawler_runs_source_id ON crawler_runs(source_id)")


def downgrade():
    op.drop_table("crawler_runs")
    for column in ("last_skip_reasons", "last_error", "consecutive_failures", "extraction_errors",
                   "rejected_events", "accepted_events", "items_processed", "pages_processed",
                   "crawl_status", "last_success_at", "last_attempt_at"):
        op.execute(f"ALTER TABLE sources DROP COLUMN {column}")
