"""Bounded public HTTPS retrieval with DNS pinning, TLS and redirect validation.

No proxies, cookies, credentials, browser execution or PDF parser. Search snippets
never become evidence. PDF/paywall/inaccessible sources are recorded as gaps.
"""
import hashlib
import http.client
import ipaddress
import socket
import ssl
import time
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit, urljoin
from urllib.robotparser import RobotFileParser

AGENT = 'WeAwareResearchBot'
MAX_BYTES = 1_000_000


def public_url(url):
    parts = urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError('Only public HTTPS URLs on port 443 are supported')
    if len(url) > 2048 or any(ord(c) < 32 for c in url):
        raise ValueError('Invalid URL')
    return urlunsplit(('https', parts.netloc, parts.path or '/', parts.query, ''))


def resolve_public(host):
    records = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(record[4][0] for record in records))
    if not addresses or any(not ipaddress.ip_address(addr).is_global for addr in addresses):
        raise ValueError('Non-public destination blocked')
    return addresses[0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def connect(self):
        address = resolve_public(self.host)
        raw = socket.create_connection((address, 443), timeout=self.timeout)
        try:
            self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def download(url, deadline, limit=MAX_BYTES, origin=None):
    for _ in range(4):
        url = public_url(url)
        parts = urlsplit(url)
        if origin and parts.netloc != origin:
            raise ValueError('Cross-origin redirect requires separate discovery')
        if time.monotonic() >= deadline:
            raise TimeoutError('Retrieval deadline reached')
        connection = PinnedHTTPS(parts.hostname, timeout=min(12, max(0.1, deadline-time.monotonic())))
        try:
            connection.request('GET', urlunsplit(('', '', parts.path, parts.query, '')),
                               headers={'User-Agent': AGENT + '/1.0', 'Accept': 'text/html,text/plain', 'Accept-Encoding': 'identity'})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                url = urljoin(url, response.getheader('Location') or '')
                continue
            if response.status != 200:
                raise ValueError('Source unavailable (HTTP %s)' % response.status)
            content_type = (response.getheader('Content-Type') or '').lower()
            if not any(kind in content_type for kind in ('text/html', 'text/plain', 'application/xhtml+xml')):
                raise ValueError('Unsupported document format')
            if response.getheader('Content-Encoding', 'identity') != 'identity':
                raise ValueError('Compressed response refused')
            chunks, size = [], 0
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Retrieval deadline reached')
                # read1 returns after one underlying read, allowing the overall
                # deadline to stop a server that trickles bytes continuously.
                chunk = response.read1(min(16384, limit + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > limit:
                    raise ValueError('Document exceeds retrieval limit')
            return url, b''.join(chunks).decode('utf-8', errors='replace'), content_type
        finally:
            connection.close()
    raise ValueError('Redirect limit reached')


class Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.pieces = []
        self.title_parts = []
        self.in_title = False
        self.published = None

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript', 'svg'):
            self.hidden += 1
        if tag == 'title':
            self.in_title = True
        if tag == 'meta':
            attrs = dict(attrs)
            if attrs.get('property', attrs.get('name')) in ('article:published_time', 'datePublished', 'date'):
                self.published = attrs.get('content', '')[:100]

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript', 'svg'):
            self.hidden = max(0, self.hidden - 1)
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        if not self.hidden:
            if self.in_title:
                self.title_parts.append(data)
            self.pieces.append(data)


def resolve_discovery_url(url, deadline):
    # Google grounding returns citation redirects. Resolve only that known
    # discovery host, then enforce the destination's own robots policy.
    for _ in range(5):
        url = public_url(url)
        parts = urlsplit(url)
        if parts.hostname != 'vertexaisearch.cloud.google.com':
            return url
        if time.monotonic() >= deadline:
            raise TimeoutError('Discovery redirect deadline reached')
        connection = PinnedHTTPS(parts.hostname,timeout=min(10,max(.1,deadline-time.monotonic())))
        try:
            connection.request('GET',urlunsplit(('', '',parts.path,parts.query,'')),headers={'User-Agent':AGENT+'/1.0'})
            response = connection.getresponse()
            if response.status not in (301,302,303,307,308) or not response.getheader('Location'):
                raise ValueError('Discovery citation has no usable redirect')
            url = urljoin(url,response.getheader('Location'))
        finally:
            connection.close()
    raise ValueError('Discovery redirect limit reached')


def fetch_source(url, deadline):
    url = resolve_discovery_url(url,deadline)
    parts = urlsplit(url)
    robots_url = urlunsplit(('https', parts.netloc, '/robots.txt', '', ''))
    # Fail closed on robots errors other than a missing robots file.
    try:
        _, robots_text, _ = download(robots_url, deadline, limit=100_000, origin=parts.netloc)
    except ValueError as exc:
        if 'HTTP 404' not in str(exc):
            raise
        robots_text = ''
    robots = RobotFileParser()
    robots.parse(robots_text.splitlines())
    if not robots.can_fetch(AGENT, url):
        raise ValueError('Source disallows research crawling')
    final_url, text, content_type = download(url, deadline, origin=parts.netloc)
    # Redirects across origins need their own robots policy; skip in the pilot.
    if urlsplit(final_url).netloc != parts.netloc:
        raise ValueError('Cross-origin redirect requires separate source discovery')
    parsed = Extractor()
    if 'html' in content_type:
        parsed.feed(text)
        text = ' '.join(parsed.pieces)
    text = ' '.join(text.split())
    if len(text) < 1000:
        raise ValueError('Too little accessible source text')
    return {'url': final_url, 'title': ' '.join(parsed.title_parts)[:300] or parts.hostname,
            'publisherHost': parts.hostname, 'publishedAt': parsed.published,
            'contentHash': hashlib.sha256(text.encode()).hexdigest(), 'text': text[:16000]}
