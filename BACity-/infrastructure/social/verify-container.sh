#!/bin/sh
# Disposable fixture verification only; no staff accounts, platform calls or deployment.
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$TASK_ROOT"
docker build -f services/social_collector/Dockerfile -t bacity-l4-collector-verify .
docker run --rm -i --network none --read-only \
  --tmpfs /tmp:size=128m --tmpfs /home/collector:size=16m \
  --cap-drop=ALL --security-opt=no-new-privileges:true \
  --security-opt=seccomp=infrastructure/social/seccomp_profile.json \
  --memory=512m --cpus=0.5 --pids-limit=128 --shm-size=128m \
  bacity-l4-collector-verify python - <<'PY'
import asyncio,json,os
from pathlib import Path
from app.social.acquisition.browser import render
from app.social.acquisition.network import Page
assert os.getuid()!=0
assert not Path('/runner/app/social/auth.py').exists()
assert not Path('/runner/app/social/db.py').exists()
assert 'SOCIAL_DATABASE_URL' not in os.environ
assert 'SOCIAL_WORKER_KEY' not in os.environ
assert 'SCRAPINGANT_API_KEY' not in os.environ
assert 'APIFY_API_TOKEN' not in os.environ
from app.social.acquisition.apify import Client as ApifyClient
from app.social.acquisition.scrapingant import Client,parse_document
calls=[]
def fixture(url,**kwargs):
    calls.append(url)
    if url.endswith('/robots.txt'):
        return Page(url,200,b'User-agent: *\nAllow: /\n',{})
    assert url=='https://novacvernovka.eu/program/container-fixture'
    return Page(url,200,b'''<html><body><script>
      const item=document.createElement('script');item.type='application/ld+json';
      item.textContent=JSON.stringify({'@type':'MusicEvent',name:'Synthetic container concert',
        startDate:'2030-11-01T20:00:00+01:00',location:{name:'Fixture Hall'}});
      document.body.append(item);
    </script></body></html>''',{'content-type':'text/html'})
observations,received=asyncio.run(render('https://novacvernovka.eu/program/container-fixture',fetcher=fixture))
assert len(observations)==1 and len(calls)==2
print(json.dumps({'kind':'synthetic_fixture_not_live_acquisition','non_root':True,
                  'network':'none','sandbox':True,'observations_parsed':len(observations),
                  'fixture_bytes':received,'staff_or_database_modules_present':False}))
PY
