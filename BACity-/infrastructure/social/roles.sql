-- Run after Alembic, by the database owner, against the existing BACity database.
-- NOLOGIN groups only. Provision distinct LOGIN identities/passwords separately.
-- Never grant any application identity the migration-owner role.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='bacity_l4_staff') THEN CREATE ROLE bacity_l4_staff NOLOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='bacity_l4_gateway') THEN CREATE ROLE bacity_l4_gateway NOLOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='bacity_l4_relay') THEN CREATE ROLE bacity_l4_relay NOLOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='bacity_l4_maintenance') THEN CREATE ROLE bacity_l4_maintenance NOLOGIN; END IF;
END $$;

GRANT USAGE ON SCHEMA public TO bacity_l4_staff,bacity_l4_gateway,bacity_l4_relay,bacity_l4_maintenance;
GRANT SELECT,INSERT,UPDATE ON l4_staff,l4_credentials,l4_invitations,l4_challenges,l4_sessions,
  l4_rate_buckets,l4_publishers,l4_collection_jobs,l4_event_candidates,l4_control TO bacity_l4_staff;
GRANT SELECT,INSERT ON l4_candidate_reviews,l4_observations TO bacity_l4_staff;
GRANT SELECT ON events,venues,event_sources,event_occurrences,event_offers,sources TO bacity_l4_staff;

GRANT SELECT ON l4_publishers TO bacity_l4_gateway;
GRANT UPDATE(next_due,last_attempt,last_success,last_error,failures,checkpoint,eligibility,enabled) ON l4_publishers TO bacity_l4_gateway;
GRANT SELECT,INSERT,UPDATE ON l4_collection_jobs,l4_control,l4_rate_buckets TO bacity_l4_gateway;
GRANT SELECT,INSERT ON l4_observations,l4_event_candidates TO bacity_l4_gateway;

GRANT SELECT ON l4_staff,l4_publishers,l4_observations,l4_candidate_reviews,l4_control TO bacity_l4_relay;
GRANT SELECT,UPDATE ON l4_event_candidates TO bacity_l4_relay;
GRANT SELECT,INSERT,UPDATE ON events,venues,sources,event_sources,event_occurrences,event_offers,event_reconciliations TO bacity_l4_relay;

GRANT SELECT,DELETE ON l4_observations,l4_event_candidates,l4_candidate_reviews,l4_challenges,l4_invitations,
  l4_sessions,l4_rate_buckets,l4_collection_jobs TO bacity_l4_maintenance;

GRANT SELECT,INSERT ON l4_audit_events TO bacity_l4_staff,bacity_l4_gateway,bacity_l4_relay,bacity_l4_maintenance;
GRANT SELECT,INSERT,UPDATE ON l4_audit_head TO bacity_l4_staff,bacity_l4_gateway,bacity_l4_relay,bacity_l4_maintenance;
REVOKE UPDATE,DELETE,TRUNCATE ON l4_audit_events FROM PUBLIC,bacity_l4_staff,bacity_l4_gateway,bacity_l4_relay,bacity_l4_maintenance;
REVOKE UPDATE ON l4_observations FROM PUBLIC,bacity_l4_staff,bacity_l4_gateway,bacity_l4_relay,bacity_l4_maintenance;
-- No privileges on consumer identities, subscriptions, entitlements, messages or private storage.
-- The acquisition image receives none of these database identities, only a staging-only HTTP key.

-- Optional consumer runtime group: legacy data only, no L4 staff/session/credential tables.
-- Run Alembic separately as migration owner; the API runtime must not own the database.
DO $$ DECLARE t RECORD; BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='bacity_public_runtime') THEN CREATE ROLE bacity_public_runtime NOLOGIN; END IF;
  GRANT USAGE ON SCHEMA public TO bacity_public_runtime;
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='public' AND left(tablename,3)<>'l4_' AND tablename<>'alembic_version' LOOP
    EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON TABLE public.%I TO bacity_public_runtime',t.tablename);
  END LOOP;
  FOR t IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind='S' AND left(c.relname,3)<>'l4_' LOOP
    EXECUTE format('GRANT USAGE,SELECT ON SEQUENCE public.%I TO bacity_public_runtime',t.relname);
  END LOOP;
END $$;

-- ScrapingAnt accounting is private staging state. No keys are stored here.
GRANT SELECT ON l4_provider_budget,l4_provider_requests TO bacity_l4_staff;
GRANT SELECT,INSERT,UPDATE ON l4_provider_budget,l4_provider_requests TO bacity_l4_gateway;

-- Apify money ledger/run state is separate from ScrapingAnt; no tokens are stored.
GRANT SELECT ON l4_apify_budget,l4_apify_runs TO bacity_l4_staff;
GRANT SELECT,INSERT,UPDATE ON l4_apify_budget,l4_apify_runs TO bacity_l4_gateway;
GRANT SELECT,INSERT,UPDATE ON l4_instagram_items TO bacity_l4_gateway,bacity_l4_staff;

GRANT UPDATE(instagram_timestamp) ON l4_publishers TO bacity_l4_gateway;
GRANT SELECT ON l4_apify_runs,l4_provider_requests TO bacity_l4_maintenance;
GRANT UPDATE(items) ON l4_apify_runs TO bacity_l4_maintenance;

-- Delivery receipts contain hashes/results, not raw captions or provider tokens.
GRANT SELECT,INSERT ON l4_delivery_receipts TO bacity_l4_gateway;
GRANT SELECT ON l4_delivery_receipts TO bacity_l4_staff,bacity_l4_maintenance;
