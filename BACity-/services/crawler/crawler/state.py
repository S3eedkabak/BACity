"""Durable scheduler, discovery, delivery and geocoder state (shared worker volume)."""
import json
import os
import sqlite3
import time
from pathlib import Path
from dataclasses import asdict


class State:
    def __init__(self, path=None):
        path = path or os.getenv("CRAWLER_STATE_PATH", "crawler-state/state.db")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sources (
                domain TEXT PRIMARY KEY, seed TEXT NOT NULL, next_run REAL NOT NULL DEFAULT 0,
                failures INTEGER NOT NULL DEFAULT 0, discovered_from TEXT, last_success REAL);
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY, domain TEXT NOT NULL, started REAL NOT NULL,
                finished REAL, success INTEGER, stats TEXT, error TEXT);
            CREATE TABLE IF NOT EXISTS outbox (
                key TEXT PRIMARY KEY, payload TEXT NOT NULL, created REAL NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, error TEXT);
            CREATE TABLE IF NOT EXISTS geocache (
                query TEXT PRIMARY KEY, latitude REAL, longitude REAL, expires REAL);
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT);
        """)
        columns = {row[1] for row in self.db.execute('PRAGMA table_info(outbox)')}
        with self.db:
            if 'status' not in columns:
                self.db.execute("ALTER TABLE outbox ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
            if 'next_try' not in columns:
                self.db.execute("ALTER TABLE outbox ADD COLUMN next_try REAL NOT NULL DEFAULT 0")

    def seed(self, seed, discovered_from=None):
        with self.db:
            self.db.execute("INSERT INTO sources(domain,seed,discovered_from) VALUES(?,?,?) ON CONFLICT(domain) DO UPDATE SET seed=excluded.seed",
                            (seed.domain, json.dumps(asdict(seed)), discovered_from))

    def due(self, now=None):
        return self.db.execute("SELECT * FROM sources WHERE next_run<=? ORDER BY next_run,rowid",
                               (now if now is not None else time.time(),)).fetchall()

    def begin(self, domain):
        with self.db:
            return self.db.execute("INSERT INTO runs(domain,started) VALUES(?,?)",
                                   (domain, time.time())).lastrowid

    def finish(self, run_id, seed, success, stats, error=None):
        now = time.time()
        row = self.db.execute("SELECT failures FROM sources WHERE domain=?", (seed.domain,)).fetchone()
        failures = 0 if success else row[0] + 1
        delay = seed.crawl_frequency_minutes * 60 if success else min(3600, 60 * 2 ** min(failures, 6))
        with self.db:
            self.db.execute("UPDATE runs SET finished=?,success=?,stats=?,error=? WHERE id=?",
                            (now, int(success), json.dumps(stats, default=str), error, run_id))
            self.db.execute("UPDATE sources SET next_run=?,failures=?,last_success=CASE WHEN ? THEN ? ELSE last_success END WHERE domain=?",
                            (now + delay, failures, success, now, seed.domain))
        return failures

    def enqueue(self, payload):
        import hashlib
        key = hashlib.sha256(json.dumps([payload['source_url'], payload['title'], payload['start_time']]).encode()).hexdigest()
        with self.db:
            self.db.execute("INSERT INTO outbox(key,payload,created) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload,status='pending',next_try=0",
                            (key, json.dumps(payload), time.time()))
        return key

    def close(self):
        self.db.close()
