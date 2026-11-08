import asyncio
import json
import socket
from unittest.mock import Mock
import pytest
from app.social.acquisition.urls import normalize_target
from app.social.acquisition.network import (Page,AccessFailure,public_addresses,checked_url,robots_allowed,fetch_document,fetch)
from app.social.acquisition.adapters import ADAPTERS
from app.social.acquisition.runner import perform


def test_dns_rebinding_and_internal_address_denial(monkeypatch):
    for address in ['127.0.0.1','10.0.0.1','169.254.169.254','::1','192.168.1.2','100.64.0.1']:
        monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',(address,443))])
        with pytest.raises(AccessFailure):public_addresses('novacvernovka.eu')
    for url in ['https://localhost/','http://novacvernovka.eu/','https://novacvernovka.eu.evil.test/',
                'https://user:secret@novacvernovka.eu/','https://novacvernovka.eu:444/']:
        with pytest.raises(AccessFailure):checked_url(url)


def test_redirects_robots_and_login_stop_without_retry():
    calls=[]
    def deny(url,**kw):
        calls.append(url);return Page(url,200,b'User-agent: *\nDisallow: /\n',{'content-type':'text/plain'})
    with pytest.raises(AccessFailure) as error:robots_allowed('https://www.instagram.com/p/ABC123/',deny)
    assert error.value.category=='robots_denied' and len(calls)==1
    def private(url,**kw):return Page(url,302,b'',{'location':'https://127.0.0.1/private'})
    with pytest.raises(AccessFailure):fetch_document('https://novacvernovka.eu/program/event',private)
    def login(url,**kw):return Page(url,302,b'',{'location':'/accounts/login/'})
    with pytest.raises(AccessFailure) as error:fetch_document('https://www.instagram.com/p/ABC123/',login)
    assert error.value.category=='login_required'

@pytest.mark.parametrize('status,outcome,category',[(401,'unauthorized','login_required'),(403,'blocked','access_denied'),(429,'rate_limited','rate_limit')])
def test_actual_http_status_classification_closes_connection(monkeypatch,status,outcome,category):
    class Response:
        def __init__(self):self.status=status
        def getheaders(self):return [('Retry-After','120')]
    conn=Mock();conn.getresponse.return_value=Response()
    monkeypatch.setattr('app.social.acquisition.network.PinnedHTTPS',lambda *a,**kw:conn)
    with pytest.raises(AccessFailure) as error:fetch('https://www.instagram.com/p/ABC123/')
    assert error.value.outcome==outcome and error.value.category==category
    if status==429:assert error.value.retry_after==120
    conn.close.assert_called_once()


def test_oversize_and_timeout_are_bounded(monkeypatch):
    response=Mock();response.status=200;response.getheaders.return_value=[('Content-Length','3000000')]
    conn=Mock();conn.getresponse.return_value=response
    monkeypatch.setattr('app.social.acquisition.network.PinnedHTTPS',lambda *a,**kw:conn)
    with pytest.raises(AccessFailure) as error:fetch('https://novacvernovka.eu/program/event')
    assert error.value.category=='response_limit'
    conn.request.side_effect=TimeoutError()
    with pytest.raises(AccessFailure) as error:fetch('https://novacvernovka.eu/program/event')
    assert error.value.category=='timeout'
    assert conn.close.call_count==2

@pytest.mark.parametrize('platform,url,body',[
 ('instagram','https://www.instagram.com/p/ABC123/','<meta property="og:description" content=\'123 likes, 4 comments - venue on Instagram: "Koncert Jazz 2030-11-01 20:00 Fixture Hall"\'>'),
 ('facebook','https://www.facebook.com/events/123456/','<meta property="og:description" content="Koncert Jazz 2030-11-01 20:00 Fixture Hall">'),
 ('tiktok','https://www.tiktok.com/@venue/video/1234567890123','<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">'+json.dumps({'itemStruct':{'id':'1234567890123','desc':'Koncert 2030-11-01 20:00 Fixture Hall','createTime':1790000000,'author':{'uniqueId':'venue'}}})+'</script>'),
 ('event_url','https://novacvernovka.eu/program/event','<script type="application/ld+json">'+json.dumps({'@type':'MusicEvent','name':'Concert Jazz','startDate':'2030-11-01T20:00:00+01:00','location':{'name':'Fixture Hall'}})+'</script>'),
])
def test_synthetic_public_document_parsing_is_not_a_live_acquisition_claim(platform,url,body):
    target=normalize_target(url)
    if platform in ('instagram','facebook'):
        body='<meta property="og:url" content="'+target.url+'">'+body
    page=Page(url,200,body.encode(),{'content-type':'text/html'})
    result=ADAPTERS[platform].parse(target,page)
    assert len(result)==1 and result[0]['external_id']==target.external_id
    assert 'Koncert' in result[0]['caption'] or 'Concert' in result[0]['caption']
    for wall in ['<p>Log in to continue</p>','<p>Access denied</p>']:
        with pytest.raises(AccessFailure):ADAPTERS[platform].parse(target,Page(url,200,wall.encode(),{}))


def test_profiles_are_explicitly_unsupported_and_do_not_hit_network():
    for platform,url in [('instagram','https://instagram.com/venue'),('facebook','https://facebook.com/venue'),('tiktok','https://tiktok.com/@venue')]:
        network=Mock(side_effect=AssertionError('No profile enumeration'))
        with pytest.raises(AccessFailure) as error:ADAPTERS[platform].acquire(url,network)
        assert error.value.category=='unsupported'
        network.assert_not_called()
    result=perform({'platform':'instagram','url':'https://instagram.com/venue','method':'http','permission_expires':0})
    assert result['outcome']=='unauthorized' and not result['observations']


def test_empty_shell_and_biography_are_not_instagram_content():
    target=normalize_target('https://instagram.com/p/ABC123')
    for body in ['<div id="root"></div>','<meta property="og:description" content="120 posts, 3000 followers, Bratislava venue">']:
        with pytest.raises(AccessFailure):ADAPTERS['instagram'].parse(target,Page(target.url,200,body.encode(),{}))


def test_aggregate_network_budget_and_access_denial_never_retried():
    from app.social.acquisition.network import NetworkBudget
    calls=[]
    def fixture(url,**kwargs):
        calls.append(url)
        return Page(url,200,b'hello',{})
    transport=NetworkBudget(fixture)
    for _ in range(12):transport('https://novacvernovka.eu/program/event')
    with pytest.raises(AccessFailure):transport('https://novacvernovka.eu/program/event')
    assert len(calls)==12 and transport.received==60
    deny=Mock(side_effect=AccessFailure('rate_limit','rate_limited',60));transport=NetworkBudget(deny)
    for _ in range(2):
        with pytest.raises(AccessFailure):transport('https://www.instagram.com/p/ABC123/')
    deny.assert_called_once()


def test_public_event_article_fallback_preserves_only_actual_evidence():
    url='https://novacvernovka.eu/program/fixture-event'
    body=b'<meta property="og:title" content="Concert Jazz"><main><h1>Concert Jazz</h1><p>2030-11-01 20:00 at Fixture Hall Bratislava</p></main>'
    result=ADAPTERS['event_url'].parse(normalize_target(url),Page(url,200,body,{}))
    assert '2030-11-01 20:00' in result[0]['caption']
    assert result[0]['published_at'] is None
    assert result[0]['content_type']=='text'


def test_profile_metadata_returned_for_a_post_is_not_acquisition():
    url='https://www.facebook.com/events/123456/'
    body=b'<meta property="og:url" content="https://www.facebook.com/venue/"><meta property="og:description" content="Public venue biography, Bratislava culture and events">'
    with pytest.raises(AccessFailure):
        ADAPTERS['facebook'].parse(normalize_target(url),Page(url,200,body,{}))
