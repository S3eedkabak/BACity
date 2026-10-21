"""Run with python -m crawler.worker; one scheduler per persistent state volume."""
import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import replace

import requests
from filelock import FileLock, Timeout

from crawler.sources import ACTIVE_SOURCES, SourceSeed
from crawler.state import State

log = logging.getLogger(__name__)
stop = threading.Event()


def deliver(state, api_url, token="", limit=500, budget_seconds=30):
    """Keep failed submissions on disk, including across process restarts."""
    delivered = 0
    deadline = time.monotonic() + budget_seconds
    headers = {"X-Ingestion-Key": token} if token else {}
    for row in state.db.execute("SELECT * FROM outbox WHERE status='pending' AND next_try<=? ORDER BY created LIMIT ?", (time.time(), limit)).fetchall():
        if time.monotonic() >= deadline:
            break
        try:
            response = requests.post(f"{api_url.rstrip('/')}/events", json=json.loads(row['payload']), headers=headers, timeout=max(.1,min(20,deadline-time.monotonic())))
            response.raise_for_status()
        except requests.RequestException as exc:
            status = exc.response.status_code if exc.response is not None else 0
            permanent = status in (400, 404, 413, 422)
            from crawler.retry import retry_after
            wait=min(3600, 30 * 2 ** min(row['attempts'],7))
            if status in (429,503):
                wait=max(wait,retry_after(exc.response.headers.get('Retry-After')))
            with state.db:
                state.db.execute("UPDATE outbox SET attempts=attempts+1,error=?,status=?,next_try=? WHERE key=?",
                                 (str(exc), 'rejected' if permanent else 'pending', time.time() + wait, row['key']))
            log.error("Event delivery failed: %s", exc)
            if permanent:
                continue
            # Back off for unavailable API instead of spending minutes on every queued item.
            break
        else:
            with state.db:
                state.db.execute("DELETE FROM outbox WHERE key=?", (row['key'],))
                state.db.execute("INSERT INTO metadata(key,value) VALUES('outbox_delivered','1') ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER)+1")
            delivered += 1
    return delivered


def _safe_stats(stats):
    reasons = {key.rsplit('/', 1)[-1]: int(value) for key, value in stats.items()
               if key.startswith('validation/rejected/') and isinstance(value, (int, float))}
    pages = int(stats.get('response_received_count', 0))
    items = int(stats.get('item_scraped_count', 0))
    rejected = int(stats.get('validation/rejected', 0))
    errors = int(stats.get('extraction/errors', 0)) + int(stats.get('source/request_errors', 0)) + int(stats.get('item_error_count',0))
    return pages, int(stats.get('pipeline/raw_listings',stats.get('extraction/raw', items + rejected))), items, rejected, errors, dict(list(reasons.items())[:20])


def report_run(api_url, token, seed, started, finished, success, stats, error):
    pages, items, accepted, rejected, extraction_errors, reasons = _safe_stats(stats)
    status = 'healthy' if success and accepted else 'empty' if success else 'timed_out' if error and 'timeout' in error else 'failed'
    if success and (stats.get('finish_reason','finished') != 'finished' or stats.get('resource/item_limit') or stats.get('resource/page_limit')):
        status = 'partial'  # A quota-limited scan cannot establish upstream absence.
    body = {'name': seed.name, 'domain': seed.domain, 'base_url': seed.base_url, 'event_url': seed.event_url,
            'source_type': seed.source_type, 'language': seed.language, 'parser': seed.parser,
            'reliability_score': seed.reliability_score, 'requires_js': seed.requires_js,
            'crawl_frequency_minutes': seed.crawl_frequency_minutes,
            'started_at': datetime.fromtimestamp(started, timezone.utc).isoformat(),
            'finished_at': datetime.fromtimestamp(finished, timezone.utc).isoformat(), 'success': success,
            'status': status, 'pages_processed': pages, 'items_processed': items,
            'accepted_events': accepted, 'rejected_events': rejected, 'extraction_errors': extraction_errors,
            'skip_reasons': reasons, 'error': (error or '')[:2000] or None,
            'quality_metrics': {**{k.removeprefix('quality/'):float(v) for k,v in stats.items() if k.startswith('quality/') and isinstance(v,(int,float))},
                                'crawl_duration_seconds':max(0,finished-started),
                                **{k:float(stats.get(k,0)) for k in ('pipeline/raw_listings','pipeline/normalized_listings','extraction/raw','ingestion/queued','ingestion/delivered','ingestion/pending','extraction/unsupported_pages','source/request_errors','geocoding/requests','geocoding/errors','geocoding/cache_hit','geocoding/deferred')}}}
    response = requests.post(f"{api_url.rstrip('/')}/crawler/runs", json=body,
                             headers={'X-Ingestion-Key': token} if token else {}, timeout=20)
    response.raise_for_status()


def sync_runtime_config(state, api_url, token):
    try:
        response = requests.get(f"{api_url.rstrip('/')}/crawler/runtime",
                                headers={'X-Ingestion-Key': token} if token else {}, timeout=20)
        response.raise_for_status()
        state.apply_runtime_config(response.json())
    except (requests.RequestException, ValueError, TypeError) as exc:
        log.warning("Crawler runtime configuration unavailable; retaining local schedule: %s", exc)


def collect_orphan_run_stats(state, state_path, now=None, retention_seconds=86400, limit=100):
    """Remove only abandoned scratch statistics; durable runs/outbox remain."""
    now=now or time.time()
    removed=0
    for path in Path(state_path).parent.glob('run-*.json'):
        if removed>=limit:break
        try:
            run_id=int(path.stem.removeprefix('run-'))
            row=state.db.execute('SELECT finished FROM runs WHERE id=?',(run_id,)).fetchone()
            if row is None or row['finished'] is None or now-path.stat().st_mtime < retention_seconds:
                continue
            path.unlink()
            removed+=1
        except (ValueError,OSError):
            continue
    return removed


def run_source(state, seed, api_url=None, token="", inspection=False):
    run_id = state.begin(seed.domain)
    started = state.db.execute("SELECT started FROM runs WHERE id=?", (run_id,)).fetchone()[0]
    stats_path = Path(os.getenv("CRAWLER_STATE_PATH", "crawler-state/state.db")).parent / f"run-{run_id}.json"
    command = [sys.executable, "-m", "crawler.run", "--source", json.dumps(seed.__dict__), "--stats", str(stats_path)]
    if inspection:
        command.append('--inspection')
    error = None
    stats = {}
    process = subprocess.Popen(command)
    deadline = time.monotonic() + (120 if inspection else int(os.getenv("CRAWLER_JOB_TIMEOUT", "900")))
    heartbeat_due = 0
    while process.poll() is None:
        if time.monotonic() >= heartbeat_due:
            with state.db:
                state.db.execute("INSERT OR REPLACE INTO metadata VALUES('heartbeat',?)", (str(time.time()),))
            heartbeat_due = time.monotonic() + 30
        if stop.wait(1) or time.monotonic() > deadline:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            error = "interrupted or job timeout"
            break
    if stats_path.exists():
        try:
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
            if not isinstance(stats,dict):
                raise ValueError('stats must be an object')
        except (ValueError,OSError) as exc:
            error = 'invalid or interrupted crawl statistics: ' + type(exc).__name__
            stats = {}
        finally:
            stats_path.unlink(missing_ok=True)
    success = process.returncode == 0 and stats.get("success", False)
    if inspection:
        stats['inspection/urls'] = [seed.event_url, *seed.entry_urls]
    failures = state.finish(run_id, seed, success, stats, error or stats.get("error") or stats.get("source/last_error"), inspection=inspection)
    log.info("CRAWL_RESULT source=%s success=%s stats=%s", seed.domain, success, stats)
    if failures >= 3:
        log.error("CRAWLER_ALERT repeated_failure source=%s failures=%s", seed.domain, failures)
    if api_url:
        try:
            report_run(api_url, token, seed, started, time.time(), success, stats, error or stats.get("error") or stats.get("source/last_error"))
        except requests.RequestException as exc:
            log.warning("Could not publish source health for %s: %s", seed.domain, exc)
    return success


def discovery_cycle(state, api_url, token, limit=5):
    if not token:
        log.warning('Source-learning synchronization requires an ingestion key')
        return
    headers = {'X-Ingestion-Key': token}
    try:
        requests.post(api_url.rstrip('/') + '/crawler/learning/process', headers=headers, timeout=20).raise_for_status()
    except requests.RequestException:
        log.warning('Published-source learning unavailable; durable API work retained')
    try:
        response = requests.get(api_url.rstrip('/') + '/crawler/candidates/runtime', headers=headers, timeout=20)
        response.raise_for_status()
        for row in response.json()[:250]:
            try:
                state.discover(row['url'], row['origin'])
            except (KeyError, ValueError):
                continue
            with state.db:
                if not row['enabled']:
                    state.db.execute("UPDATE candidates SET status='disabled' WHERE domain=?", (row['domain'],))
                else:
                    state.db.execute("UPDATE candidates SET status='discovered',next_inspection=0 WHERE domain=? AND status='disabled'", (row['domain'],))
                    if row['status'] == 'discovered' and row['attempts'] == 0:
                        state.db.execute("UPDATE candidates SET status='discovered',next_inspection=0,attempts=0,good_runs=0,failures=0 WHERE domain=? AND status IN ('blocked','rejected')",(row['domain'],))
    except (requests.RequestException, ValueError, TypeError):
        # Retain local, already validated queue on API failure.
        log.warning('Candidate controls unavailable; retaining local state')
    for row in state.inspect_due()[:limit]:
        if stop.is_set():
            break
        urls = state.inspection_urls(row['domain']) or [row['url']]
        seed = SourceSeed(row['domain'], row['domain'], urls[0], urls[0], 'event_platform',
                          .6 if row['status'] != 'trusted' else .75, parser='structured', crawl_frequency_minutes=360, entry_urls=urls[1:])
        state.seed(seed, row['origin'])
        run_source(state, seed, api_url, token, inspection=True)
    rows = []
    for row in state.db.execute('SELECT * FROM candidates ORDER BY domain LIMIT 250'):
        rows.append({key: row[key] for key in ('domain','url','origin','status','discovered','inspected','attempts','good_runs','failures','reason')})
        rows[-1]['metrics'] = json.loads(row['metrics'])
    try:
        requests.post(api_url.rstrip('/') + '/crawler/candidates/report', json={'items': rows}, headers=headers, timeout=20).raise_for_status()
    except requests.RequestException:
        log.warning('Candidate snapshot unavailable; durable local queue retained')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run currently due sources, drain delivery queue, then exit")
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--status", action="store_true", help="Print source schedules, recent jobs and queue health")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    state_path = os.getenv("CRAWLER_STATE_PATH", "crawler-state/state.db")
    Path(state_path).parent.mkdir(parents=True, exist_ok=True)
    if args.status:
        state = State(state_path)
        print(json.dumps({'sources': [dict(r) for r in state.db.execute('SELECT domain,enabled,next_run,failures,last_success,discovered_from FROM sources')],
                          'runs': [dict(r) for r in state.db.execute('SELECT * FROM runs ORDER BY id DESC LIMIT 20')],
                          'delivery': [dict(r) for r in state.db.execute('SELECT status,count(*) AS count,min(created) AS oldest,max(attempts) AS max_attempts FROM outbox GROUP BY status')],
                          'candidates': [dict(r) for r in state.db.execute('SELECT domain,status,reason,next_inspection,good_runs,graph_depth,qualified_observations,last_qualified,bad_runs,metrics FROM candidates')],
                          'endpoint_count': state.db.execute('SELECT count(*) FROM candidate_endpoints').fetchone()[0],
                          'delivery_totals': dict(state.db.execute("SELECT key,value FROM metadata WHERE key LIKE 'outbox_%'"))}, indent=2))
        state.close()
        return
    if args.health:
        state = State(state_path)
        row = state.db.execute("SELECT value FROM metadata WHERE key='heartbeat'").fetchone()
        state.close()
        raise SystemExit(0 if row and time.time() - float(row[0]) < int(os.getenv("CRAWLER_JOB_TIMEOUT", "900")) + 180 else 1)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    try:
        with FileLock(state_path + ".lock", timeout=0):
            state = State(state_path)
            api_url = os.getenv("API_BASE_URL", "http://localhost:8000")
            ingestion_token = os.getenv("INGESTION_API_KEY", "")
            with state.db:
                state.db.execute("UPDATE runs SET finished=?,success=0,error='worker restarted before completion' WHERE finished IS NULL", (time.time(),))
            for seed in ACTIVE_SOURCES:
                override = int(os.getenv('CRAWLER_INTERVAL_MINUTES', '0'))
                if override > 0:
                    seed = replace(seed, crawl_frequency_minutes=max(15, override))
                state.seed(seed)
            try:
                while not stop.is_set():
                    with state.db:
                        state.db.execute("INSERT OR REPLACE INTO metadata VALUES('heartbeat',?)", (str(time.time()),))
                    deliver(state, api_url, ingestion_token)
                    sync_runtime_config(state, api_url, ingestion_token)
                    discovery_cycle(state, api_url, ingestion_token, limit=1)
                    # --once holds a finite snapshot even when early failures
                    # become due again during later, slower source jobs.
                    due_sources = state.due()
                    for row in (due_sources if args.once else due_sources[:1]):
                        if stop.is_set():
                            break
                        run_source(state, SourceSeed(**json.loads(row['seed'])), api_url, ingestion_token)
                        with state.db:
                            state.db.execute("INSERT OR REPLACE INTO metadata VALUES('heartbeat',?)", (str(time.time()),))
                        if args.once:
                            discovery_cycle(state, api_url, ingestion_token, limit=1)
                    deliver(state, api_url, ingestion_token)
                    try:
                        response = requests.post(api_url.rstrip('/') + '/events/maintenance',
                                                 headers={'X-Ingestion-Key': ingestion_token}, timeout=20)
                        response.raise_for_status()
                    except requests.RequestException as exc:
                        log.warning('Freshness maintenance failed: %s', exc)
                    cleaned=collect_orphan_run_stats(state,state_path)
                    if cleaned:log.info('Removed %s abandoned scratch statistics files',cleaned)
                    if args.once:
                        break
                    stop.wait(30)
            finally:
                state.close()
    except Timeout:
        log.error("Another worker owns this state volume; refusing overlapping jobs")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
