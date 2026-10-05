"""Optional real Postgres migration/backfill test, in an isolated temporary DB."""
import os
from datetime import date, datetime, timedelta
from pathlib import Path
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.api.routes.area_watches import _lock_owner, _owned
from app.api.routes.groups import _group
from app.models.area_watch import AreaWatch
from app.models.group import GroupSession
from app.models.user import User
from app.models.entitlement import ConsumerSubscription


@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'), reason='TEST_POSTGRES_URL not configured')
def test_upgrade_backfills_existing_source_references():
    url = make_url(os.environ['TEST_POSTGRES_URL'])
    name = 'bacity_test_' + uuid.uuid4().hex
    admin = create_engine(url, isolation_level='AUTOCOMMIT')
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE {name}'))
    test_url = url.set(database=name)
    env = {**os.environ, 'DATABASE_URL': test_url.render_as_string(hide_password=False)}
    api_dir = Path(__file__).resolve().parents[1]
    db = None
    try:
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', '0002'], cwd=api_dir, env=env, check=True, capture_output=True)
        db = create_engine(test_url)
        with db.begin() as connection:
            connection.execute(text("INSERT INTO events(id,title,start_time,source_url,category,status,tags) VALUES(:id,'Test Jazz',CURRENT_TIMESTAMP,'https://venue.example/event','Music','fresh','[]')"), {'id': uuid.uuid4()})
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=api_dir, env=env, check=True, capture_output=True)
        with db.connect() as connection:
            row = connection.execute(text('SELECT title_key,source_url FROM event_sources')).one()
            assert row.title_key == 'test jazz'
            assert row.source_url == 'https://venue.example/event'
            assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar() == '0013'
            assert connection.execute(text("SELECT data_type FROM information_schema.columns WHERE table_name='event_sources' AND column_name='facts'")).scalar() == 'jsonb'
            assert connection.execute(text("SELECT count(*) FROM pg_constraint WHERE conname='ck_candidate_status'")).scalar() == 1
            assert connection.execute(text("SELECT count(*) FROM pg_indexes WHERE indexname='ix_candidate_status_inspected'")).scalar() == 1
            assert connection.execute(text("SELECT data_type FROM information_schema.columns WHERE table_name='consumer_subscriptions' AND column_name='provider_purchase_token'")).scalar() == 'text'
            assert connection.execute(text('SELECT trust_level FROM events')).scalar() == 'Unverified'
            assert connection.execute(text('SELECT count(*) FROM submissions')).scalar() == 0
            assert connection.execute(text('SELECT count(*) FROM oauth_identities')).scalar() == 0
            assert connection.execute(text('SELECT count(*) FROM crawler_runs')).scalar() == 0
            assert connection.execute(text('SELECT count(*) FROM oauth_identities WHERE refresh_token_encrypted IS NOT NULL')).scalar() == 0
            assert connection.execute(text('SELECT count(*) FROM consumer_subscriptions')).scalar() == 0
            assert connection.execute(text('SELECT count(*) FROM entitlement_grants')).scalar() == 0
            assert connection.execute(text('SELECT count(*) FROM group_sessions')).scalar() == 0
            assert connection.execute(text('SELECT count(*) FROM group_participants')).scalar() == 0
            assert connection.execute(text('SELECT count(*) FROM group_match_rounds')).scalar() == 0
            assert connection.execute(text('SELECT count(*) FROM group_candidates')).scalar() == 0
            assert connection.execute(text('SELECT count(*) FROM group_votes')).scalar() == 0
            assert connection.execute(text('SELECT count(*) FROM area_watches')).scalar() == 0
            assert connection.execute(text('SELECT count(*) FROM consumer_billing_customers')).scalar() == 0
            assert connection.execute(text('SELECT count(*) FROM provider_event_receipts')).scalar() == 0
            jsonb_columns = set(connection.execute(text("""
                SELECT table_name || '.' || column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND data_type = 'jsonb'
            """)).scalars())
            assert {'group_sessions.categories', 'group_participants.liked_categories',
                    'group_participants.disliked_categories', 'group_candidates.explanations',
                    'area_watches.categories'} <= jsonb_columns
            constraints = set(connection.execute(text("""
                SELECT conname FROM pg_constraint
                WHERE connamespace = 'public'::regnamespace
            """)).scalars())
            assert {'uq_group_participant', 'uq_group_match_round_number', 'uq_group_candidate_event',
                    'uq_group_candidate_position', 'uq_group_vote', 'ck_group_vote_value',
                    'ck_group_session_status', 'ck_group_session_participant_limit',
                    'uq_area_watch_user_name', 'ck_area_watch_latitude', 'ck_area_watch_longitude',
                    'ck_area_watch_radius', 'uq_consumer_billing_customer_provider_user',
                    'uq_consumer_billing_customer_provider_external', 'uq_provider_event_receipt'} <= constraints
            indexes = set(connection.execute(text("""
                SELECT indexname FROM pg_indexes WHERE schemaname = 'public'
            """)).scalars())
            assert {'uq_group_match_active_round', 'ix_group_sessions_host_status',
                    'ix_group_participants_user_group', 'ix_group_votes_user_candidate',
                    'ix_area_watches_user_active', 'ix_events_area_watch_discovery'} <= indexes
            assert {'ix_consumer_billing_customers_user_id',
                    'ix_provider_event_receipts_provider_created'} <= indexes
            columns = set(connection.execute(text("""
                SELECT table_name || '.' || column_name FROM information_schema.columns
                WHERE table_schema = 'public'
            """)).scalars())
            assert {'consumer_subscriptions.livemode', 'consumer_subscriptions.last_reconciled_at',
                    'consumer_billing_customers.pending_checkout_session_id'} <= columns
            cascades = connection.execute(text("""
                SELECT count(*) FROM pg_constraint
                WHERE connamespace = 'public'::regnamespace
                  AND contype = 'f' AND confdeltype = 'c'
                  AND conrelid::regclass::text IN ('group_sessions','group_participants','group_match_rounds','group_candidates','group_votes')
            """)).scalar()
            assert cascades == 8
            area_watch_cascade = connection.execute(text("""
                SELECT count(*) FROM pg_constraint
                WHERE connamespace = 'public'::regnamespace AND contype = 'f'
                  AND confdeltype = 'c' AND conrelid::regclass::text = 'area_watches'
            """)).scalar()
            assert area_watch_cascade == 1

        sessions = sessionmaker(bind=db)
        # Exercise the new ORM JSONB evidence and correlated lifecycle SQL on
        # PostgreSQL, not only SQLite's metadata-created test schema.
        from app.crud.ingestion import ingest, expire_events
        from app.schemas.event import EventCreate
        from app.models.event_source import EventSource
        from datetime import timezone
        with sessions() as verification:
            starts=datetime.now(timezone.utc)+timedelta(days=2)
            event=ingest(verification,EventCreate(title='Postgres evidence audit',
                start_time=starts,end_time=starts+timedelta(hours=2),
                venue_name='Audit Hall',address='Bratislava',
                source_url='https://audit.example/events/1',temporal_evidence='explicit_end'))
            evidence=verification.query(EventSource).filter_by(event_id=event.id).one()
            assert evidence.facts['best_end']['rank'] == 3
            expire_events(verification)
        with sessions.begin() as seed:
            owner = User(email='locking@example.com', hashed_password='not-used')
            seed.add(owner)
            seed.flush()
            group = GroupSession(
                host_id=owner.id, name='Lock audit', target_date=date.today(),
                starts_at=datetime.utcnow(), ends_at=datetime.utcnow() + timedelta(hours=2),
                categories=[], expires_at=datetime.utcnow() + timedelta(days=1),
                purge_after=datetime.utcnow() + timedelta(days=31),
            )
            watch = AreaWatch(
                user_id=owner.id, name='Lock audit', center_latitude=48.1486,
                center_longitude=17.1077, radius_km=2, categories=[],
            )
            seed.add_all([group, watch])
            seed.flush()
            owner_id, group_id, watch_id = owner.id, group.id, watch.id

        def assert_row_lock(acquire):
            first, second = sessions(), sessions()
            try:
                acquire(first)
                second.execute(text("SET LOCAL lock_timeout = '100ms'"))
                with pytest.raises(OperationalError):
                    acquire(second)
            finally:
                second.rollback()
                first.rollback()
                second.close()
                first.close()

        assert_row_lock(lambda session: _group(session, group_id, for_update=True))
        assert_row_lock(lambda session: _owned(session, watch_id, owner_id, for_update=True))
        assert_row_lock(lambda session: _lock_owner(session, owner_id))
        with sessions.begin() as seed:
            seed.add(ConsumerSubscription(
                user_id=owner_id, provider='stripe', entitlement='bacity_plus',
                external_subscription_id='stripe-preserved', product_id='price_plus', status='active',
            ))
            seed.add(ConsumerSubscription(
                user_id=owner_id, provider='google_play', entitlement='bacity_plus',
                external_subscription_id='a' * 64, provider_purchase_token='test-only-' + 'x' * 4096,
                product_id='test_product', status='expired',
            ))
        with db.connect() as connection:
            assert connection.execute(text("SELECT length(provider_purchase_token) FROM consumer_subscriptions WHERE provider='google_play'")).scalar() == 4106
        subprocess.run([sys.executable, '-m', 'alembic', 'downgrade', '0011'], cwd=api_dir, env=env, check=True, capture_output=True)
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=api_dir, env=env, check=True, capture_output=True)
        with db.connect() as connection:
            assert connection.execute(text("SELECT status FROM consumer_subscriptions WHERE external_subscription_id='stripe-preserved'")).scalar() == 'active'
            assert connection.execute(text("SELECT provider_purchase_token FROM consumer_subscriptions WHERE provider='google_play'")).scalar() is None
        subprocess.run([sys.executable, '-m', 'alembic', 'downgrade', '0003'], cwd=api_dir, env=env, check=True, capture_output=True)
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=api_dir, env=env, check=True, capture_output=True)
    finally:
        if db:
            db.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE {name} WITH (FORCE)'))
        admin.dispose()
