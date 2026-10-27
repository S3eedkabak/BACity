import ipaddress
import uuid
from urllib.parse import urlsplit
from starlette.responses import JSONResponse
from .config import settings


class PrivateBoundary:
    def __init__(self, app):
        self.app=app

    async def __call__(self, scope, receive, send):
        if scope['type']!='http':
            return await self.app(scope,receive,send)
        cfg=settings()
        scope.setdefault('state',{})['request_id']=uuid.uuid4().hex
        headers=dict(scope.get('headers',[]))
        client=scope.get('client')
        permitted=False
        try:
            address=ipaddress.ip_address(client[0])
            if cfg.trusted_proxy_ip and str(address)==cfg.trusted_proxy_ip:
                address=ipaddress.ip_address(headers.get(b'x-forwarded-for',b'').decode())
            scope['state']['source_ip']=str(address)
            permitted=any(address in ipaddress.ip_network(n.strip()) for n in cfg.admin_networks.split(','))
        except (TypeError,ValueError):
            pass
        expected_host=urlsplit(cfg.admin_origin).netloc.encode()
        code,detail=0,''
        trusted_proxy=bool(cfg.trusted_proxy_ip and client and client[0]==cfg.trusted_proxy_ip)
        secure=scope.get('scheme')=='https' or (trusted_proxy and headers.get(b'x-forwarded-proto')==b'https')
        if not cfg.l4_enabled:
            code,detail=404,'Not found'
        elif not secure:
            code,detail=403,'HTTPS is required'
        elif not permitted or headers.get(b'host',b'').lower()!=expected_host:
            code,detail=403,'Private staff access required'
        elif scope['method'] not in ('GET','HEAD') and headers.get(b'origin',b'').decode()!=cfg.admin_origin:
            code,detail=403,'Origin verification failed'
        elif headers.get(b'sec-fetch-site',b'')==b'cross-site':
            code,detail=403,'Cross-site request denied'
        async def secured(message):
            if message['type']=='http.response.start':
                message.setdefault('headers',[]).extend([
                    (b'content-security-policy',b"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"),
                    (b'x-frame-options',b'DENY'), (b'x-content-type-options',b'nosniff'),
                    (b'referrer-policy',b'no-referrer'), (b'cache-control',b'no-store'),
                    (b'strict-transport-security',b'max-age=31536000'),
                    (b'permissions-policy',b'camera=(), microphone=(), geolocation=(), publickey-credentials-get=(self), publickey-credentials-create=(self)'),
                    (b'x-request-id',scope['state']['request_id'].encode()),
                ])
            await send(message)
        if code:
            return await JSONResponse({'detail':detail},code)(scope,receive,secured)
        await self.app(scope,receive,secured)
