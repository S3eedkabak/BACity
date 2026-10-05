from unittest.mock import Mock

import pytest
import requests
from crawler.discovery import candidate_url
from crawler.state import State
from crawler.worker import discovery_cycle


@pytest.mark.parametrize('url', ['https://tiktok.com/@hall', 'https://m.facebook.com/event',
    'https://instagram.com/p/poster', 'https://instagram.com./p/poster', 'https://youtu.be/123'])
def test_social_discovery_is_disabled_even_with_config_override(monkeypatch, url):
    monkeypatch.setenv('CRAWLER_BLOCK_DOMAINS', '')
    with pytest.raises(ValueError):
        candidate_url(url)


@pytest.mark.parametrize('learning_fails', [False, True])
def test_existing_worker_drains_learning_without_blocking_candidate_cycle(tmp_path, monkeypatch, learning_fails):
    state = State(str(tmp_path / 'worker.db'))
    calls = []
    def post(url, **kwargs):
        calls.append(url)
        if learning_fails and url.endswith('/learning/process'):
            raise requests.ConnectionError('API unavailable')
        return Mock(raise_for_status=lambda: None)
    get = Mock(return_value=Mock(raise_for_status=lambda: None, json=lambda: []))
    monkeypatch.setattr(requests, 'post', post)
    monkeypatch.setattr(requests, 'get', get)
    discovery_cycle(state, 'http://api:8000', 'worker-key')
    assert calls == ['http://api:8000/crawler/learning/process', 'http://api:8000/crawler/candidates/report']
    assert get.call_args.args[0].endswith('/candidates/runtime')
    state.close()
