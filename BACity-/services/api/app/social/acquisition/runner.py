"""Single bounded worker. This image contains no staff, ORM or ingestion code."""
import argparse
import secrets
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from .adapters import ADAPTERS
from .urls import normalize_target
from .network import AccessFailure,NetworkBudget


def perform(job):
    started=time.monotonic()
    transport=NetworkBudget()
    try:
        if job['permission_expires']<=time.time():
            raise AccessFailure('permission_required','unauthorized')
        target=normalize_target(job['url'])
        if job['method']=='browser':
            from .browser import acquire_browser
            observations,received=acquire_browser(target.url,fetcher=transport)
        elif job['method']=='http':
            observations,received=ADAPTERS[target.platform].acquire(target.url,fetcher=transport)
        else:
            raise AccessFailure('unsupported','failed')
        return {'outcome':'success' if observations else 'empty','error':'none','observations':observations,
                'bytes_received':transport.received,'requests':transport.requests,'elapsed_ms':min(60000,int((time.monotonic()-started)*1000))}
    except AccessFailure as error:
        return {'outcome':error.outcome,'error':error.category,'retry_after':error.retry_after,'observations':[],
                'bytes_received':transport.received,'requests':transport.requests,'elapsed_ms':min(60000,int((time.monotonic()-started)*1000))}
    except Exception:
        return {'outcome':'failed','error':'invalid_content','observations':[]}


def gateway(path,key,*,payload=None,lease=None):
    # Fixed deployment service, never an external source or redirect target.
    base=os.environ.get('SOCIAL_WORKER_GATEWAY','http://social-gateway:8012')
    if base not in ('http://social-gateway:8012','http://127.0.0.1:8012'):
        raise RuntimeError('Untrusted worker gateway')
    headers={'Content-Type':'application/json','X-Social-Worker-Key':key}
    if lease:
        headers['X-Social-Lease']=lease
    request=urllib.request.Request(base+path,data=json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode() if payload is not None else None,headers=headers)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args):
            return None
    with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()).open(request,timeout=10) as response:
        value=response.read(65537)
        if len(value)>65536:
            raise RuntimeError('Gateway response too large')
        return json.loads(value)


def bounded(job,key):
    # Secrets remain in parent only. The acquisition child receives just the target.
    env={k:v for k,v in os.environ.items() if k in ('PATH','PYTHONPATH','HOME','PLAYWRIGHT_BROWSERS_PATH','SOCIAL_EGRESS_PROXY','LANG')}
    import tempfile
    import signal
    with tempfile.TemporaryFile(mode='w+t') as output_file:
        process=None
        try:
            process=subprocess.Popen([sys.executable,'-m','app.social.acquisition.runner','--job'],stdin=subprocess.PIPE,stdout=output_file,
                stderr=subprocess.DEVNULL,text=True,env=env,start_new_session=True)
            try:
                process.stdin.write(json.dumps({k:v for k,v in job.items() if k!='lease'}))
                process.stdin.close()
            except BrokenPipeError:
                pass
            process.stdin=None
            deadline=time.monotonic()+40
            while process.poll() is None:
                if time.monotonic()>deadline:
                    raise TimeoutError()
                try:
                    active=gateway('/jobs/'+job['id']+'/active',key,lease=job['lease'])['active']
                except urllib.error.HTTPError as error:
                    if error.code<500:raise
                    active=True # Finish this already-authorized bounded child; buffer output.
                except urllib.error.URLError:active=True
                if not active:
                    return {'outcome':'failed','error':'access_denied','observations':[]}
                time.sleep(1)
            output_file.seek(0)
            output=output_file.read(65537)
            if process.returncode or len(output)>65536:
                return {'outcome':'failed','error':'invalid_content','observations':[]}
            return json.loads(output)
        except TimeoutError:
            return {'outcome':'failed','error':'timeout','observations':[]}
        except OSError:
            return {'outcome':'failed','error':'resource_limit','observations':[]}
        finally:
            if process:
                try:
                    os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)



def provider_collect(job,key):
    from .scrapingant import Client,collect,ProviderFailure
    if os.environ.get('SCRAPINGANT_ENABLED','false').lower() not in ('true','1') or not os.environ.get('SCRAPINGANT_API_KEY'):
        return {'outcome':'failed','error':'provider_not_configured','observations':[]}
    def quota(action,payload):
        try:
            if action=='status':
                return gateway('/jobs/'+job['id']+'/provider/status',key,lease=job['lease'])
            return gateway('/jobs/'+job['id']+'/provider/'+action,key,payload={**payload,'lease':job['lease']})
        except urllib.error.HTTPError as exc:
            # Allow only fixed quota categories. Never log provider/key-bearing text.
            category='usage_unverified'
            try:
                value=json.loads(exc.read(4096)).get('detail')
                if value in ('budget_exhausted','provider_request_in_flight','provider_job_request_limit','provider_request_already_reserved','provider_cost_exceeded_reservation','provider_disabled','provider_not_configured'):
                    category='provider_not_configured' if value=='provider_disabled' else value
            except (ValueError,TypeError):pass
            raise ProviderFailure(category) from None
        except (urllib.error.URLError,ValueError,RuntimeError):
            raise ProviderFailure('network_error') from None
    try:
        return collect(job,Client(os.environ['SCRAPINGANT_API_KEY']),quota)
    except ProviderFailure as exc:
        return {'outcome':'failed','error':exc.category,'observations':[]}


def apify_cycle(key,owner):
    if not os.environ.get('APIFY_API_TOKEN'):
        return False
    from .apify import Client
    from .apify_worker import step
    from .scrapingant import ProviderFailure
    batch=gateway('/apify/lease',key,payload={'owner':owner,'cleanup_only':os.environ.get('APIFY_ENABLED','false').lower() not in ('true','1')})['run']
    if not batch:return False
    def call(action,payload):
        try:
            # gateway's default GET is distinct from a JSON-null POST finish.
            return gateway('/apify/runs/'+batch['id']+'/'+action,key,payload=payload if payload is not None else {},lease=owner)
        except urllib.error.HTTPError as exc:
            category='invalid_content'
            try:
                detail=json.loads(exc.read(4096)).get('detail')
                if detail in ('budget_exhausted','billing_unverified'):category=detail
            except (ValueError,TypeError):pass
            raise ProviderFailure(category) from None
        except (urllib.error.URLError,ValueError,RuntimeError):raise ProviderFailure('network_error') from None
    try:step(batch,Client(os.environ['APIFY_API_TOKEN']),call)
    except ProviderFailure:
        # Durable intent/charge reservation survives lost gateway acknowledgements.
        print('Apify phase paused; durable state retained',file=sys.stderr)
    return True


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--job',action='store_true'); parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    if args.job:
        payload=sys.stdin.read(65537)
        if len(payload)>65536:
            raise SystemExit(2)
        print(json.dumps(perform(json.loads(payload)),ensure_ascii=False))
        return
    key=os.environ.get('SOCIAL_WORKER_KEY','')
    if len(key)<32:
        raise SystemExit('Configure a separate worker credential')
    from .durable_runner import run
    run(key,args.once)

if __name__=='__main__':
    main()
