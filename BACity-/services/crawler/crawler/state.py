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
            CREATE TABLE IF NOT EXISTS candidate_endpoints (
                url TEXT PRIMARY KEY, domain TEXT NOT NULL, discovered REAL NOT NULL,
                inspected REAL NOT NULL DEFAULT 0);
            CREATE INDEX IF NOT EXISTS ix_candidate_endpoints_host ON candidate_endpoints(domain,inspected);
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
        with self.db:
            self.db.execute('CREATE INDEX IF NOT EXISTS ix_outbox_due ON outbox(status,next_try,created)')
            self.db.execute('CREATE INDEX IF NOT EXISTS ix_runs_domain ON runs(domain,id)')
            self.db.execute('INSERT OR IGNORE INTO candidate_endpoints(url,domain,discovered) SELECT url,domain,discovered FROM candidates c WHERE NOT EXISTS (SELECT 1 FROM candidate_endpoints e WHERE e.domain=c.domain)')
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
        delay = seed.crawl_frequency_minutes * 60 if success else min(3600, 300 * 2 ** min(max(failures-1,0), 4))
        delay = max(delay, stats.get('source/retry_after_until', 0)-now)
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
            existed=self.db.execute('SELECT 1 FROM outbox WHERE key=?',(key,)).fetchone() is not None
            self.db.execute("INSERT INTO outbox(key,payload,created) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET status=CASE WHEN payload!=excluded.payload THEN 'pending' ELSE status END,next_try=CASE WHEN payload!=excluded.payload THEN 0 ELSE next_try END,attempts=CASE WHEN payload!=excluded.payload THEN 0 ELSE attempts END,error=CASE WHEN payload!=excluded.payload THEN NULL ELSE error END,payload=excluded.payload",
                            (key, json.dumps(payload), time.time()))
            for metric,value in (('outbox_observations',1),('outbox_new_records',int(not existed))):
                self.db.execute('INSERT INTO metadata(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER)+CAST(excluded.value AS INTEGER)',(metric,str(value)))
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
            self.db.execute("INSERT INTO candidates(domain,url,origin,discovered) VALUES(?,?,?,?) ON CONFLICT(domain) DO NOTHING", (domain,url,origin,time.time()))
            # Keep independently evidenced endpoints without multiplying the
            # host's trust state, controls, concurrency or scheduling quota.
            from crawler.discovery import endpoint_rank
            added = 0
            endpoints = self.db.execute('SELECT url FROM candidate_endpoints WHERE domain=?',(domain,)).fetchall()
            if len(endpoints) >= 8 and url not in {r[0] for r in endpoints}:
                weakest = min(endpoints,key=lambda r:endpoint_rank(r[0]))[0]
                if endpoint_rank(url) > endpoint_rank(weakest):
                    self.db.execute('DELETE FROM candidate_endpoints WHERE url=?',(weakest,))
                    endpoints = endpoints[:-1]
            if len(endpoints) < 8:
                added=self.db.execute('INSERT OR IGNORE INTO candidate_endpoints(url,domain,discovered) VALUES(?,?,?)',(url,domain,time.time())).rowcount
                if existing and added:
                    self.db.execute('UPDATE candidates SET evidence_count=min(evidence_count+1,10000) WHERE domain=?',(domain,))
        return bool(added)

    def inspection_urls(self, domain):
        from crawler.discovery import endpoint_rank
        rows=self.db.execute('SELECT url,inspected,discovered FROM candidate_endpoints WHERE domain=?',(domain,)).fetchall()
        return [r['url'] for r in sorted(rows,key=lambda r:(r['inspected'],-endpoint_rank(r['url']),r['discovered']))[:4]]

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
        good = row['good_runs'] + 1 if success and accepted and stats.get('quality/future_events',accepted)>0 and valid_ratio >= .8 and mean_quality >= 60 else 0
        blocked = not accepted and bool(stats.get('robotstxt/forbidden') or stats.get('downloader/response_status_count/403'))
        status, reason = assess(attempts, good, failures, stats, blocked)
        metrics = {k: v for k,v in stats.items() if (k.startswith('quality/') or k.startswith('validation/')) and isinstance(v,(int,float))}
        metrics = dict(list(metrics.items())[:24])
        for key in ('extraction/unsupported_pages','extraction/raw','ingestion/queued','ingestion/delivered','ingestion/pending','elapsed_time_seconds'):
            if isinstance(stats.get(key),(int,float)):
                metrics[key] = stats[key]
        if not accepted and stats.get('extraction/unsupported_pages'):
            reason = 'unsupported_extraction'
        if not success and not blocked and failures < 3:
            status, reason = ('probation' if row['status'] in ('probation','trusted') else 'inspected'), 'temporary_failure'
        delay = 21600 if status == 'trusted' else min(86400, 3600 * 2 ** min(failures, 4))
        delay=max(delay,stats.get('source/retry_after_until',0)-time.time())
        with self.db:
            self.db.execute('UPDATE candidates SET status=?,reason=?,attempts=?,good_runs=?,failures=?,inspected=?,next_inspection=?,metrics=? WHERE domain=?',
                (status,reason,attempts,good,failures,time.time(),time.time()+delay,json.dumps(metrics),domain))
            for url in stats.get('inspection/urls', [row['url']])[:4]:
                self.db.execute('UPDATE candidate_endpoints SET inspected=? WHERE domain=? AND url=?',(time.time(),domain,url))
            # Discovered sources stay exclusively in this queue, never becoming
            # unrestricted trusted seeds or opening further discovery hops.
