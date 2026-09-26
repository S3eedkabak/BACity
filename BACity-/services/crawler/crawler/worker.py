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


def deliver(state, api_url, token="", limit=500):
    """Keep failed submissions on disk, including across process restarts."""
    delivered = 0
    headers = {"X-Ingestion-Key": token} if token else {}
    for row in state.db.execute("SELECT * FROM outbox WHERE status='pending' AND next_try<=? ORDER BY created LIMIT ?", (time.time(), limit)).fetchall():
        try:
            response = requests.post(f"{api_url.rstrip('/')}/events", json=json.loads(row['payload']), headers=headers, timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            status = exc.response.status_code if exc.response is not None else 0
            permanent = status in (400, 404, 413, 422)
            with state.db:
                state.db.execute("UPDATE outbox SET attempts=attempts+1,error=?,status=?,next_try=? WHERE key=?",
                                 (str(exc), 'rejected' if permanent else 'pending', time.time() + min(3600, 30 * 2 ** min(row['attempts'], 7)), row['key']))
            log.error("Event delivery failed: %s", exc)
            if permanent:
                continue
            # Back off for unavailable API instead of spending minutes on every queued item.
            break
        else:
            with state.db:
                state.db.execute("DELETE FROM outbox WHERE key=?", (row['key'],))
            delivered += 1
    return delivered


def _safe_stats(stats):
    reasons = {key.rsplit('/', 1)[-1]: int(value) for key, value in stats.items()
               if key.startswith('validation/rejected/') and isinstance(value, (int, float))}
    pages = int(stats.get('response_received_count', 0))
    items = int(stats.get('item_scraped_count', 0))
    rejected = int(stats.get('validation/rejected', 0))
    errors = int(stats.get('extraction/errors', 0)) + int(stats.get('source/request_errors', 0))
    return pages, items, items, rejected, errors, dict(list(reasons.items())[:20])


def report_run(api_url, token, seed, started, finished, success, stats, error):
    pages, items, accepted, rejected, extraction_errors, reasons = _safe_stats(stats)
    status = 'healthy' if success and accepted else 'empty' if success else 'timed_out' if error and 'timeout' in error else 'failed'
    body = {'name': seed.name, 'domain': seed.domain, 'base_url': seed.base_url, 'event_url': seed.event_url,
            'source_type': seed.source_type, 'language': seed.language, 'parser': seed.parser,
            'reliability_score': seed.reliability_score, 'requires_js': seed.requires_js,
            'crawl_frequency_minutes': seed.crawl_frequency_minutes,
            'started_at': datetime.fromtimestamp(started, timezone.utc).isoformat(),
            'finished_at': datetime.fromtimestamp(finished, timezone.utc).isoformat(), 'success': success,
            'status': status, 'pages_processed': pages, 'items_processed': items,
            'accepted_events': accepted, 'rejected_events': rejected, 'extraction_errors': extraction_errors,
            'skip_reasons': reasons, 'error': (error or '')[:2000] or None}
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


def run_source(state, seed, api_url=None, token=""):
    run_id = state.begin(seed.domain)
    started = state.db.execute("SELECT started FROM runs WHERE id=?", (run_id,)).fetchone()[0]
    stats_path = Path(os.getenv("CRAWLER_STATE_PATH", "crawler-state/state.db")).parent / f"run-{run_id}.json"
    command = [sys.executable, "-m", "crawler.run", "--source", json.dumps(seed.__dict__), "--stats", str(stats_path)]
    error = None
    stats = {}
    process = subprocess.Popen(command)
    deadline = time.monotonic() + int(os.getenv("CRAWLER_JOB_TIMEOUT", "900"))
    while process.poll() is None:
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
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        stats_path.unlink()
    success = process.returncode == 0 and stats.get("success", False)
    failures = state.finish(run_id, seed, success, stats, error or stats.get("error"))
    log.info("CRAWL_RESULT source=%s success=%s stats=%s", seed.domain, success, stats)
    if failures >= 3:
        log.error("CRAWLER_ALERT repeated_failure source=%s failures=%s", seed.domain, failures)
    if api_url:
        try:
            report_run(api_url, token, seed, started, time.time(), success, stats, error or stats.get("error"))
        except requests.RequestException as exc:
            log.warning("Could not publish source health for %s: %s", seed.domain, exc)
    return success


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
                          'delivery': [dict(r) for r in state.db.execute('SELECT status,count(*) AS count FROM outbox GROUP BY status')]}, indent=2))
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
                    for row in state.due():
                        if stop.is_set():
                            break
                        run_source(state, SourceSeed(**json.loads(row['seed'])), api_url, ingestion_token)
                        with state.db:
                            state.db.execute("INSERT OR REPLACE INTO metadata VALUES('heartbeat',?)", (str(time.time()),))
                    deliver(state, api_url, ingestion_token)
                    try:
                        response = requests.post(api_url.rstrip('/') + '/events/maintenance',
                                                 headers={'X-Ingestion-Key': ingestion_token}, timeout=20)
                        response.raise_for_status()
                    except requests.RequestException as exc:
                        log.warning('Freshness maintenance failed: %s', exc)
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
