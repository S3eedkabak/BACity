"""Ephemeral Chromium, mediated GET requests, sandbox enabled, hard job limits."""
import asyncio
import time
import os
from urllib.parse import urlsplit
from .network import AccessFailure,fetch,robots_allowed,USER_AGENT,checked_url
from .urls import normalize_target
from .adapters import ADAPTERS


async def render(url,*,fetcher=fetch,playwright_factory=None):
    from playwright.async_api import async_playwright
    target=normalize_target(url)
    if target.target_type=='profile':
        raise AccessFailure('unsupported','failed')
    await asyncio.to_thread(robots_allowed,target.url,fetcher)
    factory=playwright_factory or async_playwright
    async with factory() as runtime:
        launch={'headless':True,'chromium_sandbox':True,'args':['--disable-dev-shm-usage']}
        if os.getenv('SOCIAL_BROWSER_EXECUTABLE'):
            launch['executable_path']=os.environ['SOCIAL_BROWSER_EXECUTABLE']
        try:
            browser=await runtime.chromium.launch(**launch)
        except Exception:
            raise AccessFailure('unsupported','failed') from None
        try:
            context=await browser.new_context(user_agent=USER_AGENT,accept_downloads=False,service_workers='block',
                                              viewport={'width':1000,'height':800})
            received,requests,restriction=0,0,None
            origin=urlsplit(target.url).hostname
            async def route_request(route):
                nonlocal received,requests,restriction
                request=route.request
                if restriction:
                    await route.abort(); return
                requests+=1
                try:
                    parsed=checked_url(request.url)
                    if (request.method!='GET' or parsed.hostname!=origin or requests>12
                            or received>=4*1024*1024 or request.resource_type in ('image','media','font','websocket','other')):
                        await route.abort(); return
                    if any(path in parsed.path.lower() for path in ('/login','/accounts/','/challenge','/checkpoint')):
                        raise AccessFailure('login_required','unauthorized')
                    page=await asyncio.to_thread(fetcher,request.url,max_bytes=min(2*1024*1024,4*1024*1024-received),timeout=5)
                    received+=len(page.body)
                    if page.status in (301,302,303,307,308):
                        # Redirects are handled explicitly by the HTTP adapter, never automatically here.
                        raise AccessFailure('access_denied')
                    if page.status!=200:
                        raise AccessFailure('invalid_content','failed')
                    headers={key:value for key,value in page.headers.items() if key in ('content-type','content-security-policy')}
                    await route.fulfill(status=200,body=page.body,headers=headers)
                except AccessFailure as error:
                    restriction=error
                    await route.abort()
            await context.route('**/*',route_request)
            # WebSockets must not escape request interception.
            if not hasattr(context,'route_web_socket'):
                raise AccessFailure('unsupported','failed')
            async def close_socket(ws):
                await ws.close(code=1008,reason='WebSockets are disabled for collection')
            await context.route_web_socket('**/*',close_socket)
            page=await context.new_page()
            async def close_popup(popup):
                await popup.close()
            context.on('page',close_popup)
            try:
                await page.goto(target.url,wait_until='domcontentloaded',timeout=15000)
                await page.wait_for_timeout(300)
                if restriction:
                    raise restriction
                html=await page.content()
                if len(html.encode())>2*1024*1024:
                    raise AccessFailure('response_limit','failed')
                from .network import Page
                observations=ADAPTERS[target.platform].parse(target,Page(target.url,200,html.encode(),{'content-type':'text/html'}))
                return observations,received
            except AccessFailure:
                raise
            except Exception:
                if restriction:
                    raise restriction
                raise AccessFailure('timeout','failed') from None
            finally:
                await context.close()
        finally:
            await browser.close()


def acquire_browser(url,*,fetcher=fetch):
    try:
        return asyncio.run(asyncio.wait_for(render(url,fetcher=fetcher),timeout=30))
    except TimeoutError:
        raise AccessFailure('timeout','failed') from None
