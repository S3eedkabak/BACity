"""Bound request bodies before JSON parsing and emit structured, token-free request logs."""
import json
import logging
import time
import uuid
from starlette.responses import JSONResponse

log = logging.getLogger('bacity.http')


class RequestMiddleware:
    def __init__(self, app, max_body=1048576):
        self.app, self.max_body = app, max_body

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
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
        async def replay():
            return messages.pop(0) if messages else await receive()
        async def traced_send(message):
            if message['type'] == 'http.response.start':
                message.setdefault('headers', []).extend([(b'x-request-id', request_id.encode()), (b'x-content-type-options', b'nosniff'), (b'cache-control', b'no-store')])
                log.info(json.dumps({'request_id': request_id, 'method': scope['method'], 'route': getattr(scope.get('route'), 'path', 'unmatched'), 'status': message['status'], 'duration_ms': round((time.monotonic()-started)*1000)}))
            await send(message)
        await self.app(scope, replay, traced_send)
