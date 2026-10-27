"""Disposable staff fixtures. Cryptographic assertions use the actual verifier."""
import hashlib
import json
import secrets
import time
from datetime import datetime,timedelta,timezone
import cbor2
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from app.social.config import settings
from app.social.models import SocialBase,Staff,Credential,StaffSession,Invitation,Publisher
from app.social.security import COOKIE,digest,encoded
from app.social.db import database
from app.social.main import app
from app.social.worker_api import app as gateway_app
from app.database import Base

ORIGIN='https://admin.bacity.test'

class Authenticator:
    def __init__(self,staff_id=None):
        self.key=ec.generate_private_key(ec.SECP256R1())
        self.id=secrets.token_bytes(32)
        self.staff_id=staff_id
        numbers=self.key.public_key().public_numbers()
        self.cose=cbor2.dumps({1:2,3:-7,-1:1,-2:numbers.x.to_bytes(32,'big'),-3:numbers.y.to_bytes(32,'big')})
    def registration(self,options,*,origin=ORIGIN,flags=0x45):
        client=json.dumps({'type':'webauthn.create','challenge':options['challenge'],'origin':origin}).encode()
        auth=hashlib.sha256(b'admin.bacity.test').digest()+bytes([flags])+(0).to_bytes(4,'big')+bytes(16)+len(self.id).to_bytes(2,'big')+self.id+self.cose
        return {'id':encoded(self.id),'rawId':encoded(self.id),'type':'public-key','response':{
            'clientDataJSON':encoded(client),'attestationObject':encoded(cbor2.dumps({'fmt':'none','attStmt':{},'authData':auth})), 'transports':['internal']}}
    def assertion(self,options,*,origin=ORIGIN,flags=0x05,count=1):
        client=json.dumps({'type':'webauthn.get','challenge':options['challenge'],'origin':origin}).encode()
        auth=hashlib.sha256(b'admin.bacity.test').digest()+bytes([flags])+count.to_bytes(4,'big')
        signature=self.key.sign(auth+hashlib.sha256(client).digest(),ec.ECDSA(hashes.SHA256()))
        return {'id':encoded(self.id),'rawId':encoded(self.id),'type':'public-key','response':{
            'clientDataJSON':encoded(client),'authenticatorData':encoded(auth),'signature':encoded(signature),
            'userHandle':encoded(self.staff_id.encode()) if self.staff_id else None}}

@pytest.fixture
def social(monkeypatch,tmp_path):
    monkeypatch.setenv('SOCIAL_L4_ENABLED','true')
    monkeypatch.setenv('SOCIAL_ALLOW_SQLITE','true')
    monkeypatch.setenv('SOCIAL_L4_COLLECTION_ENABLED','false')
    monkeypatch.setenv('SOCIAL_L4_PUBLICATION_ENABLED','false')
    monkeypatch.setenv('SOCIAL_ADMIN_ORIGIN',ORIGIN)
    monkeypatch.setenv('SOCIAL_ADMIN_NETWORKS','127.0.0.1/32')
    monkeypatch.setenv('SOCIAL_WORKER_KEY','test-worker-key-'+('x'*32))
    monkeypatch.setenv('SOCIAL_DATABASE_URL','sqlite:///'+str(tmp_path/'staff.db'))
    settings.cache_clear()
    engine=create_engine(settings().database_url,connect_args={'check_same_thread':False})
    @event.listens_for(engine,'connect')
    def foreign_keys(connection,record):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    SocialBase.metadata.create_all(engine)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    def dependency():
        with factory() as db:
            yield db
    app.dependency_overrides[database]=dependency
    gateway_app.dependency_overrides[database]=dependency
    class Harness:
        def __init__(self):
            self.factory=factory
        def client(self,ip='127.0.0.1',worker=False):
            target=gateway_app if worker else app
            async def local(scope,receive,send):
                scope=dict(scope);scope['client']=(ip,50000)
                await target(scope,receive,send)
            return TestClient(local,base_url=ORIGIN,headers={'Origin':ORIGIN},raise_server_exceptions=True)
        def staff(self,role='OWNER',*,active=True):
            with factory() as db:
                s=Staff(email=secrets.token_hex(5)+'@staff.test',name='Test staff',role=role,active=active)
                db.add(s);db.flush()
                auth=Authenticator(s.id)
                c=Credential(id=encoded(auth.id),staff_id=s.id,public_key=encoded(auth.cose),sign_count=0,label='Test key')
                db.add(c);db.commit()
                return s,auth
        def login(self,role='OWNER',age=0,verified_age=0):
            s,auth=self.staff(role)
            raw=secrets.token_urlsafe(32)
            with factory() as db:
                db.add(StaffSession(digest=digest(raw),staff_id=s.id,staff_version=1,credential_id=encoded(auth.id),
                    created=time.time()-age,last_seen=time.time()-age,verified=time.time()-verified_age));db.commit()
            client=self.client()
            client.cookies.set(COOKIE,raw,domain='admin.bacity.test',path='/')
            client.headers['X-CSRF-Token']=digest('csrf:'+raw)
            return client,s,auth,raw
        def invite(self):
            with factory() as db:
                s=Staff(email=secrets.token_hex(5)+'@staff.test',name='New staff',role='SOCIAL_EDITOR')
                db.add(s);db.flush();raw=secrets.token_urlsafe(32)
                db.add(Invitation(digest=digest(raw),staff_id=s.id,expires=time.time()+900));db.commit()
                return s,raw
        def publisher(self,staff,**values):
            defaults={'platform':'instagram','url':'https://www.instagram.com/fixture_venue/','external_id':'fixture_venue',
                'target_type':'profile','name':'Fixture Hall','relevance':'Verified fixture venue in Bratislava',
                'venue_name':'Fixture Hall','address':'Test Street 12, Bratislava','latitude':48.15,'longitude':17.12,
                'approval':'approved','eligibility':'available','permission_basis':'Explicit synthetic fixture permission',
                'permission_expires':time.time()+86400,'method':'http','enabled':True,'created_by':staff.id}
            with factory() as db:
                p=Publisher(**(defaults|values));db.add(p);db.commit();return p
    yield Harness()
    app.dependency_overrides.clear();gateway_app.dependency_overrides.clear();engine.dispose();settings.cache_clear()

@pytest.fixture
def announcement():
    day=(datetime.now(timezone.utc)+timedelta(days=10)).date().isoformat()
    return {'source_url':'https://www.instagram.com/p/TestPost123/','external_id':'TestPost123',
            'caption':f'Koncert Jazz Night\n{day} 20:00\nFixture Hall, Bratislava\nVstup 10 EUR',
            'published_at':datetime.now(timezone.utc).isoformat(),
            'permission_attestation':'Synthetic evidence supplied under an explicit test-only permission.'}
