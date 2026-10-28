import time
import pytest
from app.social.config import settings
from app.social.models import Staff,StaffSession,Credential,Challenge,AuditEvent
from app.social.security import COOKIE,digest,verify_audit
from .conftest import Authenticator,ORIGIN


def test_actual_webauthn_enrollment_login_rotation_and_replay(social):
    staff,invite=social.invite();client=social.client();auth=Authenticator(staff.id)
    options=client.post('/api/auth/register/options',json={'invitation':invite})
    assert options.status_code==200
    assert options.json()['authenticatorSelection']['userVerification']=='required'
    signed=auth.registration(options.json())
    result=client.post('/api/auth/register/verify',json={'credential':signed,'label':'Primary key'})
    assert result.status_code==200,result.text
    assert '__Host-bacity-staff=' in result.headers['set-cookie']
    for value in ['Secure','HttpOnly','SameSite=strict','Path=/']:
        assert value in result.headers['set-cookie']
    assert 'Domain=' not in result.headers['set-cookie']
    raw=client.cookies.get(COOKIE)
    assert client.post('/api/auth/register/verify',json={'credential':signed}).status_code==400
    client.headers['X-CSRF-Token']=result.json()['csrf']
    assert client.get('/api/auth/session').json()['role']=='SOCIAL_EDITOR'
    assert client.post('/api/auth/logout',json={}).status_code==200
    options=client.post('/api/auth/login/options').json()
    result=client.post('/api/auth/login/verify',json={'credential':auth.assertion(options)})
    assert result.status_code==200,result.text
    assert client.cookies.get(COOKIE)!=raw
    with social.factory() as db:
        assert db.get(StaffSession,digest(raw)).revoked
        assert db.query(Challenge).filter_by(consumed=False).count()==0
        assert verify_audit(db.query(AuditEvent).order_by(AuditEvent.sequence))
        assert raw not in str([a.record for a in db.query(AuditEvent)])
    assert client.post('/api/auth/login/verify',json={'credential':auth.assertion(options)}).status_code==400

@pytest.mark.parametrize('flags',[0x41,0x44,0x40])
def test_registration_requires_user_presence_and_verification(social,flags):
    staff,invite=social.invite();client=social.client();auth=Authenticator(staff.id)
    opts=client.post('/api/auth/register/options',json={'invitation':invite}).json()
    response=client.post('/api/auth/register/verify',json={'credential':auth.registration(opts,flags=flags)})
    assert response.status_code==400
    with social.factory() as db:
        assert db.query(Credential).filter_by(staff_id=staff.id).count()==0

@pytest.mark.parametrize('flags',[0x01,0x04,0x00])
def test_authentication_requires_up_uv_with_real_signature(social,flags):
    staff,auth=social.staff();client=social.client();opts=client.post('/api/auth/login/options').json()
    assert client.post('/api/auth/login/verify',json={'credential':auth.assertion(opts,flags=flags)}).status_code==400
    assert client.get('/api/auth/session').status_code==401


def test_origin_rp_challenge_expiry_and_signature_fail_closed(social):
    staff,auth=social.staff();client=social.client()
    opts=client.post('/api/auth/login/options').json()
    assert client.post('/api/auth/login/verify',json={'credential':auth.assertion(opts,origin='https://evil.test')}).status_code==400
    opts=client.post('/api/auth/login/options').json()
    with social.factory() as db:
        db.query(Challenge).filter_by(consumed=False).update({'expires':time.time()-1});db.commit()
    assert client.post('/api/auth/login/verify',json={'credential':auth.assertion(opts)}).status_code==400
    opts=client.post('/api/auth/login/options').json()
    payload=auth.assertion(opts);payload['response']['signature']='AAAA'
    assert client.post('/api/auth/login/verify',json={'credential':payload}).status_code==400


def test_anonymous_consumer_and_premium_tokens_have_no_staff_access(social):
    client=social.client()
    for headers in ({},{'Authorization':'Bearer consumer-jwt'},{'Authorization':'Bearer premium-jwt','X-Social-Worker-Key':settings().worker_key}):
        for path in ['/api/dashboard','/api/publishers','/api/candidates','/api/staff','/api/audit','/api/health']:
            assert client.get(path,headers=headers).status_code==401
    assert client.post('/api/auth/register/options',json={'role':'OWNER','email':'attacker@test.tld'}).status_code==422

@pytest.mark.parametrize('role',['SOCIAL_ADMIN','SOCIAL_EDITOR','SOCIAL_REVIEWER','SOCIAL_VIEWER'])
def test_nonowners_cannot_manage_staff_or_technical_access(social,role):
    client,staff,_,_=social.login(role)
    assert client.get('/api/staff').status_code==403
    assert client.post('/api/staff',json={'name':'Attacker','email':'attacker@staff.test','role':'OWNER'}).status_code==403
    p=social.publisher(staff)
    assert client.post('/api/publishers/'+p.id+'/access',json={'eligibility':'available','method':'http',
        'permission_basis':'cannot grant this permission','permission_expires':time.time()+3600}).status_code==403


def test_csrf_origin_and_forwarded_ip_spoofing_rejected(social):
    client,staff,_,_=social.login()
    client.headers.pop('X-CSRF-Token')
    assert client.post('/api/auth/logout',json={}).status_code==403
    assert client.post('/api/auth/login/options',headers={'Origin':'https://evil.test'}).status_code==403
    outsider=social.client(ip='203.0.113.5')
    assert outsider.get('/',headers={'X-Forwarded-For':'127.0.0.1'}).status_code==403
    assert client.get('/',headers={'Host':'evil.test'}).status_code==403

@pytest.mark.parametrize('age',[7201,28801])
def test_expired_admin_sessions_rejected(social,age):
    client,_,_,_=social.login(age=age)
    assert client.get('/api/dashboard').status_code==401


def test_recent_authentication_and_offboarding(social):
    owner,_,_,_=social.login(verified_age=301)
    assert owner.post('/api/staff',json={'email':'invite@staff.test','name':'Invited staff','role':'SOCIAL_EDITOR'}).status_code==403
    owner,_,_,_=social.login()
    editor,staff,_,_=social.login('SOCIAL_EDITOR')
    assert editor.get('/api/dashboard').status_code==200
    assert owner.patch('/api/staff/'+staff.id,json={'active':False,'role':'SOCIAL_EDITOR'}).status_code==200
    assert editor.get('/api/dashboard').status_code==401
    with social.factory() as db:
        assert db.query(AuditEvent).filter().count()>0
        assert all(s.revoked for s in db.query(StaffSession).filter_by(staff_id=staff.id))


def test_login_and_enrollment_limits(social):
    client=social.client()
    outcomes=[client.post('/api/auth/login/options').status_code for _ in range(21)]
    assert outcomes[-1]==429
    assert client.post('/api/auth/login/options').headers.get('Retry-After')=='300'


def test_credential_revoke_requires_backup_and_kills_sessions(social):
    client,staff,auth,_=social.login()
    assert client.delete('/api/auth/credentials/'+auth.assertion({'challenge':'x'})['id']).status_code==409
    opts=client.post('/api/auth/register/options',json={}).json();backup=Authenticator(staff.id)
    result=client.post('/api/auth/register/verify',json={'credential':backup.registration(opts),'label':'Backup'})
    assert result.status_code==200,result.text
    client.headers['X-CSRF-Token']=result.json()['csrf']
    assert client.delete('/api/auth/credentials/'+auth.assertion({'challenge':'x'})['id']).status_code==200
    assert client.get('/api/auth/session').status_code==200


def test_security_headers_input_bound_and_disabled_boundary(social,monkeypatch):
    client=social.client();response=client.get('/')
    assert response.status_code==200
    assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
    assert response.headers['X-Frame-Options']=='DENY'
    assert client.post('/api/auth/login/options',content='x'*65537).status_code==413
    assert client.get('/docs').status_code==404
    monkeypatch.setenv('SOCIAL_L4_ENABLED','false');settings.cache_clear()
    assert client.get('/').status_code==404
    assert client.post('/api/auth/login/options').status_code==404

@pytest.mark.parametrize('role,plus',[('USER',False),('USER',True),('ADMIN',False)])
def test_valid_consumer_jwt_and_real_plus_grant_never_authorize_staff(social,role,plus):
    from app.models.user import User
    from app.models.entitlement import EntitlementGrant
    from app.core.security import create_access_token
    with social.factory() as db:
        user=User(email='consumer-'+str(plus)+role+'@fixture.test',hashed_password='unused-test-hash',role=role)
        db.add(user);db.flush()
        if plus:
            db.add(EntitlementGrant(user_id=user.id,entitlement='bacity_plus',source='fixture',reason_category='test'))
        db.commit();token=create_access_token(str(user.id))
    client=social.client()
    assert client.get('/api/dashboard',headers={'Authorization':'Bearer '+token}).status_code==401
    assert client.get('/api/staff',headers={'Authorization':'Bearer '+token}).status_code==401
