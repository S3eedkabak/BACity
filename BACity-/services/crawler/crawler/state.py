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
                CHECK(status IN ('discovered','inspected','probation','trusted','degraded','rejected','blocked','disabled')));
            CREATE TABLE IF NOT EXISTS candidate_endpoints (
                url TEXT PRIMARY KEY, domain TEXT NOT NULL, discovered REAL NOT NULL,
                inspected REAL NOT NULL DEFAULT 0);
            CREATE INDEX IF NOT EXISTS ix_candidate_endpoints_host ON candidate_endpoints(domain,inspected);
            CREATE INDEX IF NOT EXISTS ix_candidates_due ON candidates(status,next_inspection);
        """)
        definition = self.db.execute("SELECT sql FROM sqlite_master WHERE name='candidates'").fetchone()[0]
        if "'degraded'" not in definition:
            with self.db:
                self.db.execute('ALTER TABLE candidates RENAME TO candidates_legacy')
                self.db.execute(definition.replace("'trusted','rejected'", "'trusted','degraded','rejected'"))
                self.db.execute('INSERT INTO candidates SELECT * FROM candidates_legacy')
                self.db.execute('DROP TABLE candidates_legacy')
                self.db.execute('CREATE INDEX ix_candidates_due ON candidates(status,next_inspection)')
        endpoint_columns = {r[1] for r in self.db.execute('PRAGMA table_info(candidate_endpoints)')}
        if 'origin' not in endpoint_columns:
            with self.db:
                self.db.execute('ALTER TABLE candidate_endpoints ADD COLUMN origin TEXT')
                self.db.execute('UPDATE candidate_endpoints SET origin=(SELECT origin FROM candidates WHERE candidates.domain=candidate_endpoints.domain)')
        endpoint_columns = {r[1] for r in self.db.execute('PRAGMA table_info(candidate_endpoints)')}
        if 'origin_verified' not in endpoint_columns:
            with self.db:
                self.db.execute('ALTER TABLE candidate_endpoints ADD COLUMN origin_verified INTEGER NOT NULL DEFAULT 0')
        candidate_columns = {r[1] for r in self.db.execute('PRAGMA table_info(candidates)')}
        with self.db:
            for name, spec in {'graph_depth':'INTEGER NOT NULL DEFAULT 1', 'qualified_observations':'INTEGER NOT NULL DEFAULT 0',
                               'last_qualified':'REAL', 'bad_runs':'INTEGER NOT NULL DEFAULT 0'}.items():
                if name not in candidate_columns:
                    self.db.execute(f'ALTER TABLE candidates ADD COLUMN {name} {spec}')
            self.db.execute("CREATE TABLE IF NOT EXISTS qualification_runs (run_id INTEGER PRIMARY KEY, domain TEXT NOT NULL, started REAL NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL, metrics TEXT NOT NULL)")
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

    def finish(self, run_id, seed, success, stats, error=None, inspection=False):
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
            if inspection:
                self.candidate_result(seed.domain,stats,success,run_id=run_id)
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
        parent, origin = candidate_url(origin)
        parent_row = self.db.execute('SELECT status,graph_depth FROM candidates WHERE domain=?',(parent,)).fetchone()
        graph_depth = 1
        if parent_row:
            from crawler.qualification import POLICY
            if parent_row['status'] not in ('probation','trusted') or parent_row['graph_depth'] >= POLICY.max_graph_depth:
                return False
            graph_depth = parent_row['graph_depth'] + 1
        with self.db:
            existing = self.db.execute('SELECT domain FROM candidates WHERE domain=?', (domain,)).fetchone()
            if not existing and self.db.execute('SELECT count(*) FROM candidates').fetchone()[0] >= 250:
                return False
            self.db.execute('UPDATE candidate_endpoints SET origin=?,origin_verified=1 WHERE url=? AND domain=?',(origin,url,domain))
            self.db.execute("INSERT INTO candidates(domain,url,origin,discovered,graph_depth) VALUES(?,?,?,?,?) ON CONFLICT(domain) DO NOTHING", (domain,url,origin,time.time(),graph_depth))
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
                added=self.db.execute('INSERT OR IGNORE INTO candidate_endpoints(url,domain,discovered,origin,origin_verified) VALUES(?,?,?,?,1)',(url,domain,time.time(),origin)).rowcount
                if existing and added:
                    self.db.execute('UPDATE candidates SET evidence_count=min(evidence_count+1,10000) WHERE domain=?',(domain,))
        return bool(added)

    def inspection_urls(self, domain):
        from crawler.discovery import endpoint_rank
        rows=self.db.execute('SELECT url,inspected,discovered FROM candidate_endpoints WHERE domain=?',(domain,)).fetchall()
        return [r['url'] for r in sorted(rows,key=lambda r:(r['inspected'],-endpoint_rank(r['url']),r['discovered']))[:4]]

    def inspect_due(self):
        from crawler.qualification import priority
        rows = self.db.execute("SELECT * FROM candidates WHERE status IN ('discovered','inspected','probation','trusted','degraded','rejected') AND next_inspection<=? ORDER BY next_inspection,domain LIMIT 250", (time.time(),)).fetchall()
        return sorted(rows,key=lambda r: (-(priority(r)+min(100,max(0,time.time()-(r['next_inspection'] or r['discovered']))/864)),r['domain']))[:5]

    def candidate_result(self, domain, stats, success, run_id=None):
        from crawler.qualification import POLICY, evidence
        row = self.db.execute('SELECT * FROM candidates WHERE domain=?', (domain,)).fetchone()
        if not row or row['status'] in ('disabled','blocked'):
            return
        if run_id is not None and self.db.execute('SELECT 1 FROM qualification_runs WHERE run_id=?',(run_id,)).fetchone():
            return
        run = self.db.execute('SELECT * FROM runs WHERE id=? AND domain=?',(run_id,domain)).fetchone() if run_id is not None else None
        now = time.time()
        independent = bool(run and run['success'] and run['started'] >= row['next_inspection'] and
                           (row['last_qualified'] is None or run['started']-row['last_qualified'] >= POLICY.independent_seconds))
        accepted, future, blockers = evidence(stats)
        failures = 0 if success else row['failures']+1
        good, observations, last = (row['good_runs'] if row['last_qualified'] else 0), row['qualified_observations'], row['last_qualified']
        qualified = success and independent and not blockers and not stats.get('audit')
        if qualified:
            good += 1
            observations += future
            last = run['started']
        productive = stats.get('quality/events',0) > 0
        bad = 0 if qualified else row['bad_runs']+1 if (not success or (stats.get('validation/rejected',0) and 'integrity_defects' in blockers) or (productive and 'low_extraction_confidence' in blockers)) else row['bad_runs']
        blocked = not productive and bool(stats.get('robotstxt/forbidden') or stats.get('downloader/response_status_count/403'))
        established = row['status'] in ('probation','trusted','degraded') or observations > 0
        if blocked:
            status,reason = 'blocked','robots_or_policy'
        elif established and bad >= POLICY.degradation_runs:
            status,reason = 'degraded','repeated_operational_or_integrity_failure'
            good = observations = 0
        elif not success:
            status,reason = ('probation' if established else 'inspected'),'temporary_failure'
            good = 0
        elif qualified and good >= POLICY.productive_runs and (observations >= POLICY.observations or good >= POLICY.low_volume_runs):
            status,reason = 'trusted','independent_validated_runs'
        elif row['status']=='trusted' and not blockers:
            status,reason = 'trusted','monitoring'
        elif productive or established:
            status,reason = 'probation',((blockers[0] if blockers else '') or ('awaiting_independent_schedule' if not independent else 'collecting_scheduled_evidence'))
        else:
            status,reason = 'inspected','unsupported_extraction' if stats.get('extraction/unsupported_pages') else 'no_valid_events'
        metrics = {k:v for k,v in stats.items() if k.startswith(('quality/','validation/','extraction/','ingestion/')) and isinstance(v,(int,float))}
        metrics.update({'qualification/blocker/'+b:1 for b in blockers})
        metrics.update({'qualification/independent':int(independent),'qualification/observations':observations,
                        'qualification/bad_runs':bad,'discovery/graph_depth':row['graph_depth'],
                        'operation/request_errors':stats.get('downloader/exception_count',0)+sum(v for k,v in stats.items() if k.startswith('downloader/response_status_count/5')),
                        'elapsed_time_seconds':stats.get('elapsed_time_seconds',0),
                        'operation/last_success':now if success else self.db.execute('SELECT coalesce(last_success,0) FROM sources WHERE domain=?',(domain,)).fetchone()[0] if self.db.execute('SELECT 1 FROM sources WHERE domain=?',(domain,)).fetchone() else 0,
                        'endpoints/count':self.db.execute('SELECT count(*) FROM candidate_endpoints WHERE domain=?',(domain,)).fetchone()[0]})
        delay = POLICY.trusted_seconds if status=='trusted' else POLICY.probation_seconds if productive else POLICY.dormant_seconds
        delay = max(delay, min(86400,3600*2**min(failures,4)), stats.get('source/retry_after_until',0)-now)
        metrics['schedule/next'] = now+delay
        with self.db:
            self.db.execute('UPDATE candidates SET status=?,reason=?,attempts=attempts+1,good_runs=?,failures=?,inspected=?,next_inspection=?,metrics=?,qualified_observations=?,last_qualified=?,bad_runs=? WHERE domain=?',
                (status,reason,good,failures,now,now+delay,json.dumps(metrics),observations,last,bad,domain))
            if run:
                self.db.execute('INSERT INTO qualification_runs VALUES(?,?,?,?,?,?)',(run_id,domain,run['started'],status,reason,json.dumps(metrics)))
                self.db.execute('DELETE FROM qualification_runs WHERE domain=? AND run_id NOT IN (SELECT run_id FROM qualification_runs WHERE domain=? ORDER BY run_id DESC LIMIT 50)',(domain,domain))
            for url in stats.get('inspection/urls',[row['url']])[:4]:
                self.db.execute('UPDATE candidate_endpoints SET inspected=? WHERE domain=? AND url=?',(now,domain,url))
