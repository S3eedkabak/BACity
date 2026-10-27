import os
import subprocess
import sys
from unittest.mock import Mock
from app.social.acquisition.runner import bounded


def test_real_acquisition_child_is_killed_on_cancel_and_receives_no_secrets(monkeypatch):
    real_popen=subprocess.Popen
    processes=[]
    def launch(argv,**kwargs):
        assert 'SOCIAL_WORKER_KEY' not in kwargs['env']
        assert 'SOCIAL_DATABASE_URL' not in kwargs['env']
        assert 'INGESTION_API_KEY' not in kwargs['env']
        p=real_popen([sys.executable,'-c','import time;time.sleep(30)'],**kwargs)
        processes.append(p);return p
    monkeypatch.setenv('SOCIAL_DATABASE_URL','secret-do-not-inherit')
    monkeypatch.setenv('SOCIAL_WORKER_KEY','secret-do-not-inherit')
    monkeypatch.setenv('INGESTION_API_KEY','secret-do-not-inherit')
    monkeypatch.setattr('app.social.acquisition.runner.subprocess.Popen',launch)
    monkeypatch.setattr('app.social.acquisition.runner.gateway',lambda *a,**kw:{'active':False})
    result=bounded({'id':'fixture-job','lease':'fixture-lease'},'parent-only-secret')
    assert result['error']=='access_denied'
    assert processes[0].poll() is not None


def test_worker_process_crash_does_not_publish_or_call_existing_worker(monkeypatch):
    real_popen=subprocess.Popen
    def launch(argv,**kwargs):
        return real_popen([sys.executable,'-c','raise SystemExit(9)'],**kwargs)
    monkeypatch.setattr('app.social.acquisition.runner.subprocess.Popen',launch)
    monkeypatch.setattr('app.social.acquisition.runner.gateway',lambda *a,**kw:{'active':True})
    result=bounded({'id':'fixture-job','lease':'fixture-lease'},'parent-only-secret')
    assert result['outcome']=='failed' and result['error']=='invalid_content'


def test_process_resource_exhaustion_is_a_bounded_classified_failure(monkeypatch):
    def exhausted(*a,**kw):raise OSError('process limit')
    monkeypatch.setattr('app.social.acquisition.runner.subprocess.Popen',exhausted)
    result=bounded({'id':'fixture-job','lease':'fixture-lease'},'parent-only-secret')
    assert result['outcome']=='failed' and result['error']=='resource_limit'


def test_actual_runner_module_spawns_and_returns_a_classified_result(monkeypatch):
    # Exercises the real -m child invocation used when the parent itself runs with -m.
    from pathlib import Path
    monkeypatch.setenv('PYTHONPATH',str(Path(__file__).resolve().parents[2]))
    monkeypatch.setattr('app.social.acquisition.runner.gateway',lambda *a,**kw:{'active':True})
    result=bounded({'id':'fixture-job','lease':'fixture-lease','url':'https://www.instagram.com/p/ABC123/',
                    'permission_expires':0,'method':'http'},'parent-only-secret')
    assert result['outcome']=='unauthorized' and result['error']=='permission_required'
