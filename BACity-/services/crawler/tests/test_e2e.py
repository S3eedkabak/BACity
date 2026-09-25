"""Real HTTP -> Scrapy -> durable queue -> FastAPI -> DB -> map, repeated twice."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests


def test_full_ingestion_roundtrip(tmp_path):
    root = Path(__file__).resolve().parents[1]
    api_dir = root.parent / 'api'
    start = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0).isoformat()
    hits = {}
    cancelled = False

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits[self.path] = hits.get(self.path, 0) + 1
            if self.path == '/robots.txt':
                body = 'User-agent: *\nDisallow: /events/blocked\n'
            elif self.path == '/events':
                body = '<a href="/about">About</a>' * 30 + '<a href="/events/jazz">Jazz</a><a href="/events/blocked">Event blocked</a><a rel="next" href="/events?page=2">Next</a>'
            elif self.path == '/events?page=2':
                body = '<a href="/events/duplicate">Jazz</a>'
            elif self.path == '/events/jazz' and hits[self.path] == 1:
                self.send_response(503)
                self.end_headers()
                return
            elif self.path in ('/events/jazz', '/events/duplicate'):
                event = {'@type': 'MusicEvent', 'name': 'Integration Jazz Concert', 'startDate': start,
                         'url': 'https://venue.example' + self.path, 'eventStatus': 'https://schema.org/EventCancelled' if cancelled else 'https://schema.org/EventScheduled',
                         'location': {'name': 'Test Jazz Venue', 'address': 'Test Street, Bratislava', 'geo': {'latitude': 48.15, 'longitude': 17.12}}}
                body = '<script type="application/ld+json">' + json.dumps(event) + '</script>'
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain' if self.path == '/robots.txt' else 'text/html')
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        api_port = sock.getsockname()[1]
    api_url = f'http://127.0.0.1:{api_port}'
    env = {**os.environ, 'DATABASE_URL': 'sqlite:///' + (tmp_path / 'events.db').as_posix(),
           'API_BASE_URL': api_url, 'INGESTION_API_KEY': 'test-ingestion-key',
           'CRAWLER_STATE_PATH': str(tmp_path / 'state.db'), 'NO_PROXY': '127.0.0.1,localhost'}
    with (tmp_path / 'api.log').open('w') as log:
        api = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(api_port)],
                               cwd=api_dir, env=env, stdout=log, stderr=log)
        try:
            for _ in range(100):
                try:
                    if requests.get(api_url + '/health', timeout=1).ok:
                        break
                except requests.RequestException:
                    pass
                time.sleep(.1)
            else:
                raise AssertionError('API did not start: ' + (tmp_path / 'api.log').read_text())
            for iteration in range(3):
                cancelled = iteration == 2
                result = subprocess.run([sys.executable, '-m', 'tests.fixture_crawl', f'http://127.0.0.1:{server.server_port}'],
                                        cwd=root, env=env, capture_output=True, text=True, timeout=60)
                assert result.returncode == 0, result.stdout + result.stderr
                events = requests.get(api_url + '/events', timeout=5).json()
                if cancelled:
                    assert events['total'] == 0
                    break
                assert events['total'] == 1
                assert len(events['items'][0]['sources']) == 2
                assert events['items'][0]['start_time'].endswith('+00:00')
                nearby = requests.get(api_url + '/events/nearby', params={'lat': 48.15, 'lng': 17.12}, timeout=5).json()
                assert len(nearby) == 1
            assert hits.get('/events/blocked', 0) == 0
            assert hits['/events/jazz'] >= 4  # includes transient 503 retry
        finally:
            api.terminate()
            api.wait(timeout=10)
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
