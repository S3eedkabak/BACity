"""Optional real Postgres migration/backfill test, in an isolated temporary DB."""
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


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
            assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar() == '0003'
    finally:
        if db:
            db.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE {name} WITH (FORCE)'))
        admin.dispose()
