"""Read-only production-data inventory for BACity event/runtime diagnostics.

Run inside the API container so it uses the same DATABASE_URL as the app:
    python -m scripts.runtime_inventory

The transaction is explicitly read-only on PostgreSQL and the report contains
only aggregate event/source data (never users, tokens, coordinates, or secrets).
"""

from __future__ import annotations

import json

from sqlalchemy import text

from app.database import engine


SCALAR_QUERIES = {
    "events_total": "SELECT count(*) FROM events",
    "events_future": "SELECT count(*) FROM events WHERE start_time > timezone('UTC', now())",
    "events_ongoing_known": """
        SELECT count(*) FROM events
        WHERE start_time <= timezone('UTC', now())
          AND end_time > timezone('UTC', now())
    """,
    "events_past_known": """
        SELECT count(*) FROM events
        WHERE coalesce(end_time, start_time) < timezone('UTC', now())
    """,
    "events_missing_start": "SELECT count(*) FROM events WHERE start_time IS NULL",
    "events_missing_end": "SELECT count(*) FROM events WHERE end_time IS NULL",
    "events_with_category": "SELECT count(*) FROM events WHERE category IS NOT NULL",
    "events_without_category": "SELECT count(*) FROM events WHERE category IS NULL",
    "events_with_direct_coordinates": """
        SELECT count(*) FROM events WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """,
    "events_with_usable_coordinates": """
        SELECT count(*) FROM events e LEFT JOIN venues v ON v.id = e.venue_id
        WHERE (e.latitude IS NOT NULL AND e.longitude IS NOT NULL)
           OR (v.latitude IS NOT NULL AND v.longitude IS NOT NULL)
    """,
    "events_created_24h": """
        SELECT count(*) FROM events WHERE created_at >= timezone('UTC', now()) - interval '24 hours'
    """,
    "events_created_7d": """
        SELECT count(*) FROM events WHERE created_at >= timezone('UTC', now()) - interval '7 days'
    """,
    "events_created_30d": """
        SELECT count(*) FROM events WHERE created_at >= timezone('UTC', now()) - interval '30 days'
    """,
    "lifecycle_valid": "SELECT count(*) FROM events WHERE status::text IN ('fresh', 'stale')",
    "temporally_relevant": """
        SELECT count(*) FROM events
        WHERE status::text IN ('fresh', 'stale')
          AND (start_time > timezone('UTC', now()) OR end_time > timezone('UTC', now()))
    """,
    "recommendation_window_90d": """
        SELECT count(*) FROM events
        WHERE status::text IN ('fresh', 'stale')
          AND start_time >= timezone('UTC', now())
          AND start_time < timezone('UTC', now()) + interval '90 days'
    """,
    "map_api_eligible": """
        SELECT count(*) FROM events
        WHERE status::text IN ('fresh', 'stale')
          AND latitude IS NOT NULL AND longitude IS NOT NULL
    """,
    "legacy_first_page_mapped": """
        SELECT count(*) FROM (
          SELECT latitude, longitude FROM events
          WHERE status::text IN ('fresh', 'stale')
          ORDER BY start_time ASC LIMIT 100
        ) first_page
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """,
    "initial_map_viewport": """
        SELECT count(*) FROM events
        WHERE status::text IN ('fresh', 'stale')
          AND latitude BETWEEN 48.085 AND 48.225
          AND longitude BETWEEN 17.005 AND 17.215
    """,
    "planner_window_30d": """
        SELECT count(*) FROM events
        WHERE status::text IN ('fresh', 'stale')
          AND start_time >= timezone('UTC', now())
          AND start_time < timezone('UTC', now()) + interval '30 days'
    """,
    "event_source_links": "SELECT count(*) FROM event_sources",
    "canonical_events_with_multiple_sources": """
        SELECT count(*) FROM (
          SELECT event_id FROM event_sources GROUP BY event_id HAVING count(*) > 1
        ) linked
    """,
    "exact_title_start_duplicate_rows": """
        SELECT coalesce(sum(rows - 1), 0) FROM (
          SELECT count(*) AS rows FROM events
          GROUP BY lower(regexp_replace(title, '[^[:alnum:]]+', '', 'g')), start_time
          HAVING count(*) > 1
        ) duplicates
    """,
}


def grouped(connection, sql: str) -> list[dict[str, object]]:
    return [dict(row._mapping) for row in connection.execute(text(sql))]


def main() -> None:
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            if connection.dialect.name == "postgresql":
                connection.execute(text("SET TRANSACTION READ ONLY"))
            report = {
                "database_dialect": connection.dialect.name,
                "counts": {
                    name: connection.execute(text(sql)).scalar_one()
                    for name, sql in SCALAR_QUERIES.items()
                },
                "by_status": grouped(connection, """
                    SELECT status::text AS status, count(*) AS events
                    FROM events GROUP BY status ORDER BY events DESC, status
                """),
                "by_category": grouped(connection, """
                    SELECT category::text AS category, count(*) AS events
                    FROM events GROUP BY category ORDER BY events DESC, category
                """),
                "source_health": grouped(connection, """
                    SELECT name, status::text AS enabled_status, crawl_status,
                           items_processed, accepted_events, rejected_events,
                           extraction_errors, consecutive_failures,
                           last_attempt_at, last_success_at
                    FROM sources
                    ORDER BY name, domain
                """),
                "events_by_source": grouped(connection, """
                    SELECT s.name AS source, count(*) AS provenance_links,
                           count(DISTINCT es.event_id) AS canonical_events
                    FROM event_sources es JOIN sources s ON s.id = es.source_id
                    GROUP BY s.name ORDER BY canonical_events DESC, source
                """),
                "events_by_organizer": grouped(connection, """
                    SELECT coalesce(o.name, 'No organizer') AS organizer, count(*) AS events
                    FROM events e LEFT JOIN organizations o ON o.id = e.organization_id
                    GROUP BY o.name ORDER BY events DESC, organizer LIMIT 20
                """),
                "events_by_venue": grouped(connection, """
                    SELECT coalesce(v.name, 'No venue') AS venue, count(*) AS events
                    FROM events e LEFT JOIN venues v ON v.id = e.venue_id
                    GROUP BY v.name ORDER BY events DESC, venue LIMIT 20
                """),
                "provenance_distribution": grouped(connection, """
                    SELECT source_count, count(*) AS canonical_events
                    FROM (
                      SELECT event_id, count(*) AS source_count
                      FROM event_sources GROUP BY event_id
                    ) linked
                    GROUP BY source_count ORDER BY source_count
                """),
            }
            print(json.dumps(report, indent=2, default=str, sort_keys=True))
        finally:
            transaction.rollback()


if __name__ == "__main__":
    main()
