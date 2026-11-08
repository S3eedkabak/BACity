"""One bounded phase per loop; durable progress is owned by the existing gateway."""
import time
from .apify import Client,ACTOR_ID,TERMINAL,money,normalize_record
from .scrapingant import ProviderFailure


def run_progress(value,expected=None):
    import re
    if not isinstance(value,dict) or value.get('actId')!=ACTOR_ID or not re.fullmatch(r'[A-Za-z0-9]{1,32}',str(value.get('id',''))):
        raise ProviderFailure('invalid_content')
    if expected and value['id']!=expected:raise ProviderFailure('invalid_content')
    status=value.get('status')
    if status not in TERMINAL|{'READY','RUNNING','ABORTING','TIMING-OUT'}:raise ProviderFailure('invalid_content')
    return {'run_id':value['id'],'status':status,'dataset_id':value.get('defaultDatasetId'),
        'cost':money(value['usageTotalUsd']) if status in TERMINAL and value.get('usageTotalUsd') is not None else None}


def step(batch,client,call):
    """call(action,payload) is lease-authenticated and never starts a remote run."""
    started=time.monotonic();state=batch['state'];launched_here=False
    try:
        if batch.get('next_poll',0)>time.time():return
        if batch.get('cancel_requested'):
            if batch.get('run_id'):
                if batch.get('provider_status')!='ABORTING':
                    call('progress',{'run_id':batch['run_id'],'status':'ABORTING','dataset_id':batch.get('dataset_id')})
                    client.abort(batch['run_id'])
                value=run_progress(client.run(batch['run_id']),batch['run_id'])
                call('progress',value)
                if value['status'] not in TERMINAL or value['status']!='SUCCEEDED':return
            call('finish',{'error':'cancelled'});return
        if state=='planned':
            call('sync',client.preflight())
            batch=call('reserve',{});state=batch['state']
        if state=='reserved':
            batch=call('dispatch',{});state='dispatching';launched_here=True
            response=client.launch(batch['actor_input'],batch['actor_cap'],batch['build'])
            batch=call('progress',run_progress(response));state=batch['state']
        elif state=='dispatching' and not batch.get('run_id'):
            # The prior process may have submitted POST. Never repeat a billable launch.
            call('finish',{'error':'launch_uncertain'});return
        if state=='running':
            value=run_progress(client.run(batch['run_id']),batch['run_id'])
            if value['status'] not in TERMINAL and time.time()-batch['created']>900:
                client.abort(batch['run_id']);call('finish',{'error':'timeout'});return
            batch=call('progress',value);state=batch['state']
        if state=='dataset':
            if batch['total'] is None:
                metadata=client.dataset(batch['dataset_id']);total=metadata.get('itemCount')
                if type(total) is not int or not 0<=total<=80:raise ProviderFailure('invalid_content')
                batch=call('progress',{'run_id':batch['run_id'],'dataset_id':batch['dataset_id'],'status':'SUCCEEDED','total':total})
            for _ in range(4):
                if batch['offset']==batch['total']:
                    call('finish',None);return
                if time.monotonic()-started>40:return
                raw=client.page(batch['dataset_id'],batch['offset'])
                if not isinstance(raw,list) or len(raw)>5 or not raw:raise ProviderFailure('invalid_content')
                records=[]
                for value in raw:
                    job_id,content,error=normalize_record(value,batch['members'])
                    records.append({'job_id':job_id,'content':content,'error':error})
                ack=call('page',{'offset':batch['offset'],'count':len(raw),'records':records})
                batch['offset']=ack['offset']
            if batch['offset']==batch['total']:call('finish',None)
    except (KeyError,TypeError,ValueError):
        call('finish',{'error':'invalid_content'})
    except ProviderFailure as error:
        if state=='dispatching' or launched_here and not batch.get('run_id'):
            # Includes ambiguous transport/5xx launch failures. Keep the full charge.
            call('finish',{'error':'launch_uncertain'});return
        if state in ('running','dataset') and error.category in ('network_error','provider_transient','rate_limit'):
            call('defer',{'retry_after':max(30,error.retry_after),'error':error.category});return
        category=error.category if error.category in ('billing_unverified','budget_exhausted','network_error','provider_auth','provider_denied','rate_limit','provider_transient','response_limit','timeout','invalid_content') else 'invalid_content'
        call('finish',{'error':category,'retry_after':error.retry_after})
