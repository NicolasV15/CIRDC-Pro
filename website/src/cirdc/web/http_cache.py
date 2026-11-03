"""Bounded caching for the shared publication catalog and public text assets."""
import gzip
import hashlib
import threading
import time

from starlette.datastructures import Headers, MutableHeaders
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import Response


def accepts_gzip(value):
    encodings = {}
    for item in value.lower().split(','):
        name, *parameters = item.strip().split(';')
        quality = 1.0
        for parameter in parameters:
            if parameter.strip().startswith('q='):
                try:
                    quality = float(parameter.strip()[2:])
                except ValueError:
                    quality = 0.0
        encodings[name] = quality
    return encodings.get('gzip', encodings.get('*', 0.0)) > 0


class CatalogCache:
    def __init__(self, seconds=60):
        self.seconds = seconds
        self.expires = 0
        self.variants = {}
        self.lock = threading.Lock()

    def response(self, request, build):
        with self.lock:
            if not self.variants or time.monotonic() >= self.expires:
                body = build()
                packed = gzip.compress(body, compresslevel=5, mtime=0)
                self.variants = {
                    encoding: (value, '"' + hashlib.sha256(value).hexdigest() + '"')
                    for encoding, value in [('identity', body), ('gzip', packed)]
                }
                self.expires = time.monotonic() + self.seconds
            encoding = 'gzip' if accepts_gzip(request.headers.get('accept-encoding', '')) else 'identity'
            body, etag = self.variants[encoding]
        headers = {'Cache-Control': f'private, max-age={self.seconds}',
                   'ETag': etag, 'Vary': 'Accept-Encoding'}
        if encoding == 'gzip':
            headers['Content-Encoding'] = 'gzip'
        validators = [tag.strip().removeprefix('W/') for tag in request.headers.get('if-none-match', '').split(',')]
        if '*' in validators or etag in validators:
            return Response(status_code=304, headers=headers)
        return Response(body, media_type='application/json', headers=headers)


class PublicTextCompression:
    """Leave resources, PDF/Range, authentication and administrator APIs alone."""
    def __init__(self, app):
        self.app = app
        self.compressed = GZipMiddleware(app, minimum_size=1024, compresslevel=5)

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        eligible = (scope['type'] == 'http' and scope.get('method') == 'GET'
                    and (path == '/api/papers' or
                         (path.startswith('/assets/') and path.endswith(('.js', '.css', '.svg', '.json')))))
        headers = Headers(scope=scope) if eligible else None
        if not eligible or 'range' in headers:
            await self.app(scope, receive, send)
            return

        async def varied(message):
            if message['type'] == 'http.response.start':
                message = {**message, 'headers': list(message['headers'])}
                outgoing = MutableHeaders(scope=message)
                if 'accept-encoding' not in [v.strip().lower() for v in outgoing.get('vary', '').split(',')]:
                    outgoing.add_vary_header('Accept-Encoding')
            await send(message)

        app = self.compressed if accepts_gzip(headers.get('accept-encoding', '')) else self.app
        # The framework gzip middleware uses a literal gzip token, so normalize
        # accepted wildcard encodings and strip rejected/zero-quality encodings.
        if app is self.compressed:
            scope = {**scope, 'headers': [(k, v) for k, v in scope['headers'] if k.lower() != b'accept-encoding']
                     + [(b'accept-encoding', b'gzip')]}
        await app(scope, receive, varied)
