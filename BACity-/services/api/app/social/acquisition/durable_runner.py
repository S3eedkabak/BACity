"""Independent capture journal + ordered, transactional delivery to the gateway."""
import copy
import hashlib
import json
import os
import sys
import sqlite3
import time
import urllib.error
import uuid
from .outbox import Outbox,OutboxUnavailable,encoded
from .scrapingant import ProviderFailure


def send_with(key):
    from .runner import gateway
    def send(path,*,payload=None,lease=None):
        return gateway(path,key,payload=payload,lease=lease)
    return send


def renew(box,send,data,**extra):
    job=data['batch'] if data['kind']=='apify' else data['job']
    owner=box.owner if data['kind']=='apify' else job['lease']
    return send('/outbox/renew',payload={'kind':data['kind'],'identity':job['id'],'owner':owner,**extra})

class DurableApifyClient:
    def __init__(self,box,send,client):self.box,self.send,self.client=box,send,client
    def __getattr__(self,key):return getattr(self.client,key)
    def preflight(self):
        identity,data=self.box.load()
        if 'preflight' not in data:data['preflight']=self.client.preflight();self.box.save(data)
        return data['preflight']
    def launch(self,*args):
        identity,data=self.box.load()
        if 'launch_response' in data:return data['launch_response']
        if data.get('launch_intent'):raise ProviderFailure('network_error') # Ambiguous POST; never repeat.
        renew(self.box,self.send,data) # Fresh approval/budget ownership, never a cached offline grant.
        self.box.capacity();data['launch_intent']=True;self.box.save(data)
        value=self.client.launch(*args)
        identity,data=self.box.load();data['launch_response']=value;self.box.save(data)
        return value


def apify_phase(box,send,client):
    from .apify_worker import step,run_progress
    identity,data=box.load()
    def call(action,payload):
        _,current=box.load();batch=current['batch']
        if action in ('sync','reserve','dispatch'):
            result=box.online(send,'apify:'+action,batch['id'],box.owner,payload,'prepare:'+action)
            if result.get('rejected'):raise ProviderFailure(result['rejected'])
            _,current=box.load()
            if action!='sync':current['batch']=result;box.save(current)
            return result
        after=copy.deepcopy(current);b=after['batch']
        if action=='progress':
            b.update(run_id=payload['run_id'],provider_status=payload['status'])
            if payload.get('dataset_id'):b['dataset_id']=payload['dataset_id']
            if payload['status']=='SUCCEEDED':
                b['state']='dataset'
                if payload.get('total') is not None:b['total']=payload['total'];b['dataset_done']=b['offset']==b['total']
            elif payload['status'] in ('FAILED','TIMED-OUT','ABORTED'):b['state']='failed';after['done']=True
            else:b['state']='running'
            result=b
        elif action=='page':
            b['offset']=payload['offset']+payload['count'];b['dataset_done']=b['offset']==b['total']
            result={'offset':b['offset'],'done':b['dataset_done']}
        elif action=='finish':after['done']=True;b['state']='finished';result={'state':'finished'}
        elif action=='defer':b['next_poll']=time.time()+payload['retry_after'];result={'deferred_until':b['next_poll']}
        else:raise OutboxUnavailable('Unsupported buffered phase')
        box.message('apify:'+action,b['id'],box.owner,payload,data_after=after)
        return result
    if data['batch']['state']=='dispatching' and data.get('launch_response'):
        call('progress',run_progress(data['launch_response']));_,data=box.load()
    # A restart after dispatch ACK but before POST is an ambiguous launch too;
    # fail closed. Known responses resume by run ID without another POST.
    step(data['batch'],DurableApifyClient(box,send,client),call)


class DurableScrapingClient:
    def __init__(self,box,send,client):self.box,self.send,self.client=box,send,client;self.bytes=0
    def request(self,kind,target=None):
        key=hashlib.sha256(encoded([kind,target]).encode()).hexdigest()
        _,data=self.box.load();saved=data.setdefault('responses',{}).get(key)
        if saved:
            if saved.get('error'):
                error=ProviderFailure(saved['error'],saved.get('retry_after',0));error.cost=saved.get('cost');raise error
            return saved['value'],saved['cost']
        if key in data.setdefault('request_intents',[]):
            error=ProviderFailure('network_error');error.cost=None;raise error
        renew(self.box,self.send,data,request_id=data.get('last_request_id'),request_kind=kind);self.box.capacity();data['request_intents'].append(key);self.box.save(data)
        try:value,cost=self.client.request(kind,target);saved={'value':value,'cost':cost}
        except ProviderFailure as error:
            saved={'error':error.category,'retry_after':error.retry_after,'cost':getattr(error,'cost',None)}
            _,data=self.box.load();data.setdefault('responses',{})[key]=saved;self.box.save(data);raise
        _,data=self.box.load();data.setdefault('responses',{})[key]=saved;self.box.save(data);self.bytes=self.client.bytes
        return value,cost


def legacy_phase(box,send,key,scraping_client=None):
    from .runner import bounded
    from .scrapingant import Client,collect
    work_id,data=box.load();job=data['job']
    if 'result' in data:
        result=data['result'] # Captured content must survive an enqueue failure.
    elif job['method']=='scrapingant':
        index=0
        def request_id():
            nonlocal index
            index+=1;return str(uuid.uuid5(uuid.UUID(work_id),'request:'+str(index)))
        def quota(action,payload):
            _,current=box.load()
            if action=='status':
                if 'quota_status' not in current:
                    current['quota_status']=send('/jobs/'+job['id']+'/provider/status',lease=job['lease']);box.save(current)
                return current['quota_status']
            if action=='reserve':
                result=box.online(send,'legacy:reserve',job['id'],job['lease'],payload,'reserve:'+payload['request_id'])
                if result.get('rejected'):raise ProviderFailure(result['rejected'])
                _,current=box.load();current['last_request_id']=payload['request_id'];box.save(current)
                return result
            if action=='settle':
                box.message('legacy:settle',job['id'],job['lease'],payload,stable='settle:'+payload['request_id'])
                return {'cost':payload.get('cost') if payload.get('cost') is not None else 125,'cost_kind':'reported' if payload.get('cost') is not None else 'estimated'}
            raise OutboxUnavailable('Unsupported quota action')
        result=collect(job,DurableScrapingClient(box,send,scraping_client or Client(os.environ.get('SCRAPINGANT_API_KEY',''))),quota,request_id_factory=request_id)
    else:
        if data.get('started'):
            result={'outcome':'failed','error':'worker_timeout','observations':[]}
        else:
            renew(box,send,data);data['started']=True;box.save(data)
            result=bounded(job,key)
    _,current=box.load();current['result']=result;box.save(current)
    current['done']=True
    box.message('legacy:complete',job['id'],job['lease'],result,data_after=current)


def cycle(box,send,key,*,apify_client=None,scraping_client=None,media_capture=None):
    # Known remote work can finish capture even while earlier gateway messages
    # are unavailable. Deliveries are ordered and always drain before new work.
    identity,data=box.load()
    box.last_kind=data.get('kind') if data else None
    if data:
        if not data.get('done'):
            if data['kind']=='apify':
                try:
                    state=send('/outbox/state',payload={'kind':'apify','identity':data['batch']['id'],'owner':box.owner})
                    data['batch']['cancel_requested']=state['cancel_requested'];box.save(data)
                except urllib.error.HTTPError as error:
                    if error.code<500:raise
                except urllib.error.URLError:pass # Capture known work despite database downtime.
                from .apify import Client
                apify_phase(box,send,apify_client or Client(os.environ.get('APIFY_API_TOKEN','')))
            elif data['kind']=='media':
                if 'result' not in data:
                    from .poster import bounded
                    data['result']=(media_capture or bounded)(data['image']['url']);box.save(data)
                after=copy.deepcopy(data);after['done']=True
                box.message('media:complete',data['image']['id'],box.owner,data['result'],data_after=after)
            else:legacy_phase(box,send,key,scraping_client)
        box.flush(send)
        _,current=box.load()
        if current.get('done'):box.clear()
        return True
    box.capacity()
    if os.environ.get('APIFY_API_TOKEN'):
        result=send('/apify/lease',payload={'owner':box.owner,'cleanup_only':os.environ.get('APIFY_ENABLED','false').lower() not in ('true','1')})
        if result['run']:
            box.save({'kind':'apify','batch':result['run']});return cycle(box,send,key,apify_client=apify_client,scraping_client=scraping_client)
    try:result=send('/lease',payload={})
    except urllib.error.HTTPError as error:
        # Processing images already collected does not enable new source jobs.
        if error.code!=503 or os.environ.get('SOCIAL_MEDIA_ENABLED','false').lower() not in ('true','1'):raise
        result={'job':None}
    if result['job']:
        box.save({'kind':'legacy','job':result['job']});return cycle(box,send,key,apify_client=apify_client,scraping_client=scraping_client)
    if os.environ.get('SOCIAL_MEDIA_ENABLED','false').lower() in ('true','1'):
        result=send('/media/lease',payload={'owner':box.owner})
        if result['image']:
            box.save({'kind':'media','image':result['image']})
            return cycle(box,send,key,media_capture=media_capture)
    return False


def run(key,once=False):
    path=os.environ.get('SOCIAL_OUTBOX_PATH',os.path.expanduser('~/.local/share/bacity/outbox.sqlite3'))
    box=Outbox(path);send=send_with(key)
    try:
        while True:
            try:cycle(box,send,key)
            except (urllib.error.URLError,ValueError,RuntimeError,OSError,sqlite3.Error):
                print('Social delivery paused; local outbox retained. Inspect outbox status and service health.',file=sys.stderr)
                if once:return
            if once:return
            time.sleep(3 if getattr(box,'last_kind',None)=='media' else 30)
    finally:box.close()
