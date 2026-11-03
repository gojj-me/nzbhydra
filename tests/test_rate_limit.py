"""Rate-limit regressions with actual legacy models and synthetic HTTP only."""
from __future__ import print_function
import os, sys, shutil, subprocess, tempfile, threading, time, unittest
from email.utils import formatdate
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'libs')]
import arrow
from bunch import Bunch
from requests import Response
from requests.exceptions import SSLError
from nzbhydra import config, database, indexers, search, rate_limit
from nzbhydra.search_module import SearchModule
from nzbhydra.searchmodules.newznab import NewzNab, check_api_limit
from nzbhydra.exceptions import IndexerApiLimitReachedException


class RateLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.mkdtemp(prefix='hydra-rate-test-')
        cls.path = os.path.join(cls.folder, 'synthetic.db')
        database.init_db(cls.path)
        database.Indexer.create(name='synthetic')
        database.Indexer.create(name='healthy')

    @classmethod
    def tearDownClass(cls):
        database.db.stop(); database.db.close()
        shutil.rmtree(cls.folder)

    def setUp(self):
        database.IndexerStatus.delete().execute()
        database.IndexerApiAccess.delete().execute()
        config.settings = Bunch.fromDict(config.initialConfig)
        self.module = self.module_for('synthetic')
        self.url = 'https://example.invalid/api?apikey=synthetic-value'
        self.calls = []

    def module_for(self, name):
        return NewzNab(Bunch(name=name, host='https://example.invalid', enabled=True,
                            accessType='both', categories=[], loadLimitOnRandom=0,
                            hitLimit=0, downloadLimit=0, score=0, search_ids=[], timeout=1))

    def response(self, code=429, retry=None, body='<rss/>'):
        response = Response(); response.status_code = code
        response.url = self.url
        response._content = body.encode('utf8')
        if retry is not None: response.headers['Retry-After'] = retry
        return response

    def install(self, response, module=None):
        def get(url, **kwargs):
            self.calls.append(url)
            return response
        (module or self.module).get = get

    def hit(self, module=None, save=False):
        return (module or self.module).get_url_with_papi_access(self.url, 'search', saveToDb=save)

    def test_retry_after_seconds_zero_and_large_values(self):
        now = arrow.get('2026-01-01T00:00:00+00:00')
        for value, seconds in [('120',120),('0',1),(' 0002 ',2)]:
            self.assertEqual(seconds, (rate_limit.retry_at(value, now) - now).total_seconds())
        self.assertEqual(9999, rate_limit.retry_at('9'*100, now).year)

    def test_retry_after_http_date_and_invalid_fallback(self):
        now = arrow.get('2026-01-01T00:00:00+00:00')
        date = formatdate(now.timestamp + 3600, usegmt=True)
        self.assertEqual(3600, (rate_limit.retry_at(date, now) - now).total_seconds())
        for value in [None, '', '-1', '1.5', 'invalid', '1\r\ninjected', 'x'*129,
                      formatdate(now.timestamp - 1, usegmt=True)]:
            self.assertEqual(900, (rate_limit.retry_at(value, now)-now).total_seconds(), repr(value))

    def test_http_429_is_persisted_and_sanitized(self):
        self.install(self.response(retry='120'))
        response, access, status = self.hit(save=True)
        self.assertIsNone(response)
        self.assertFalse(access.response_successful)
        self.assertTrue(rate_limit.active(status))
        self.assertFalse(status.disabled_permanently)
        self.assertEqual(0, status.level)
        self.assertNotIn('apikey', status.reason)
        self.assertNotIn('example.invalid', status.reason)
        self.assertNotIn('synthetic-value', access.error)
        self.assertTrue(100 < (status.disabled_until-arrow.utcnow()).total_seconds() <= 120)
        self.assertEqual(1, database.IndexerApiAccess.select().count())
        self.hit(save=True)
        self.assertEqual(1, len(self.calls))
        self.assertEqual(1, database.IndexerApiAccess.select().count())

    def test_newznab_codes_quotes_and_descriptions(self):
        for body in ['<error code="500" description="synthetic"/>',
                     "<?xml version='1.0'?><error description='synthetic' code='501'/>",
                     '<error code="999" description="Request limit reached"/>',
                     'Daily Hits limit reached']:
            database.IndexerStatus.delete().execute()
            self.install(self.response(code=200, body=body))
            response, access, status = self.hit()
            self.assertIsNone(response)
            self.assertTrue(rate_limit.active(status), body)
            self.assertFalse(status.disabled_permanently)

    def test_newznab_limit_honors_header_and_stops_pending_queries(self):
        self.install(self.response(code=200, retry='180', body='<error code="500" description="synthetic"/>'))
        result = self.module.execute_queries([self.url, self.url + '&offset=100'], search.SearchRequest(query='synthetic'))
        self.assertFalse(result.has_more)
        self.assertEqual(1, len(self.calls))
        self.assertTrue(rate_limit.active(result.indexerStatus))
        self.assertTrue(160 < (result.indexerStatus.disabled_until-arrow.utcnow()).total_seconds() <= 180)

    def test_queued_search_skip_is_not_recorded_as_a_new_attempt(self):
        self.module.handle_rate_limit('120')
        self.install(self.response(code=200))
        result = self.module.execute_queries([self.url], search.SearchRequest(query='synthetic'))
        self.assertFalse(result.didsearch)
        self.assertFalse(result.has_more)
        self.assertEqual([], self.calls)

    def test_rate_limit_logs_do_not_include_url_or_header_contents(self):
        import logging
        captured = []
        class Capture(logging.Handler):
            def emit(self, record): captured.append(record.getMessage())
        handler = Capture()
        logger = logging.getLogger('root')
        logger.addHandler(handler)
        try:
            self.install(self.response(retry='malformed-synthetic-value'))
            self.hit()
        finally:
            logger.removeHandler(handler)
        self.assertTrue(any('Rate limited' in line for line in captured))
        self.assertFalse(any('apikey' in line or 'synthetic-value' in line or self.url in line for line in captured))

    def test_scheduler_blocks_rate_limit_even_with_temporary_override(self):
        self.module.handle_rate_limit('120')
        healthy = self.module_for('healthy')
        indexers.enabled_indexers = [self.module, healthy]
        config.settings.searching.ignoreTemporarilyDisabled = True
        for internal in (False, True):
            request = search.SearchRequest(query='synthetic', internal=internal)
            self.assertEqual([healthy], search.pick_indexers(request))

    def test_concurrent_module_instances_make_one_network_call(self):
        entered, release = threading.Event(), threading.Event()
        results, errors = [], []
        response = self.response(retry='120')
        def get(*args, **kwargs):
            self.calls.append('synthetic')
            entered.set(); release.wait(2)
            return response
        def hit(module):
            try: results.append(self.hit(module))
            except Exception as exc: errors.append(type(exc).__name__)
        modules = [self.module_for('synthetic') for i in range(6)]
        for module in modules: module.get = get
        threads = [threading.Thread(target=hit, args=(module,)) for module in modules]
        try:
            threads[0].start()
            self.assertTrue(entered.wait(1))
            for t in threads[1:]: t.start()
        finally:
            release.set()
            for t in threads: t.join(3)
        self.assertEqual([], errors)
        self.assertEqual(6, len(results))
        self.assertEqual(1, len(self.calls))
        self.assertTrue(all(result[0] is None for result in results))

    def test_slow_provider_does_not_block_a_healthy_provider(self):
        entered, release = threading.Event(), threading.Event()
        errors = []
        def blocked(*args, **kwargs):
            entered.set(); release.wait(2)
            return self.response()
        self.module.get = blocked
        def run():
            try: self.hit()
            except Exception as exc: errors.append(type(exc).__name__)
        worker = threading.Thread(target=run)
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            healthy = self.module_for('healthy')
            self.install(self.response(code=200), healthy)
            started = time.time()
            response, unused, status = self.hit(healthy)
            self.assertIsNotNone(response)
            self.assertLess(time.time()-started, 1)
        finally:
            release.set(); worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual([], errors)

    def test_success_or_other_failure_cannot_erase_or_shorten_cooldown(self):
        original = self.module.handle_rate_limit('3600').disabled_until
        for status in [self.module.handle_indexer_success(), self.module.handle_indexer_failure('synthetic failure'), self.module.handle_rate_limit('60')]:
            self.assertEqual(original, status.disabled_until)
            self.assertTrue(rate_limit.active(status))
        self.module.handle_indexer_failure('Authentication failed', True)
        self.assertTrue(self.module.indexer.status.get().disabled_permanently)
        self.module.handle_rate_limit('60')
        self.assertTrue(self.module.indexer.status.get().disabled_permanently)

    def test_expiry_allows_next_request_and_authenticated_success(self):
        status = self.module.handle_rate_limit('60')
        status.disabled_until = arrow.get(0); status.save()
        self.install(self.response(code=200))
        response, access, status = self.module.get_url_with_papi_access(self.url, 'nfo', saveToDb=True)
        self.assertIsNotNone(response)
        self.assertEqual(1, len(self.calls))
        self.assertFalse(rate_limit.active(status))
        self.assertIsNone(status.reason)

    def test_restart_reads_persisted_cooldown(self):
        self.module.handle_rate_limit('3600')
        child = '''import sys
sys.path[:0] = [sys.argv[1], sys.argv[1]+'/libs']
from bunch import Bunch
from nzbhydra import database
from nzbhydra.searchmodules.newznab import NewzNab
database.db.init(sys.argv[2]); database.db.start()
m=NewzNab(Bunch(name='synthetic',host='https://example.invalid'))
def forbidden(*args, **kwargs): raise AssertionError('Network called during persisted cooldown')
m.get=forbidden
response, access, status=m.get_url_with_papi_access('https://example.invalid/api','search',saveToDb=False)
assert response is None and status.reason.startswith('Rate limited;')
database.db.stop();database.db.close()
print('PASS persisted cooldown in fresh process')
'''
        output = subprocess.check_output([sys.executable, '-B', '-c', child, ROOT, self.path])
        self.assertIn(b'PASS persisted cooldown', output)

    def test_http_errors_keep_generic_failure_behavior(self):
        for code in [404, 500, 503, 401, 403]:
            database.IndexerStatus.delete().execute()
            self.install(self.response(code=code))
            response, access, status = self.hit()
            self.assertIsNone(response)
            self.assertEqual(1, status.level)
            self.assertFalse(rate_limit.active(status))
            self.assertTrue(status.reason.startswith('Connection failed:'))

    def test_tls_failure_keeps_connection_classification(self):
        def failed(*args, **kwargs): raise SSLError('Synthetic TLS failure')
        self.module.get = failed
        response, access, status = self.hit()
        self.assertIsNone(response)
        self.assertFalse(rate_limit.active(status))
        self.assertTrue(status.reason.startswith('Connection failed:'))

    def test_authentication_body_remains_permanent_failure(self):
        self.install(self.response(code=200, body='<error code="100" description="synthetic"/>'))
        result = self.module.execute_queries([self.url], search.SearchRequest(query='synthetic'))
        self.assertTrue(result.indexerStatus.disabled_permanently)
        self.assertFalse(rate_limit.active(result.indexerStatus))


if __name__ == '__main__': unittest.main(verbosity=2)
