"""Bound request bodies before JSON parsing and emit structured, token-free request logs."""
import json
import logging
import time
import uuid
from starlette.responses import JSONResponse

log = logging.getLogger('bacity.http')


class OutboundURLRedaction(logging.Filter):
    def filter(self, record):
        # HTTPX INFO logs include URL query credentials (Google id_token) and
        # provider purchase tokens in paths. Do not retain either in log records.
        if record.name == 'httpx' and 'HTTP Request:' in record.getMessage():
            record.msg = 'Outbound HTTP request (URL redacted)'
            record.args = ()
        return True


logging.getLogger('httpx').addFilter(OutboundURLRedaction())


class RequestMiddleware:
    def __init__(self, app, max_body=1048576):
        self.app, self.max_body = app, max_body

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        path = scope.get('path', '')
        # Reject malformed/Windows UNC paths before StaticFiles resolves them.
        if not path.startswith('/') or '\\' in path or '\0' in path:
            return await JSONResponse({'detail': 'Invalid request path'}, 400)(scope, receive, send)
        request_id = uuid.uuid4().hex
        started = time.monotonic()
        size, messages = 0, []
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            size += len(message.get('body', b''))
            if size > self.max_body:
                return await JSONResponse({'detail': 'Request too large'}, 413)(scope, receive, send)
            messages.append(message)
            if not message.get('more_body', False):
                break
        content_type = dict(scope.get('headers', [])).get(b'content-type', b'').split(b';', 1)[0].lower()
        if content_type == b'application/x-www-form-urlencoded':
            body = b''.join(message.get('body', b'') for message in messages)
            # Older Starlette ignores form limits on URL-encoded input.
            if body.count(b'&') >= 128 or any(len(field) > 65536 for field in body.split(b'&')):
                return await JSONResponse({'detail': 'Form too large'}, 413)(scope, receive, send)
        async def replay():
            return messages.pop(0) if messages else await receive()
        async def traced_send(message):
            if message['type'] == 'http.response.start':
                message.setdefault('headers', []).extend([(b'x-request-id', request_id.encode()), (b'x-content-type-options', b'nosniff'), (b'cache-control', b'no-store')])
                log.info(json.dumps({'request_id': request_id, 'method': scope['method'], 'route': getattr(scope.get('route'), 'path', 'unmatched'), 'status': message['status'], 'duration_ms': round((time.monotonic()-started)*1000)}))
            await send(message)
        await self.app(scope, replay, traced_send)
