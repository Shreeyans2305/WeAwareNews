"""No paid calls. Unit gates plus optional real PostgreSQL transaction tests.

SHERLOCK_TEST_DSN must point at a disposable database: tests truncate pilot data.
"""
import copy
import json
import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parents[1]))
from research.store import Store, ResearchError, transaction, money
from research.fetch import public_url, resolve_public, PinnedHTTPS
from research.pipeline import validate_evidence, validate_report, investigate
from research.providers import Providers


def fixtures():
    quote = 'The original public record establishes the dates and describes the documented decision in detail.'
    sources = [{'id': 'S%s' % i, 'text': quote, 'url': 'https://source%s.example/article' % i,
                'title': 'Source %s' % i, 'publisherHost': 'source%s.example' % i,
                'contentHash': str(i)} for i in range(1, 7)]
    claims = [{'id': 'C%s' % i, 'finding': 'Finding %s' % i, 'state': 'supported',
               'caveat': 'Records cover a limited period.',
               'evidence': [{'sourceId': 'S%s' % ((i % 6) + 1), 'quote': quote}]} for i in range(1, 9)]
    evidence = {'sufficient': True, 'gaps': ['No interviews'], 'claims': claims,
                'sources': [{'id': s['id'], 'originGroup': s['id'], 'kind': 'primary' if i == 0 else 'reporting',
                             'independenceNote': 'Original material checked.'} for i, s in enumerate(sources)]}
    paragraph = ' '.join(['Context and supporting material were examined carefully with appropriate attribution.'] * 30)
    report = {'title': 'An evidence-led brief', 'answer': 'The evidence supports a qualified answer.',
              'sections': [{'heading': heading, 'paragraphs': [{'text': paragraph, 'claimIds': [c['id'] for c in claims]}]}
                           for heading in ('Findings', 'Background', 'Competing accounts')],
              'unknowns': ['Information not publicly available.'], 'limitations': ['Accessible text only.']}
    return sources, evidence, report


class QualityTests(unittest.TestCase):
    def test_valid_evidence_and_depth(self):
        sources, evidence, report = fixtures()
        self.assertEqual(len(validate_report(report, evidence, sources)), 8)

    def test_selected_length_enforced_without_lowering_evidence_standard(self):
        from research.lengths import LENGTHS
        sources, evidence, report = fixtures()
        for choice, limits in LENGTHS.items():
            for total in (limits['minWords'], limits['maxWords']):
                for i, section in enumerate(report['sections']):
                    count = total // 3 + (1 if i < total % 3 else 0)
                    section['paragraphs'][0]['text'] = ' '.join(['word'] * count)
                validate_report(report, evidence, sources, choice)
            report['sections'][0]['paragraphs'][0]['text'] += ' extra'
            with self.assertRaises(ResearchError):
                validate_report(report, evidence, sources, choice)
        evidence['sources'][0]['kind'] = 'reporting'
        with self.assertRaises(ResearchError):
            validate_report(report, evidence, sources, 'brief')

    def test_fabricated_quote_rejected(self):
        sources, evidence, _ = fixtures()
        evidence['claims'][0]['evidence'][0]['quote'] = 'This fabricated quotation does not appear in the original source material.'
        with self.assertRaises(ResearchError):
            validate_evidence(evidence, sources)

    def test_syndicated_coverage_not_counted_as_independent(self):
        sources, evidence, _ = fixtures()
        for source in evidence['sources']:
            source['originGroup'] = 'one wire report'
        with self.assertRaises(ResearchError):
            validate_evidence(evidence, sources)

    def test_no_primary_source_fails(self):
        sources, evidence, _ = fixtures()
        for source in evidence['sources']:
            source['kind'] = 'reporting'
        with self.assertRaises(ResearchError):
            validate_evidence(evidence, sources)

    def test_shallow_or_unlinked_report_rejected(self):
        sources, evidence, report = fixtures()
        report['sections'][0]['paragraphs'][0]['claimIds'] = ['invented']
        with self.assertRaises(ResearchError):
            validate_report(report, evidence, sources)
        report['sections'] = []
        with self.assertRaises(ResearchError):
            validate_report(report, evidence, sources)

    def test_full_pipeline_requires_review(self):
        sources, evidence, report = fixtures()
        provider, store = MagicMock(), MagicMock()
        provider.deadline = float('inf')
        provider.generate.side_effect = [
            {'safe': True, 'queries': ['Question investigation %s' % i for i in range(6)]},
            evidence, report,
            {'approved': True, 'issues': [], 'supportedClaimIds': ['C%s' % i for i in range(1, 9)],
             'independentOrigins': 6, 'primarySourcePresent': True}]
        provider.search.side_effect = [[{'url': s['url']}] for s in sources]
        source_map = {s['url']: s for s in sources}
        result, review = investigate(store, {'question': 'What happened?', 'scope': '', 'id': 'x'}, provider,
                                     fetch=lambda url, deadline: copy.deepcopy(source_map[url]))
        self.assertTrue(review['approved'])
        self.assertNotIn('text', result['sources'][0])
        self.assertEqual(len(result['claims']), 8)
        self.assertEqual(provider.generate.call_count, 4)

    def test_pipeline_uses_requested_length_and_bounded_output(self):
        from research.lengths import LENGTHS
        for choice, words in [('brief', 500), ('detailed', 1800)]:
            sources, evidence, report = fixtures()
            for i, section in enumerate(report['sections']):
                section['paragraphs'][0]['text'] = ' '.join(['analysis'] * (words // 3 + (1 if i < words % 3 else 0)))
            provider, store = MagicMock(), MagicMock()
            provider.deadline = float('inf')
            provider.generate.side_effect = [{'safe': True, 'queries': ['Research question %s' % i for i in range(6)]},
                evidence, report, {'approved': True, 'issues': [], 'supportedClaimIds': ['C%s' % i for i in range(1, 9)],
                                   'independentOrigins': 6, 'primarySourcePresent': True}]
            provider.search.side_effect = [[{'url': s['url']}] for s in sources]
            source_map = {s['url']: s for s in sources}
            result, _ = investigate(store, {'id': 'job', 'question': 'A public event?', 'scope': '', 'reportLength': choice}, provider,
                                    fetch=lambda url, deadline: copy.deepcopy(source_map[url]))
            self.assertEqual(result['reportLength'], choice)
            self.assertEqual(result['wordCount'], words)
            self.assertEqual(provider.generate.call_args_list[2].kwargs['output_tokens'], LENGTHS[choice]['outputTokens'])
            self.assertEqual(provider.generate.call_args_list[0].args[2]['reportLength']['choice'], choice)

    def test_provider_requires_explicit_paid_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ResearchError):
                Providers(None, {})

    def test_provider_reserves_before_call_and_accounts_for_thinking(self):
        config = {'SHERLOCK_PAID_CALLS_ENABLED': 'true', 'SHERLOCK_RATES_VERIFIED': 'true',
                  'SHERLOCK_MODEL': 'gemini-2.5-flash', 'GOOGLE_CLOUD_PROJECT': 'test-project',
                  'SHERLOCK_SEARCH_PROVIDER': 'brave', 'SHERLOCK_BRAVE_API_KEY': 'test-key', 'SHERLOCK_INPUT_USD_PER_MILLION': '1',
                  'SHERLOCK_OUTPUT_USD_PER_MILLION': '2', 'SHERLOCK_SEARCH_USD_PER_CALL': '.005'}
        store = MagicMock()
        response = {'usageMetadata': {'promptTokenCount': 10, 'candidatesTokenCount': 20, 'thoughtsTokenCount': 30},
                    'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': '{"safe":true}'}]}}]}
        def paid_call(request, deadline):
            store.reserve.assert_called_once()
            self.assertNotIn('tools', json.loads(request.data))
            return response
        credentials = MagicMock()
        credentials.token = 'fake-token'
        with patch.dict(os.environ, config), patch('google.auth.default', return_value=(credentials, None)), patch('research.providers.read_json', side_effect=paid_call):
            provider = Providers(store, {'id': 'job'})
            self.assertEqual(provider.generate('planning', 'Return JSON.', {'question': 'Test'}), {'safe': True})
        self.assertEqual(store.settle.call_args.args[2], Decimal('0.00011'))

    def test_google_search_has_fixed_reservation_and_keeps_suggestions(self):
        config = {'SHERLOCK_PAID_CALLS_ENABLED':'true','SHERLOCK_RATES_VERIFIED':'true',
                  'SHERLOCK_SEARCH_PROVIDER':'google','SHERLOCK_MODEL':'gemini-2.5-flash',
                  'GOOGLE_CLOUD_PROJECT':'test-project','SHERLOCK_INPUT_USD_PER_MILLION':'.3',
                  'SHERLOCK_OUTPUT_USD_PER_MILLION':'2.5','SHERLOCK_SEARCH_USD_PER_CALL':'.035'}
        store, credentials = MagicMock(), MagicMock()
        credentials.token = 'fake-token'
        html = '<div>Exact Google search suggestions</div>'
        response = {'usageMetadata':{'promptTokenCount':20,'candidatesTokenCount':50},
                    'candidates':[{'content':{'parts':[{'text':'Discovery only'}]},'groundingMetadata':{
                        'searchEntryPoint':{'renderedContent':html},
                        'groundingChunks':[{'web':{'uri':'https://example.org/record','title':'Record'}}]}}]}
        def call(request, deadline):
            store.reserve.assert_called_once()
            self.assertGreater(store.reserve.call_args.args[2],Decimal('.035'))
            self.assertEqual(json.loads(request.data)['tools'],[{'googleSearch':{}}])
            self.assertNotIn('responseMimeType',json.loads(request.data)['generationConfig'])
            return response
        with patch.dict(os.environ,config,clear=True), patch('google.auth.default',return_value=(credentials,None)), patch('research.providers.read_json',side_effect=call):
            results = Providers(store,{'id':'job'}).search('A public records query',0)
            self.assertEqual(results[0]['url'],'https://example.org/record')
            self.assertEqual(store.artifact.call_args.args[2]['renderedContent'],html)
            self.assertEqual(store.settle.call_args.args[2],Decimal('.035131'))
            with patch.dict(os.environ,{'SHERLOCK_SEARCH_USD_PER_CALL':'.001'}):
                with self.assertRaises(ValueError): Providers(store,{})

    def test_public_fetch_blocks_internal_and_mixed_dns(self):
        for url in ('http://example.com', 'https://user:pass@example.com', 'https://example.com:444/a', 'file:///etc/passwd'):
            with self.assertRaises(ValueError):
                public_url(url)
        with patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]):
            with self.assertRaises(ValueError):
                resolve_public('example.com')
        with patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', ('8.8.8.8', 443)), (2, 1, 6, '', ('169.254.169.254', 443))]):
            with self.assertRaises(ValueError):
                resolve_public('example.com')

    def test_money_rounds_up_and_rejects_nonfinite(self):
        self.assertEqual(money('0.000000001'), Decimal('0.00000001'))
        for value in ('NaN', '-1', 'Infinity'):
            with self.assertRaises(ValueError):
                money(value)


class PdfTests(unittest.TestCase):
    def investigation(self):
        sources, evidence, report = fixtures()
        report.update({'sources': sources, 'claims': evidence['claims'], 'cutoff': '2026-10-28T12:00:00+00:00',
                       'disclosure': 'AI-assisted research; editor reviewed.'})
        return {'id': 'pdf-test', 'question': 'What is supported by the available evidence?', 'scope': 'Public records',
                'status': 'completed', 'reportLength': 'standard', 'report': report}

    def test_readable_pdf_has_text_pagination_and_source_links_without_network(self):
        from io import BytesIO
        from pypdf import PdfReader
        from research.pdf import render_report_pdf
        investigation = self.investigation()
        with patch('urllib.request.urlopen', side_effect=AssertionError('PDF export must not fetch sources')), patch('research.providers.Providers.generate', side_effect=AssertionError('PDF export must not call AI')):
            content = render_report_pdf(investigation)
        reader = PdfReader(BytesIO(content))
        text = '\n'.join(page.extract_text() for page in reader.pages)
        self.assertIn(investigation['report']['title'], text)
        self.assertIn('What remains unknown', text)
        self.assertIn('Research limitations', text)
        self.assertIn('Source notebook', text)
        self.assertIn('Standard report', text)
        self.assertIn('900 words of analysis', text)
        self.assertGreaterEqual(len(reader.pages), 2)
        for i, page in enumerate(reader.pages, 1):
            self.assertIn('Page %s' % i, page.extract_text())
        links = [annotation.get_object() for page in reader.pages for annotation in page.get('/Annots', [])]
        urls = [item.get('/A', {}).get('/URI') for item in links]
        self.assertIn(investigation['report']['sources'][0]['url'], urls)
        self.assertTrue(any(item.get('/Dest') for item in links))

    def test_pdf_preserves_currency_greek_and_typographic_text(self):
        from io import BytesIO
        from pypdf import PdfReader
        from research.pdf import render_report_pdf
        investigation = self.investigation()
        investigation['report']['title'] = 'An estimate of ₹500: α and β, “quoted”'
        text = ''.join(page.extract_text() for page in PdfReader(BytesIO(render_report_pdf(investigation))).pages)
        self.assertIn(investigation['report']['title'], ' '.join(text.split()))

    def test_pdf_reflects_each_selected_length(self):
        from io import BytesIO
        from pypdf import PdfReader
        from research.pdf import render_report_pdf
        for choice, label in [('brief', 'Brief'), ('standard', 'Standard'), ('detailed', 'Detailed')]:
            investigation = self.investigation()
            investigation['reportLength'] = choice
            text = PdfReader(BytesIO(render_report_pdf(investigation))).pages[0].extract_text()
            self.assertIn(label + ' report', text)

    def test_unapproved_export_fails_closed(self):
        from research.pdf import render_report_pdf
        investigation = self.investigation()
        for status in ('queued', 'awaiting_review', 'failed'):
            investigation['status'] = status
            with self.assertRaises(ValueError):
                render_report_pdf(investigation)

    def test_model_markup_is_plain_text_not_active_markup(self):
        from io import BytesIO
        from pypdf import PdfReader
        from research.pdf import render_report_pdf
        investigation = self.investigation()
        text = '<img src="file:///private/secret"/> & <b>unaltered text</b>'
        investigation['report']['title'] = text
        investigation['report']['sources'][0]['url'] = 'javascript:alert(1)'
        reader = PdfReader(BytesIO(render_report_pdf(investigation)))
        self.assertIn(text, ' '.join(reader.pages[0].extract_text().split()))
        for page in reader.pages:
            for annotation in page.get('/Annots', []):
                self.assertFalse(str(annotation.get_object().get('/A', {}).get('/URI', '')).startswith('javascript:'))


@unittest.skipUnless(os.getenv('SHERLOCK_TEST_DSN'), 'Disposable PostgreSQL DSN not configured')
class DatabaseTests(unittest.TestCase):
    def setUp(self):
        import psycopg2
        self.db = psycopg2.connect(os.environ['SHERLOCK_TEST_DSN'])
        with transaction(self.db) as cur:
            for migration in sorted(Path(__file__).parents[1].joinpath('research/migrations').glob('*.sql')):
                cur.execute(migration.read_text())
            cur.execute('TRUNCATE sherlock_invites,sherlock_access,sherlock_requests,sherlock_operations,sherlock_artifacts,sherlock_audit CASCADE')
            cur.execute('UPDATE sherlock_budget SET enabled=TRUE,committed=0,ceiling=10 WHERE id=1')
            for uid in ('alice', 'bob'):
                cur.execute("INSERT INTO sherlock_access(uid,expires_at,credits,granted_by) VALUES (%s,NOW()+INTERVAL '1 day',3,'test')", (uid,))
        self.store = Store(self.db)

    def tearDown(self):
        self.db.close()

    def submit(self, uid='alice', key='submission-key-0001'):
        return self.store.submit(uid, 'What evidence supports this public event?', '', key)

    def scalar(self, sql, args=()):
        with transaction(self.db) as cur:
            cur.execute(sql, args)
            return cur.fetchone()[0]

    def test_manual_email_invite_activates_once_for_verified_identity(self):
        with transaction(self.db) as cur:
            cur.execute("INSERT INTO sherlock_invites(email,expires_at,credits,granted_by) VALUES ('tester@example.com',NOW()+INTERVAL '30 days',3,'operator')")
        self.store.redeem_invite('new-user','someoneelse@example.com')
        self.assertFalse(self.store.access('new-user')['eligible'])
        self.store.redeem_invite('new-user','TESTER@example.com')
        self.assertTrue(self.store.access('new-user')['eligible'])
        self.store.submit('new-user','What evidence supports this public event?','','invited-request-key')
        self.store.redeem_invite('new-user','tester@example.com')
        self.assertEqual(self.store.access('new-user')['credits'],2)
        self.store.redeem_invite('different-user','tester@example.com')
        self.assertFalse(self.store.access('different-user')['eligible'])

    def test_selected_length_persisted_claimed_and_in_idempotency(self):
        question = 'What evidence supports this public event?'
        request_id = self.store.submit('alice', question, '', 'length-submission-key', 'detailed')
        self.assertEqual(self.store.detail('alice', request_id)['reportLength'], 'detailed')
        self.assertEqual(self.store.listing('alice')[0]['reportLength'], 'detailed')
        self.assertEqual(self.store.claim()['reportLength'], 'detailed')
        self.assertEqual(self.scalar('SELECT cost_limit FROM sherlock_requests WHERE id=%s', (request_id,)), Decimal('.5'))
        with self.assertRaises(ResearchError):
            self.store.submit('alice', question, '', 'length-submission-key', 'brief')
        with self.assertRaises(ValueError):
            self.store.submit('bob', question, '', 'other-submission-key', 'unlimited')
        self.assertEqual(self.store.access('bob')['credits'], 3)

    def test_submission_idempotency_and_active_limit(self):
        request_id = self.submit()
        self.assertEqual(request_id, self.submit())
        self.assertEqual(self.store.access('alice')['credits'], 2)
        with self.assertRaises(ResearchError):
            self.submit(key='submission-key-0002')
        with self.assertRaises(ResearchError):
            self.store.submit('alice', 'A completely different question?', '', 'submission-key-0001')

    def test_ownership_and_private_draft(self):
        request_id = self.submit()
        job = self.store.claim()
        self.store.finish(job, {'title': 'private draft'}, {'approved': True})
        self.assertIsNone(self.store.detail('alice', request_id)['report'])
        with self.assertRaises(ResearchError) as raised:
            self.store.detail('bob', request_id)
        self.assertEqual(raised.exception.status, 404)
        self.assertEqual(self.store.listing('bob'), [])
        with self.assertRaises(ResearchError):
            self.store.cancel('bob', request_id)

    def test_cancellation_refunds_only_once(self):
        request_id = self.submit()
        self.store.cancel('alice', request_id)
        self.store.cancel('alice', request_id)
        self.assertEqual(self.store.access('alice')['credits'], 3)
        self.assertIsNone(self.store.claim())

    def test_request_and_global_budget_enforced(self):
        self.submit()
        job = self.store.claim()
        self.store.reserve(job, 'first', '0.49')
        with self.assertRaises(ResearchError):
            self.store.reserve(job, 'second', '0.02')
        with transaction(self.db) as cur:
            cur.execute('UPDATE sherlock_budget SET committed=9.99 WHERE id=1')
        with self.assertRaises(ResearchError):
            self.store.reserve(job, 'third', '0.02')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM sherlock_operations'), 1)

    def test_ambiguous_calls_stay_reserved_and_cannot_repeat(self):
        self.submit()
        job = self.store.claim()
        self.store.reserve(job, 'search', '.05')
        with self.assertRaises(ResearchError):
            self.store.reserve(job, 'search', '.05')
        self.store.finish(job, error='research_failed')
        self.assertEqual(self.store.access('alice')['credits'], 3)
        self.assertEqual(self.scalar('SELECT committed FROM sherlock_budget'), Decimal('.05'))

    def test_settlement_releases_only_unused_reservation(self):
        self.submit()
        job = self.store.claim()
        self.store.reserve(job, 'model', '.1')
        self.store.settle(job, 'model', '.03', {'tokens': 1})
        self.assertEqual(self.scalar('SELECT committed FROM sherlock_budget'), Decimal('.03'))
        with self.assertRaises(ResearchError):
            self.store.settle(job, 'model', '.03', {})

    def test_rate_mismatch_pauses_pilot(self):
        self.submit()
        job = self.store.claim()
        self.store.reserve(job, 'model', '.01')
        with self.assertRaises(ResearchError):
            self.store.settle(job, 'model', '.02', {})
        self.assertFalse(self.store.access('alice')['acceptingRequests'])

    def test_expired_worker_fenced_and_credit_refunded(self):
        request_id = self.submit()
        job = self.store.claim()
        self.store.reserve(job, 'ambiguous', '.1')
        with transaction(self.db) as cur:
            cur.execute("UPDATE sherlock_requests SET lease_until=NOW()-INTERVAL '1 minute' WHERE id=%s", (request_id,))
        self.store.expire()
        self.store.expire()
        self.assertEqual(self.store.access('alice')['credits'], 3)
        self.assertEqual(self.scalar('SELECT committed FROM sherlock_budget'), Decimal('.1'))
        with self.assertRaises(ResearchError):
            self.store.artifact(job, 'late', {})
        with self.assertRaises(ResearchError):
            self.store.finish(job, {'title': 'late'})

    def test_concurrent_duplicate_submissions_reserve_one_credit(self):
        import psycopg2
        def submit(_):
            db = psycopg2.connect(os.environ['SHERLOCK_TEST_DSN'])
            try:
                return Store(db).submit('alice', 'What evidence supports this public event?', '', 'same-submission-key')
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(submit, range(4)))
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(self.store.access('alice')['credits'], 2)

    def test_concurrent_workers_cannot_exceed_global_budget(self):
        import psycopg2
        self.submit('alice')
        self.submit('bob')
        jobs = [self.store.claim(), self.store.claim()]
        with transaction(self.db) as cur:
            cur.execute('UPDATE sherlock_budget SET committed=9.6 WHERE id=1')
        def reserve(job):
            db = psycopg2.connect(os.environ['SHERLOCK_TEST_DSN'])
            try:
                Store(db).reserve(job, 'race', '.3')
                return True
            except ResearchError:
                return False
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(reserve, jobs))
        self.assertEqual(sum(outcomes), 1)
        self.assertEqual(self.scalar('SELECT committed FROM sherlock_budget'), Decimal('9.9'))

    def test_human_approval_required_and_rejection_refunds(self):
        import io
        from research.cli import main
        request_id = self.submit()
        job = self.store.claim()
        self.store.finish(job, {'title': 'Checked draft'}, {'approved': True})
        self.assertIsNone(self.store.detail('alice', request_id)['report'])
        with patch('research.cli.database') as db, patch('sys.stdout', new_callable=io.StringIO), patch('sys.argv', ['research', 'review', request_id, '--decision', 'approve', '--actor', 'test-editor', '--note', 'Checked the original records and every material claim.']):
            db.return_value.__enter__.return_value = self.db
            main()
        self.assertEqual(self.store.detail('alice', request_id)['report']['title'], 'Checked draft')
        self.assertEqual(self.store.access('alice')['credits'], 2)
        second = self.submit(key='submission-key-0002')
        job = self.store.claim()
        self.store.finish(job, {'title': 'Rejected draft'}, {'approved': True})
        with patch('research.cli.database') as db, patch('sys.stdout', new_callable=io.StringIO), patch('sys.argv', ['research', 'review', second, '--decision', 'reject', '--actor', 'test-editor', '--note', 'The original source does not support the key conclusion.']):
            db.return_value.__enter__.return_value = self.db
            main()
        self.assertIsNone(self.store.detail('alice', second)['report'])
        self.assertEqual(self.store.access('alice')['credits'], 2)

    def test_pg8000_adapter_works_like_api(self):
        import pg8000.dbapi
        from urllib.parse import urlsplit
        parsed = urlsplit(os.environ['SHERLOCK_TEST_DSN'])
        db = pg8000.dbapi.connect(host=parsed.hostname, port=parsed.port, user=parsed.username, password=parsed.password, database=parsed.path[1:])
        try:
            store = Store(db)
            request_id = store.submit('alice', 'What evidence supports this public event?', '', 'adapter-submission-key')
            self.assertEqual(request_id, store.submit('alice', 'What evidence supports this public event?', '', 'adapter-submission-key'))
            self.assertEqual(store.detail('alice', request_id)['status'], 'queued')
        finally:
            db.close()

    def test_api_auth_verified_email_and_disabled_submission(self):
        from fastapi import FastAPI, HTTPException, Header
        from fastapi.testclient import TestClient
        from api.sherlock import create_router
        def db():
            yield self.db
        def claims(authorization: str = Header(None)):
            if not authorization:
                raise HTTPException(401, 'Sign in')
            return {'uid': authorization, 'email_verified': authorization != 'unverified'}
        app = FastAPI()
        app.include_router(create_router(db, claims))
        with TestClient(app) as client, patch.dict(os.environ, {'SHERLOCK_ENABLED': 'true'}):
            self.assertEqual(client.get('/api/v1/sherlock/entitlement').status_code, 401)
            self.assertEqual(client.get('/api/v1/sherlock/entitlement', headers={'Authorization': 'unverified'}).status_code, 403)
            payload = {'question': 'What evidence supports this public event?', 'submissionKey': 'api-submission-key'}
            response = client.post('/api/v1/sherlock/requests', json=payload, headers={'Authorization': 'alice'})
            self.assertEqual(response.status_code, 202, response.text)
            request_id = response.json()['id']
            self.assertEqual(client.get('/api/v1/sherlock/requests/' + request_id, headers={'Authorization': 'bob'}).status_code, 404)
            pdf_url = '/api/v1/sherlock/requests/' + request_id + '/report.pdf'
            self.assertEqual(client.get(pdf_url).status_code, 401)
            self.assertEqual(client.get(pdf_url, headers={'Authorization': 'unverified'}).status_code, 403)
            self.assertEqual(client.get(pdf_url, headers={'Authorization': 'bob'}).status_code, 404)
            self.assertEqual(client.get(pdf_url, headers={'Authorization': 'alice'}).status_code, 409)
            _, evidence, report = fixtures()
            sources, _, _ = fixtures()
            report.update({'sources': sources, 'claims': evidence['claims'], 'cutoff': '2026-10-28T12:00:00+00:00'})
            with transaction(self.db) as cur:
                cur.execute("UPDATE sherlock_requests SET report=%s::jsonb,status='awaiting_review' WHERE id=%s", (json.dumps(report), request_id))
            self.assertEqual(client.get(pdf_url, headers={'Authorization': 'alice'}).status_code, 409)
            with transaction(self.db) as cur:
                cur.execute("UPDATE sherlock_requests SET status='completed' WHERE id=%s", (request_id,))
                cur.execute("UPDATE sherlock_access SET expires_at=NOW()-INTERVAL '1 day' WHERE uid='alice'")
            response = client.get(pdf_url, headers={'Authorization': 'alice'})
            self.assertEqual(response.status_code, 200, response.text[:100] if response.status_code != 200 else '')
            self.assertEqual(response.headers['content-type'], 'application/pdf')
            self.assertEqual(response.headers['cache-control'], 'private, no-store')
            self.assertIn('attachment;', response.headers['content-disposition'])
            self.assertTrue(response.content.startswith(b'%PDF-'))
            invalid = {**payload, 'reportLength': 'unlimited'}
            self.assertEqual(client.post('/api/v1/sherlock/requests', json=invalid, headers={'Authorization': 'bob'}).status_code, 422)
            with patch.dict(os.environ, {'SHERLOCK_ENABLED': 'false'}):
                self.assertEqual(client.post('/api/v1/sherlock/requests', json=payload, headers={'Authorization': 'alice'}).status_code, 503)


if __name__ == '__main__':
    unittest.main()
