"""Bound the multipart body before Starlette parses it into temporary files."""
from starlette.responses import JSONResponse


class PhotoBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('path') != '/api/reviews/photo' or scope.get('method') != 'POST':
            return await self.app(scope, receive, send)
        parts, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b'')
            size += len(chunk)
            if size > 564 * 1024:  # 500 KB image plus bounded multipart overhead
                return await JSONResponse({'error': 'Photo is too large'}, status_code=400)(scope, receive, send)
            parts.append(chunk)
            if not message.get('more_body', False):
                break
        sent = False
        async def bounded_receive():
            nonlocal sent
            if not sent:
                sent = True
                return {'type': 'http.request', 'body': b''.join(parts), 'more_body': False}
            return await receive()
        return await self.app(scope, bounded_receive, send)
