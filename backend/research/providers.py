"""Explicitly priced, single-attempt providers. Free reference discovery or bounded Brave discovery and Vertex generation; all paid calls are reserved."""
import json
import os
import re
import time
import urllib.request
from decimal import Decimal
from urllib.parse import urlencode, urlsplit
from .store import ResearchError, money
from .schemas import SCHEMAS


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_json(request, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('Research deadline reached')
    with urllib.request.build_opener(NoRedirect).open(request, timeout=min(300, remaining)) as response:
        body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError('Provider response exceeds limit')
        return json.loads(body)


class Providers:
    def __init__(self, store, job):
        if os.getenv('SHERLOCK_PAID_CALLS_ENABLED') != 'true' or os.getenv('SHERLOCK_RATES_VERIFIED') != 'true':
            raise ResearchError('not_configured', 'Paid calls and verified rates must be explicitly enabled.')
        self.model = os.environ['SHERLOCK_MODEL']
        # Supported replacement for the retired Gemini 2.5 Flash. The output
        # token limit includes reasoning; reserve extra headroom conservatively.
        floors = {'gemini-3.5-flash-lite': ('.30','2.50'), 'gemini-3.5-flash': ('1.50','9.00')}
        if self.model not in floors:
            raise ValueError('Pilot supports Gemini 3.5 Flash/Flash-Lite; Gemini 2.5 Flash has retired')
        input_floor, output_floor = map(money, floors[self.model])
        self.project = os.environ['GOOGLE_CLOUD_PROJECT']
        if not re.fullmatch(r'[a-z][a-z0-9-]{4,62}', self.project):
            raise ValueError('Invalid Google Cloud project')
        self.search_provider = os.getenv('SHERLOCK_SEARCH_PROVIDER', 'wikipedia')
        if self.search_provider == 'google':
            raise ResearchError('search_not_configured', 'Current Google grounding has no documented hard query cap; use a fixed-price search API for this pilot.')
        if self.search_provider not in ('brave', 'wikipedia'):
            raise ValueError('Unsupported search provider')
        self.key = os.environ['SHERLOCK_BRAVE_API_KEY'] if self.search_provider == 'brave' else None
        self.input_rate = money(os.environ['SHERLOCK_INPUT_USD_PER_MILLION'])
        self.output_rate = money(os.environ['SHERLOCK_OUTPUT_USD_PER_MILLION'])
        self.search_rate = money(os.environ['SHERLOCK_SEARCH_USD_PER_CALL'])
        if min(self.input_rate, self.output_rate, self.search_rate) <= 0:
            raise ValueError('Verified paid rates must be positive, including any free-tier allowance')
        if self.input_rate < input_floor or self.output_rate < output_floor or (self.search_provider == 'brave' and self.search_rate < money('.005')):
            raise ValueError('Configured rates must cover current model tokens and fixed-price searches')
        self.store, self.job = store, job
        self.deadline = time.monotonic() + 20 * 60

    def search(self, query, number):
        if self.search_provider == 'wikipedia':
            return self.reference_search(query, number)
        name = 'search-%s' % number
        self.store.reserve(self.job, name, self.search_rate)
        request = urllib.request.Request('https://api.search.brave.com/res/v1/web/search?' + urlencode({'q': query[:400], 'count': 8}),
                                         headers={'X-Subscription-Token': self.key, 'Accept': 'application/json'})
        data = read_json(request, self.deadline)
        self.store.settle(self.job, name, self.search_rate, {'provider': 'brave', 'calls': 1})
        # Snippets intentionally omitted: only fetched document text is evidence.
        return [{'url': r['url'], 'title': r.get('title', '')[:300]} for r in data.get('web', {}).get('results', []) if r.get('url')][:8]

    def reference_search(self, query, number):
        # Wikimedia's public Action API is free. It supplies leads, never
        # corroboration or final evidence. Six sequential calls, no pagination
        # or retries, three article bibliographies and 500 links per response.
        params = {'action':'query','format':'json','generator':'search',
                  'gsrsearch':query[:200],'gsrlimit':3,'prop':'extlinks',
                  'ellimit':500,'maxlag':5}
        request = urllib.request.Request('https://en.wikipedia.org/w/api.php?'+urlencode(params),
            headers={'User-Agent':'WeAwareResearchPilot/1.0 (https://weaware-3504c.web.app; weaware.news@gmail.com)'})
        data = read_json(request, self.deadline)
        if data.get('error'):
            raise ResearchError('discovery_unavailable','The free reference index is unavailable; no automatic retry.')
        pages = sorted(data.get('query',{}).get('pages',{}).values(),key=lambda p:p.get('index',100))
        results, seen = [], set()
        # Interleave article bibliographies: one large first article must not
        # crowd the other subjects out of the bounded lead pool.
        bibliographies = [(page, page.get('extlinks', [])) for page in pages]
        for rank in range(max((len(links) for _, links in bibliographies), default=0)):
            for page, links in bibliographies:
                if rank >= len(links):
                    continue
                link = links[rank]
                url = link.get('*',link.get('url',''))
                if url.startswith('http://'):
                    url = 'https://' + url[len('http://'):]
                host = (urlsplit(url).hostname or '').lower()
                if not url.startswith('https://') or host.endswith(('wikipedia.org','wikimedia.org','archive.org')) or len(url)>1200 or url in seen:
                    continue
                seen.add(url)
                results.append({'url':url,'title':('Reference from '+page.get('title',''))[:300]})
                if len(results)>=100: break
            if len(results)>=100: break
        self.store.artifact(self.job,'reference-search-%s' % number,{'query':query,
            'articles':[{'title':p.get('title'),'pageId':p.get('pageid')} for p in pages],
            'sources':results,'provider':'Wikipedia reference discovery','searchFeeUsd':'0'})
        return results

    def generate(self, stage, instruction, payload, output_tokens=6000):
        if time.monotonic() >= self.deadline:
            raise TimeoutError('Research deadline reached')
        text = json.dumps(payload, ensure_ascii=False)
        # Conservative text-only bound: one token per UTF-8 byte plus envelope
        # headroom. Reserve thinking separately as well as the full output cap.
        response_format = {'text': {'mimeType': 'APPLICATION_JSON'}}
        if stage in SCHEMAS:
            response_format['text']['schema'] = SCHEMAS[stage]
        input_bound = len((instruction + text + json.dumps(response_format)).encode('utf-8')) + 2048
        thinking = 1024
        upper = money((Decimal(input_bound) * self.input_rate + Decimal(output_tokens + thinking) * self.output_rate) / 1_000_000)
        self.store.reserve(self.job, stage, upper)
        import google.auth
        from google.auth.transport.requests import Request
        credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        credentials.refresh(Request())
        endpoint = 'https://aiplatform.googleapis.com/v1/projects/%s/locations/global/publishers/google/models/%s:generateContent' % (self.project, self.model)
        body = {'systemInstruction': {'parts': [{'text': instruction}]},
                'contents': [{'role': 'user', 'parts': [{'text': text}]}],
                'generationConfig': {'maxOutputTokens': output_tokens,
                                     'responseFormat': [response_format],
                                     'thinkingConfig': {'thinkingLevel': 'LOW'}}}
        request = urllib.request.Request(endpoint, data=json.dumps(body).encode(), method='POST',
                                         headers={'Authorization': 'Bearer ' + credentials.token, 'Content-Type': 'application/json'})
        data = read_json(request, self.deadline)
        usage = data.get('usageMetadata', {})
        if 'promptTokenCount' not in usage or 'candidatesTokenCount' not in usage:
            raise ResearchError('unknown_usage', 'Provider usage is incomplete; full reservation retained.')
        actual = (Decimal(usage['promptTokenCount']) * self.input_rate +
                  Decimal(usage['candidatesTokenCount'] + usage.get('thoughtsTokenCount', 0)) * self.output_rate) / 1_000_000
        self.store.settle(self.job, stage, actual, {'provider': 'vertex', 'model': self.model, 'usage': usage})
        candidate = data.get('candidates', [{}])[0]
        if candidate.get('finishReason') != 'STOP':
            raise ResearchError('incomplete_generation', 'Model did not finish a complete response.')
        output = ''.join(p.get('text', '') for p in candidate.get('content', {}).get('parts', []) if not p.get('thought'))
        try:
            result = json.loads(output)
        except json.JSONDecodeError as error:
            self.store.artifact(self.job, stage+'-invalid-json', {'text': output[:100000], 'finishReason':candidate.get('finishReason')})
            raise ResearchError('invalid_structured_response','Provider returned invalid structured output; no paid retry.') from error
        if not isinstance(result, dict):
            raise ValueError('Expected a structured research object')
        self.store.artifact(self.job, stage, result)
        return result
