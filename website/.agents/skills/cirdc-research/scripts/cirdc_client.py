"""Standalone CIRDC HTTP client and CLI. Python standard library only."""
import argparse
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit, quote
from urllib.request import Request, urlopen

PREFIX = '/api/agent/v1'


class ClientError(Exception):
    def __init__(self, value, status=None):
        self.value, self.status = value, status
        super().__init__(value.get('error', 'request_failed'))


class Client:
    def __init__(self, base_url=None):
        value = base_url or os.environ.get('CIRDC_BASE_URL', '')
        if not value:
            config = Path.home() / '.config/cirdc/research.json'
            try:
                value = json.loads(config.read_text(encoding='utf-8'))['base_url'] if config.exists() else ''
            except (OSError, ValueError, KeyError, TypeError):
                raise ClientError({'error': 'invalid_site_config'}) from None
        if not isinstance(value, str):
            raise ClientError({'error': 'invalid_site_config'})
        value = value.rstrip('/')
        parsed = urlsplit(value)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
            raise ClientError({'error': 'configure_site_origin', 'message': 'Set CIRDC_BASE_URL or --base-url to the site origin.'})
        self.base_url = value

    def absolute(self, value):
        if isinstance(value, list):
            return [self.absolute(item) for item in value]
        if isinstance(value, dict):
            return {key: urljoin(self.base_url, item) if isinstance(item, str) and key.endswith(('url', '_href')) and item.startswith('/') else self.absolute(item)
                    for key, item in value.items()}
        return value

    def request(self, path, data=None, params=None, method=None):
        url = self.base_url + PREFIX + path
        if params:
            url += '?' + urlencode({k: v for k, v in params.items() if v is not None and v != ''})
        body = None if data is None else json.dumps(data, allow_nan=False).encode()
        request = Request(url, data=body, method=method, headers={'Accept': 'application/json', **({'Content-Type': 'application/json'} if body is not None else {})})
        try:
            with urlopen(request, timeout=45) as response:
                if method == 'HEAD':
                    if response.headers.get_content_type() != 'application/pdf' or int(response.headers.get('Content-Length', '0')) <= 5:
                        raise ClientError({'error': 'invalid_pdf_response'})
                    return {'url': url, 'bytes': int(response.headers['Content-Length']), 'media_type': 'application/pdf'}
                result = json.load(response)
        except HTTPError as error:
            try:
                value = json.load(error)
            except (ValueError, UnicodeError):
                value = {'error': 'http_error', 'status': error.code}
            raise ClientError(self.absolute(value), error.code) from None
        except (URLError, TimeoutError, OSError):
            raise ClientError({'error': 'connection_failed', 'message': 'The request may have been accepted. Repeating ensure without retry reuses existing work.'}) from None
        return self.absolute(result)

    def capabilities(self):
        return self.request('/capabilities')

    def search(self, query='', **filters):
        return self.request('/papers', params={'q': query, **filters})

    @staticmethod
    def number(value):
        if not isinstance(value, str) or not re.fullmatch('[0-9]{1,64}', value):
            raise ClientError({'error': 'invalid_number'})
        return value

    def paper(self, number):
        return self.request('/papers/' + self.number(number))

    def ensure(self, number, resources=None, wait_seconds=10, retry=False):
        return self.request('/papers/' + self.number(number) + '/ensure',
                            data={'resources': resources or ['content'], 'wait_seconds': wait_seconds, 'retry': retry})

    def status(self, request_id, wait_seconds=0):
        if not re.fullmatch('[a-f0-9]{32}', request_id):
            raise ClientError({'error': 'invalid_request_id'})
        if not 0 <= wait_seconds <= 30:
            raise ClientError({'error': 'invalid_wait_seconds'})
        deadline = time.monotonic() + wait_seconds
        while True:
            value = self.request('/requests/' + request_id)
            if not value.get('pending') or time.monotonic() >= deadline:
                return value
            time.sleep(min(value.get('retry_after_seconds') or 2, max(0, deadline - time.monotonic())))

    def read(self, number, format='markdown', cursor=None, version=None, limit=12000):
        return self.request('/papers/' + self.number(number) + '/content',
                            params={'format': format, 'cursor': cursor, 'version': version, 'limit': limit})

    def pdf(self, number, wait_seconds=10):
        value = self.ensure(number, ['pdf'], wait_seconds)
        if value['resources']['pdf']['state'] == 'ready':
            value['download'] = self.request('/papers/' + self.number(number) + '/pdf', method='HEAD')
        return value

    def download(self, number, output):
        target = Path(output).expanduser()
        if target.exists():
            raise ClientError({'error': 'output_exists'})
        url = self.base_url + PREFIX + '/papers/' + self.number(number) + '/pdf'
        descriptor = self.request('/papers/' + self.number(number) + '/pdf', method='HEAD')
        temporary = None
        try:
            with urlopen(Request(url, headers={'Accept': 'application/pdf'}), timeout=45) as response:
                if response.headers.get_content_type() != 'application/pdf':
                    raise ClientError({'error': 'invalid_pdf_response'})
                expected = int(response.headers.get('Content-Length', '0'))
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    count = 0
                    while chunk := response.read(1024 * 1024):
                        if count == 0 and not chunk.startswith(b'%PDF-'):
                            raise ClientError({'error': 'invalid_pdf_response'})
                        stream.write(chunk)
                        count += len(chunk)
                if count <= 5 or expected and count != expected:
                    raise ClientError({'error': 'incomplete_download'})
                # Linking publishes atomically and refuses a concurrently created target.
                os.link(temporary, target)
            return {**descriptor, 'bytes': count, 'saved_to': str(target.resolve())}
        except FileExistsError:
            raise ClientError({'error': 'output_exists'}) from None
        except (URLError, TimeoutError, OSError):
            raise ClientError({'error': 'download_failed'}) from None
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', help='Site origin; alternatively set CIRDC_BASE_URL')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('capabilities')
    search = commands.add_parser('search')
    search.add_argument('query', nargs='?', default='')
    for flag in ('field', 'sort', 'kind', 'venue', 'venue-tags', 'author-id', 'author-source', 'cursor'):
        search.add_argument('--' + flag)
    for flag in ('limit', 'year-from', 'year-to'):
        search.add_argument('--' + flag, type=int)
    commands.add_parser('paper').add_argument('number')
    ensure = commands.add_parser('ensure')
    ensure.add_argument('number')
    ensure.add_argument('--resources', nargs='+', choices=['content', 'pdf'], default=['content'])
    ensure.add_argument('--wait-seconds', type=float, default=10)
    ensure.add_argument('--retry', action='store_true')
    status = commands.add_parser('status')
    status.add_argument('request_id')
    status.add_argument('--wait-seconds', type=float, default=0)
    read = commands.add_parser('read')
    read.add_argument('number')
    read.add_argument('--format', choices=['markdown', 'text', 'html'], default='markdown')
    read.add_argument('--version')
    read.add_argument('--cursor')
    read.add_argument('--limit', type=int, default=12000)
    pdf = commands.add_parser('pdf')
    pdf.add_argument('number')
    pdf.add_argument('--wait-seconds', type=float, default=10)
    pdf.add_argument('--output')
    args = vars(parser.parse_args(argv))
    command, base_url = args.pop('command'), args.pop('base_url')
    try:
        client = Client(base_url)
        if command == 'pdf':
            output = args.pop('output')
            value = client.pdf(**args)
            if output and value.get('download'):
                value['download'] = client.download(args['number'], output)
        else:
            value = getattr(client, command)(**args)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return 0
    except ClientError as error:
        print(json.dumps(error.value, ensure_ascii=False, indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
