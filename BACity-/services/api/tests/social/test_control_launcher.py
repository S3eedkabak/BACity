"""Launcher selection must be identical for start/stop; owner jobs stay one-off."""
import json
import os
from pathlib import Path
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[4]


@pytest.fixture
def launcher(tmp_path):
    fake=tmp_path/'docker'
    fake.write_text('#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n')
    fake.chmod(0o700)
    env=dict(os.environ,PATH=str(tmp_path)+os.pathsep+os.environ['PATH'])
    for key in ('BACITY_APP_ENV_FILE','BACITY_SOCIAL_ENV_FILE','BACITY_RUNTIME_OVERRIDE_FILE'):
        file=tmp_path/key;file.write_text('');env[key]=str(file)
    def call(*args):
        r=subprocess.run([str(ROOT/'control'),*args],env=env,cwd=tmp_path,text=True,capture_output=True)
        assert r.returncode==0,r.stderr
        return [json.loads(line) for line in r.stdout.splitlines()]
    return call


def test_start_stop_use_identical_manifests_environment_and_profiles(launcher):
    start=launcher('up','-d','postgres','social-admin','social-proxy')[0]
    stop=launcher('stop','api','worker','maintenance')[0]
    down=launcher('down')[0]
    assert start[:start.index('up')]==stop[:stop.index('stop')]==down[:-1]
    assert start.count('--env-file')==2 and start.count('-f')==4
    assert 'social-retention' in start and 'social' in start
    assert start[start.index('-f')+1]==str(ROOT/'docker-compose.yml')


def test_owner_repair_does_not_start_or_reconfigure_dependencies(launcher):
    command=launcher('owner-run','python','-m','app.social.reconcile_candidates')[0]
    assert command.count('--env-file')==1 and command.count('-f')==1
    assert command[command.index('run'):]==['run','--rm','--no-deps','-T','api','python','-m','app.social.reconcile_candidates']


@pytest.mark.parametrize('group,services',[
    ('main',['postgres','redis','opensearch','api','worker','maintenance']),
    ('panel',['postgres','social-admin','social-proxy','social-gateway','social-collector','social-egress','social-retention']),
])
def test_named_starts_build_detach_and_select_only_the_requested_group(launcher,group,services):
    named=launcher('up',group)
    direct=launcher('up','-d','--build',*services)
    assert len(named)==2 and named[0]==direct[0]
    assert named[0][named[0].index('up'):]==['up','-d','--build',*services]
    assert named[1][named[1].index('logs'):]==['logs','--follow','--tail','100',*services]
    assert named[0][:named[0].index('up')]==named[1][:named[1].index('logs')]


def test_both_named_starts_keep_the_same_database_configuration(launcher):
    main=launcher('up','main')[0];panel=launcher('up','panel')[0]
    assert main[:main.index('up')]==panel[:panel.index('up')]
    assert 'down' not in main+panel and '--remove-orphans' not in main+panel


def test_dry_run_does_not_attach_to_real_logs(launcher):
    calls=launcher('up','main','--dry-run')
    assert len(calls)==1 and 'up' in calls[0] and '--dry-run' in calls[0]


@pytest.mark.parametrize('group,services',[
    ('main',['worker','maintenance','api','opensearch','redis']),
    ('panel',['social-collector','social-gateway','social-retention','social-admin','social-proxy','social-egress']),
])
def test_named_down_only_stops_its_own_services_and_keeps_shared_database(launcher,group,services):
    calls=launcher('down',group)
    assert len(calls)==1
    command=calls[0]
    assert command[command.index('stop'):]==['stop',*services]
    assert 'postgres' not in command and 'down' not in command


@pytest.mark.parametrize('group,services',[
    ('main',['worker','maintenance','api','opensearch','redis']),
    ('panel',['social-collector','social-gateway','social-retention','social-admin','social-proxy','social-egress']),
])
def test_prune_only_stops_and_removes_selected_containers(launcher,group,services):
    calls=launcher('prune',group)
    assert len(calls)==2
    assert calls[0][calls[0].index('stop'):]==['stop',*services]
    assert calls[1][calls[1].index('rm'):]==['rm','-f',*services]
    assert calls[0][:calls[0].index('stop')]==calls[1][:calls[1].index('rm')]
    for command in calls:
        assert not set(command)&{'postgres','down','--volumes','--rmi','--remove-orphans','system','prune'}


@pytest.mark.parametrize('args',[
    ('prune',),('prune','unknown'),('prune','main','--volumes'),('prune','panel','--rmi','all'),
])
def test_prune_rejects_unknown_targets_and_scope_expanding_flags(launcher,args):
    with pytest.raises(AssertionError,match='Usage: ./control prune'):
        launcher(*args)


@pytest.mark.parametrize('operation,verb',[(('up','main'),'up'),(('prune','panel'),'stop')])
def test_failed_first_step_does_not_run_logs_or_remove_containers(tmp_path,operation,verb):
    fake=tmp_path/'docker'
    fake.write_text('#!/bin/sh\ncase " $* " in *" '+verb+' "*) exit 7;; *) exit 99;; esac\n')
    fake.chmod(0o700)
    env=dict(os.environ,PATH=str(tmp_path)+os.pathsep+os.environ['PATH'])
    for key in ('BACITY_APP_ENV_FILE','BACITY_SOCIAL_ENV_FILE','BACITY_RUNTIME_OVERRIDE_FILE'):
        file=tmp_path/key;file.write_text('');env[key]=str(file)
    result=subprocess.run([str(ROOT/'control'),*operation],env=env,text=True,capture_output=True)
    assert result.returncode==7


def test_interrupting_logs_never_sends_a_stop_or_down_command(tmp_path):
    import signal
    import time
    fake=tmp_path/'docker';record=tmp_path/'calls';ready=tmp_path/'ready'
    fake.write_text('''#!/usr/bin/env python3
import json,os,pathlib,signal,sys,time
with pathlib.Path(os.environ['LAUNCHER_TEST_CALLS']).open('a') as f:
    f.write(json.dumps(sys.argv[1:])+'\\n')
if 'logs' in sys.argv:
    signal.signal(signal.SIGINT,lambda *_:sys.exit(130))
    pathlib.Path(os.environ['LAUNCHER_TEST_READY']).touch()
    while True:time.sleep(1)
''');fake.chmod(0o700)
    env=dict(os.environ,PATH=str(tmp_path)+os.pathsep+os.environ['PATH'],LAUNCHER_TEST_CALLS=str(record),LAUNCHER_TEST_READY=str(ready))
    for key in ('BACITY_APP_ENV_FILE','BACITY_SOCIAL_ENV_FILE','BACITY_RUNTIME_OVERRIDE_FILE'):
        file=tmp_path/key;file.write_text('');env[key]=str(file)
    process=subprocess.Popen([str(ROOT/'control'),'up','main'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+5
        while not ready.exists() and process.poll() is None and time.monotonic()<deadline:time.sleep(.02)
        assert ready.exists()
        process.send_signal(signal.SIGINT)
        assert process.wait(timeout=5)==130
        calls=[json.loads(line) for line in record.read_text().splitlines()]
        assert len(calls)==2 and 'up' in calls[0] and 'logs' in calls[1]
        assert not any('stop' in call or 'down' in call for call in calls)
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=5)
