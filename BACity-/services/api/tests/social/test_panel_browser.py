"""Browser workflow against the real disposable staff API, with a virtual passkey.

Opt in with SOCIAL_BROWSER_UI_TESTS=1 after installing Playwright Chromium.
No requests reach a real provider or live panel database.
"""
from http.cookies import SimpleCookie
import base64
import os
import time
from pathlib import Path
import pytest
from cryptography.hazmat.primitives import serialization
from app.social.models import Publisher, StaffSession, CollectionJob
from app.social.security import COOKIE,digest
from .conftest import ORIGIN
from .test_simple_workflow import enable

pytestmark=pytest.mark.skipif(os.getenv('SOCIAL_BROWSER_UI_TESTS')!='1',reason='Browser UI verification not selected')


def test_review_flow_and_expired_form_resume_with_real_virtual_passkey(social,monkeypatch,tmp_path):
    from playwright.sync_api import sync_playwright,expect
    enable(monkeypatch)
    owner,staff,auth,raw=social.login()
    errors=[]
    with sync_playwright() as browser_api:
        browser=browser_api.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1000},ignore_https_errors=True)
        context.add_cookies([{'name':COOKIE,'value':raw,'domain':'admin.bacity.test','path':'/','secure':True,'httpOnly':True,'sameSite':'Strict'}])
        def bridge(route):
            req=route.request
            assert req.url.startswith(ORIGIN+'/'),req.url
            result=owner.request(req.method,req.url,content=req.post_data_buffer,headers=req.headers)
            # HTTPX flattens repeated Set-Cookie headers; forward them individually
            # through the browser cookie jar rather than comma joining them.
            for value in result.headers.get_list('set-cookie'):
                parsed=SimpleCookie();parsed.load(value)
                for name,cookie in parsed.items():
                    if cookie['max-age']=='0':context.clear_cookies(name=name)
                    else:context.add_cookies([{'name':name,'value':cookie.value,'url':ORIGIN,'secure':bool(cookie['secure']),'httpOnly':bool(cookie['httponly']),'sameSite':'Strict'}])
            headers={k:v for k,v in result.headers.items() if k not in ('content-length','transfer-encoding','content-encoding','set-cookie')}
            route.fulfill(status=result.status_code,headers=headers,body=result.content)
        context.route('**/*',bridge)
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(ORIGIN)
        expect(page.get_by_role('heading',name='Overview',exact=True)).to_be_visible()
        page.get_by_role('button',name='Publishers',exact=True).click()
        page.get_by_role('button',name='＋ Add publisher',exact=True).click()
        page.get_by_label('Instagram profile or event-page link').fill('@browser_fixture')
        page.get_by_label('Publisher name',exact=True).fill('Browser fixture venue')
        page.get_by_label('What events do they share?').fill('Concerts and performances in Bratislava')
        expect(page.get_by_text('Priority · 0–100',exact=True)).to_have_count(0)
        page.get_by_role('button',name='Add for review',exact=True).click()
        expect(page.get_by_role('button',name='Approve & start daily checks')).to_be_visible()
        with social.factory() as db:
            p=db.query(Publisher).filter_by(external_id='browser_fixture').one()
            assert not p.enabled and db.query(CollectionJob).count()==0
        page.get_by_role('checkbox').check()
        screenshots=Path(os.environ.get('SOCIAL_UI_ARTIFACTS',str(tmp_path)));screenshots.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(screenshots/'publisher-review.png'),full_page=True)
        page.get_by_role('button',name='Approve & start daily checks').click()
        expect(page.get_by_text('Daily checks on',exact=True)).to_be_visible()
        with social.factory() as db:
            p=db.query(Publisher).filter_by(external_id='browser_fixture').one();assert p.enabled and p.posts_per_profile==2 and p.collection_approved
        page.get_by_role('button',name='Daily checks',exact=True).click()
        expect(page.get_by_role('heading',name='Daily checks',exact=True)).to_have_count(2)
        page.screenshot(path=str(screenshots/'daily-checks.png'),full_page=True)
        # Prepare a second form, expire the session, and resume the very same
        # submission using real WebAuthn verification with a virtual credential.
        page.get_by_role('button',name='Publishers',exact=True).click()
        page.get_by_role('button',name='＋ Add publisher',exact=True).click()
        page.get_by_label('Instagram profile or event-page link').fill('@preserved_fixture')
        page.get_by_label('Publisher name',exact=True).fill('Preserved typed publisher')
        page.get_by_label('What events do they share?').fill('This typed description must survive signing in again')
        with social.factory() as db:
            db.get(StaffSession,digest(raw)).last_seen=time.time()-7201;db.commit()
        cdp=context.new_cdp_session(page);cdp.send('WebAuthn.enable')
        authenticator=cdp.send('WebAuthn.addVirtualAuthenticator',{'options':{'protocol':'ctap2','transport':'internal','hasResidentKey':True,'hasUserVerification':True,'isUserVerified':True,'automaticPresenceSimulation':True}})['authenticatorId']
        private=auth.key.private_bytes(serialization.Encoding.DER,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        b64=lambda v:base64.b64encode(v).decode()
        cdp.send('WebAuthn.addCredential',{'authenticatorId':authenticator,'credential':{'credentialId':b64(auth.id),'isResidentCredential':True,'rpId':'admin.bacity.test','privateKey':b64(private),'userHandle':b64(staff.id.encode()),'signCount':0}})
        page.get_by_role('button',name='Add for review',exact=True).click()
        expect(page.get_by_role('heading',name='Continue where you left off')).to_be_visible()
        assert page.get_by_label('Publisher name',exact=True).input_value()=='Preserved typed publisher'
        page.screenshot(path=str(screenshots/'session-resume.png'),full_page=True)
        page.get_by_role('button',name='Continue with passkey',exact=True).click()
        expect(page.get_by_role('button',name='Approve & start daily checks')).to_be_visible(timeout=15000)
        with social.factory() as db:
            p=db.query(Publisher).filter_by(external_id='preserved_fixture').one()
            assert p.name=='Preserved typed publisher' and not p.enabled
            assert db.query(Publisher).filter_by(external_id='preserved_fixture').count()==1
        # Narrow viewport still shows the primary action without horizontal spill.
        page.set_viewport_size({'width':390,'height':844})
        expect(page.get_by_role('button',name='Approve & start daily checks')).to_be_visible()
        page.screenshot(path=str(screenshots/'publisher-review-mobile.png'),full_page=True)
        page.get_by_role('button',name='Close dialog',exact=True).click()
        page.set_viewport_size({'width':1440,'height':1000})
        page.get_by_role('button',name='Settings',exact=True).click()
        page.locator('.setting-card').filter(has=page.get_by_role('heading',name='Team access',exact=True)).get_by_role('button',name='Open →').click()
        page.get_by_role('button',name='Invite staff member',exact=True).click()
        page.get_by_label('Full name',exact=True).fill('Disposable invited teammate')
        page.get_by_label('Individual email address',exact=True).fill('fixture-teammate@example.org')
        with social.factory() as db:
            db.query(StaffSession).filter_by(staff_id=staff.id,revoked=False).one().verified=time.time()-600;db.commit()
        page.get_by_role('button',name='Create invitation',exact=True).click()
        expect(page.get_by_role('heading',name='Continue where you left off')).to_be_visible()
        assert page.get_by_label('Full name',exact=True).input_value()=='Disposable invited teammate'
        page.get_by_role('button',name='Continue with passkey',exact=True).click()
        expect(page.get_by_role('heading',name='One-use enrollment invitation')).to_be_visible()
        assert not errors,errors
        browser.close()


def test_private_post_gallery_and_ocr_text_on_desktop_and_phone(social,announcement,tmp_path):
    import io
    from PIL import Image,ImageDraw,ImageFont
    from app.social.workflows import stage
    from app.social.models import Publisher,PostImage
    from app.social.acquisition.poster import prepare
    from playwright.sync_api import sync_playwright,expect
    owner,staff,_,raw=social.login();p=social.publisher(staff)
    poster=Image.new('RGB',(900,1200),'#261326');draw=ImageDraw.Draw(poster)
    for i,text in enumerate(['HALLOWEEN','PARTY','31.10.2030','20:00','BRATISLAVA']):
        draw.text((60,100+i*170),text,font=ImageFont.load_default(size=62),fill='#ffc9e5')
    output=io.BytesIO();poster.save(output,'PNG')
    prepared=prepare(output.getvalue(),ocr=lambda image:('HALLOWEEN PARTY\n31.10.2030 20:00\nBRATISLAVA',.96,'ready'))
    with social.factory() as db:
        observation,_=stage(db,db.get(Publisher,p.id),announcement,'fixture');observation.media=['https://scontent.cdninstagram.com/post.jpg'];db.flush()
        db.add(PostImage(observation_id=observation.id,source_url=observation.media[0],source_hash='a'*64,position=0,state='ready',preview=base64.b64decode(prepared['preview']),
            width=prepared['width'],height=prepared['height'],ocr_text=prepared['ocr_text'],ocr_status='ready',ocr_confidence=.96));db.commit()
    shots=Path(os.environ.get('SOCIAL_UI_ARTIFACTS',str(tmp_path)));shots.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as browser_api:
        browser=browser_api.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1440,'height':1000},ignore_https_errors=True)
        context.add_cookies([{'name':COOKIE,'value':raw,'domain':'admin.bacity.test','path':'/','secure':True,'httpOnly':True,'sameSite':'Strict'}])
        def bridge(route):
            req=route.request;assert req.url.startswith(ORIGIN+'/'),req.url
            result=owner.request(req.method,req.url,content=req.post_data_buffer,headers=req.headers)
            route.fulfill(status=result.status_code,headers={k:v for k,v in result.headers.items() if k not in ('content-length','transfer-encoding','content-encoding')},body=result.content)
        context.route('**/*',bridge);page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(ORIGIN);page.get_by_role('button',name='Events to review',exact=True).click()
        image=page.get_by_role('img',name='Image from the original post');expect(image).to_be_visible()
        expect(image).to_have_js_property('complete',True);assert image.evaluate('(image)=>image.naturalWidth')>0
        page.get_by_text('Text read from this image',exact=True).click()
        expect(page.get_by_text('HALLOWEEN PARTY\n31.10.2030 20:00\nBRATISLAVA',exact=True)).to_be_visible()
        page.screenshot(path=str(shots/'poster-review-desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844});expect(image).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        page.screenshot(path=str(shots/'poster-review-phone.png'),full_page=True)
        # Archived noise is absent from the queue but its evidence is reachable.
        from app.social.models import EventCandidate
        with social.factory() as db:
            db.query(EventCandidate).filter_by(observation_id=observation.id).update({'status':'rejected'});db.commit()
        page.get_by_role('button',name='Refresh',exact=False).click()
        expect(page.get_by_text('Nothing awaiting your judgment.',exact=True)).to_be_visible()
        page.get_by_role('button',name='Show past decisions',exact=True).click()
        expect(page.get_by_role('img',name='Image from the original post')).to_be_visible()
        page.get_by_role('button',name='Back to review queue',exact=True).click()
        expect(page.get_by_text('Nothing awaiting your judgment.',exact=True)).to_be_visible()
        assert not errors,errors;browser.close()
