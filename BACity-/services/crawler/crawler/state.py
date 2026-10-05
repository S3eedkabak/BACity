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
            CREATE TABLE IF NOT EXISTS candidates (
                domain TEXT PRIMARY KEY, url TEXT NOT NULL, origin TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'discovered', discovered REAL NOT NULL,
                inspected REAL, next_inspection REAL NOT NULL DEFAULT 0,
                evidence_count INTEGER NOT NULL DEFAULT 1, attempts INTEGER NOT NULL DEFAULT 0,
                good_runs INTEGER NOT NULL DEFAULT 0, failures INTEGER NOT NULL DEFAULT 0,
                reason TEXT, metrics TEXT NOT NULL DEFAULT '{}',
                CHECK(status IN ('discovered','inspected','probation','trusted','rejected','blocked','disabled')));
            CREATE INDEX IF NOT EXISTS ix_candidates_due ON candidates(status,next_inspection);
        """)
        columns = {row[1] for row in self.db.execute('PRAGMA table_info(outbox)')}
        source_columns = {row[1] for row in self.db.execute('PRAGMA table_info(sources)')}
        with self.db:
            if 'status' not in columns:
                self.db.execute("ALTER TABLE outbox ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
            if 'next_try' not in columns:
                self.db.execute("ALTER TABLE outbox ADD COLUMN next_try REAL NOT NULL DEFAULT 0")
            if 'enabled' not in source_columns:
                self.db.execute("ALTER TABLE sources ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1")
        from crawler.sources import ACTIVE_SOURCES
        known = {s.domain for s in ACTIVE_SOURCES}
        for row in self.db.execute('SELECT seed,discovered_from FROM sources WHERE discovered_from IS NOT NULL LIMIT 250').fetchall():
            seed=json.loads(row['seed'])
            if seed['domain'] not in known:
                try:
                    from crawler.discovery import candidate_url
                    domain, _ = candidate_url(seed['event_url'])
                    if not self.db.execute('SELECT 1 FROM candidates WHERE domain=?', (domain,)).fetchone():
                        self.discover(seed['event_url'],row['discovered_from'])
                    with self.db:
                        self.db.execute('UPDATE sources SET enabled=0 WHERE domain=?',(seed['domain'],))
                except ValueError:
                    with self.db:
                        self.db.execute('UPDATE sources SET enabled=0 WHERE domain=?',(seed['domain'],))

    def seed(self, seed, discovered_from=None):
        with self.db:
            self.db.execute("INSERT INTO sources(domain,seed,discovered_from) VALUES(?,?,?) ON CONFLICT(domain) DO UPDATE SET seed=excluded.seed",
                            (seed.domain, json.dumps(asdict(seed)), discovered_from))

    def due(self, now=None):
        return self.db.execute("SELECT * FROM sources WHERE enabled=1 AND domain NOT IN (SELECT domain FROM candidates) AND next_run<=? ORDER BY next_run,rowid LIMIT 250",
                               (now if now is not None else time.time(),)).fetchall()

    def apply_runtime_config(self, rows):
        """Apply only allow-listed scheduling controls from the authenticated API."""
        with self.db:
            for row in rows:
                domain = row.get('domain')
                if not domain or self.db.execute("SELECT 1 FROM sources WHERE domain=?", (domain,)).fetchone() is None:
                    continue
                existing = json.loads(self.db.execute("SELECT seed FROM sources WHERE domain=?", (domain,)).fetchone()[0])
                frequency = row.get('crawl_frequency_minutes')
                if isinstance(frequency, int) and 15 <= frequency <= 10080:
                    existing['crawl_frequency_minutes'] = frequency
                self.db.execute("UPDATE sources SET enabled=?,seed=? WHERE domain=?",
                                (int(bool(row.get('enabled', True))), json.dumps(existing), domain))

    def begin(self, domain):
        with self.db:
            return self.db.execute("INSERT INTO runs(domain,started) VALUES(?,?)",
                                   (domain, time.time())).lastrowid

    def finish(self, run_id, seed, success, stats, error=None):
        now = time.time()
        row = self.db.execute("SELECT failures FROM sources WHERE domain=?", (seed.domain,)).fetchone()
        failures = 0 if success else row[0] + 1
        delay = seed.crawl_frequency_minutes * 60 if success and stats.get('item_scraped_count', 0) else max(seed.crawl_frequency_minutes * 60, min(86400, 300 * 2 ** min(failures, 8)))
        with self.db:
            self.db.execute("UPDATE runs SET finished=?,success=?,stats=?,error=? WHERE id=?",
                            (now, int(success), json.dumps(stats, default=str), error, run_id))
            self.db.execute("UPDATE sources SET next_run=?,failures=?,last_success=CASE WHEN ? THEN ? ELSE last_success END WHERE domain=?",
                            (now + delay, failures, success, now, seed.domain))
            self.db.execute('DELETE FROM runs WHERE domain=? AND id NOT IN (SELECT id FROM runs WHERE domain=? ORDER BY id DESC LIMIT 50)',(seed.domain,seed.domain))
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

    def discover(self, url, origin, public=True):
        from crawler.discovery import candidate_url
        if not public:
            raise ValueError('private_evidence')
        domain, url = candidate_url(url)
        from crawler.sources import ACTIVE_SOURCES
        if domain in {s.domain.removeprefix('www.') for s in ACTIVE_SOURCES}:
            return False
        _, origin = candidate_url(origin)
        with self.db:
            existing = self.db.execute('SELECT domain FROM candidates WHERE domain=?', (domain,)).fetchone()
            if not existing and self.db.execute('SELECT count(*) FROM candidates').fetchone()[0] >= 250:
                return False
            self.db.execute("INSERT INTO candidates(domain,url,origin,discovered) VALUES(?,?,?,?) ON CONFLICT(domain) DO UPDATE SET evidence_count=min(evidence_count+1,10000)", (domain,url,origin,time.time()))
        return True

    def inspect_due(self):
        return self.db.execute("SELECT * FROM candidates WHERE status IN ('discovered','inspected','probation','trusted') AND next_inspection<=? ORDER BY next_inspection,domain LIMIT 5", (time.time(),)).fetchall()

    def candidate_result(self, domain, stats, success):
        from crawler.discovery import assess
        row = self.db.execute('SELECT * FROM candidates WHERE domain=?', (domain,)).fetchone()
        if not row or row['status'] == 'disabled':
            return
        attempts = row['attempts'] + 1
        failures = 0 if success else row['failures'] + 1
        accepted = stats.get('quality/events', 0)
        valid_ratio = accepted / max(accepted + stats.get('validation/rejected', 0), 1)
        mean_quality = stats.get('quality/score_total', 0) / max(accepted, 1)
        good = row['good_runs'] + 1 if success and accepted and valid_ratio >= .8 and mean_quality >= 60 else 0
        blocked = bool(stats.get('robotstxt/forbidden') or stats.get('downloader/response_status_count/403'))
        status, reason = assess(attempts, good, failures, stats, blocked)
        metrics = {k: v for k,v in stats.items() if (k.startswith('quality/') or k.startswith('validation/')) and isinstance(v,(int,float))}
        metrics = dict(list(metrics.items())[:30])
        delay = 21600 if status == 'trusted' else min(86400, 3600 * 2 ** min(failures, 4))
        with self.db:
            self.db.execute('UPDATE candidates SET status=?,reason=?,attempts=?,good_runs=?,failures=?,inspected=?,next_inspection=?,metrics=? WHERE domain=?',
                (status,reason,attempts,good,failures,time.time(),time.time()+delay,json.dumps(metrics),domain))
            # Discovered sources stay exclusively in this queue, never becoming
            # unrestricted trusted seeds or opening further discovery hops.
