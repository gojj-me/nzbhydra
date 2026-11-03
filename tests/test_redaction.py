# coding=utf-8
"""Only invented credentials; real app handlers/models and disposable data."""
from __future__ import absolute_import, division, print_function, unicode_literals
import io, json, logging, os, shutil, sqlite3, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'libs')]
from bunch import Bunch
from requests.exceptions import HTTPError
from nzbhydra import config, database, log, redaction
from nzbhydra.search_module import SearchModule


class RedactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.mkdtemp(prefix='hydra-redaction-test-')
        database.init_db(os.path.join(cls.folder, 'synthetic.db'))
        cls.indexer = database.Indexer.create(name='synthetic')

    @classmethod
    def tearDownClass(cls):
        database.db.stop(); database.db.close()
        shutil.rmtree(cls.folder)

    def setUp(self):
        config.settings = Bunch.fromDict(config.initialConfig)
        config.settings.main.logging.consolelevel = 'DEBUG'
        config.settings.main.logging.logfilelevel = 'DEBUG'
        config.settings.main.logging.rolloverAtStart = False
        self.root = logging.getLogger('root')
        self.base = logging.getLogger()
        self.old_base_handlers = self.base.handlers[:]
        self.base.handlers = [log.console_logger]
        self.old_handlers = self.root.handlers[:]
        self.old_filters = self.root.filters[:]
        self.old_level = self.root.level
        self.old_stream = log.console_logger.stream
        self.console = io.StringIO()
        log.console_logger.stream = self.console
        self.root.handlers = [log.console_logger]; self.root.filters = []
        self.filename = os.path.join(self.folder, 'output.log')
        if os.path.exists(self.filename): os.unlink(self.filename)
        log.setup_custom_logger(self.filename)
        self.file = self.root.handlers[-1]
        database.IndexerApiAccess.delete().execute()
        database.IndexerStatus.delete().execute()

    def tearDown(self):
        self.file.close()
        self.root.handlers = self.old_handlers; self.root.filters = self.old_filters
        self.base.handlers = self.old_base_handlers
        self.root.setLevel(self.old_level)
        log.console_logger.stream = self.old_stream

    def output(self):
        self.file.flush()
        with io.open(self.filename, encoding='utf8') as f:
            return self.console.getvalue() + f.read()

    def safe(self, text, values):
        for value in values:
            self.assertNotIn(value, text)

    def test_direct_complete_punctuation_values(self):
        for key in ['apikey','api','password','username','token','client_secret']:
            for secret in ['invented.dot-hyphen_tail+/=%2F', 'invented,comma]brace}tail!;']:
                self.root.warning('request failed %s=%s status=429', key, secret)
                self.safe(self.output(), [secret, 'brace}tail!', 'hyphen_tail'])
        self.assertIn('status=429', self.output())

    def test_lazy_tuple_and_mapping_and_percent(self):
        self.root.error('GET %s status=%d progress=100%%', 'https://example.invalid/api?apikey=invented-lazy.tail&cat=2000', 500)
        self.root.info('password=%(password)s status=%(status)d', {'password':'invented-map.tail', 'status':403})
        output = self.output()
        self.safe(output, ['invented-lazy.tail','invented-map.tail'])
        self.assertIn('cat=2000', output); self.assertIn('status=500', output)
        self.assertIn('status=403', output); self.assertIn('100%', output)

    def test_nested_structures_and_non_string_values(self):
        self.root.info({'apiKey':'invented-nested.tail', 'details':[{'password':['invented-list',123], 'count':7}], 'ok':True})
        self.safe(self.output(), ['invented-nested.tail','invented-list'])
        self.assertIn("'count': 7", self.output())

    def test_serialized_json_and_repr_escaped_quotes(self):
        for value in [json.dumps({'password':'invented"quote-tail', 'status':500}),
                      repr({'apikey':"invented'quote-tail", 'status':404}),
                      "{u'password': u'invented\\\\slash-tail'}"]:
            self.root.info(value)
        self.safe(self.output(), ['quote-tail','slash-tail'])
        self.assertIn('status', self.output())

    def test_encoded_keys_values_and_case_repetition(self):
        text = 'https://example.invalid/api?%61pi%6Bey=invented%2Fencoded-tail&APIKEY=invented-second.tail&token=invented%3Dtoken&cat=2000'
        result = redaction.redact_text(text)
        self.safe(result, ['encoded-tail','second.tail','invented%3Dtoken'])
        self.assertIn('cat=2000', result)
        encoded = redaction.redact_text('https%3A%2F%2Fexample.invalid%2Fapi%3Fapikey%3Dinvented%2Fwhole-tail%26cat%3D2000')
        self.assertNotIn('whole-tail', encoded)

    def test_headers_cookies_bearer_and_signed_urls(self):
        self.root.info({'Authorization':'Bearer invented-auth.tail', 'Cookie':'session=invented-cookie; prefs=invented-pref'})
        self.root.info('Authorization: Bearer invented-header.tail')
        self.root.info('Cookie: session=invented-session; prefs=invented-prefs')
        self.root.info('https://example.invalid/file?X-Amz-Signature=invented-sig.tail&X-Amz-Credential=invented-credential&X-Amz-Security-Token=invented-security')
        self.safe(self.output(), ['invented-auth','invented-cookie','invented-pref','invented-header','invented-session','invented-sig','invented-credential','invented-security'])

    def test_url_userinfo(self):
        result = redaction.redact_text('https://invented-user:invented-P@ss.tail@example.invalid/api?cat=2000')
        self.safe(result,['invented-user','ss.tail'])
        self.assertIn('example.invalid/api?cat=2000',result)

    def test_exception_traceback_and_child_logger_both_handlers(self):
        child = logging.getLogger('synthetic.child')
        child.setLevel(logging.DEBUG)
        try:
            raise HTTPError('429 https://example.invalid/api?apikey=invented-exception.tail&cat=2000')
        except HTTPError:
            child.exception('provider failed: %s', 'password=invented-argument.tail')
        output = self.output()
        self.safe(output,['invented-exception.tail','invented-argument.tail'])
        self.assertIn('HTTPError',output); self.assertIn('Traceback',output); self.assertIn('cat=2000',output)

    def test_unicode_and_utf8_bytes(self):
        self.root.info('context café password=%s', 'invented-unicode.é-tail')
        self.root.info(b'password=invented-bytes.tail')
        output = self.output()
        self.safe(output,['é-tail','invented-bytes.tail'])
        self.assertIn('café',output)

    def test_idempotent_and_similarly_named_safe_keys(self):
        value = 'https://example.invalid/api?apikey=invented.tail&category=2000'
        result = redaction.redact_text(value)
        self.assertEqual(result,redaction.redact_text(result))
        self.assertEqual('monkey=banana category=2000 status=503', redaction.redact_text('monkey=banana category=2000 status=503'))

    def test_formatting_failure_is_safe(self):
        self.root.info('password=%s %s', 'invented-format.tail')
        self.assertNotIn('invented-format.tail',self.output())
        self.assertIn('formatting failed',self.output())

    def test_cyclic_structure_is_bounded(self):
        value = []; value.append(value)
        self.root.info(value)
        self.assertIn('nested value',self.output())

    def test_persisted_request_errors_and_status_are_sanitized(self):
        module = SearchModule(Bunch(name='synthetic'))
        secret = 'invented-request.tail'
        def failed(*args, **kwargs):
            raise HTTPError('500 https://example.invalid/api?apikey='+secret+'&cat=2000')
        module.get = failed
        response, access, status = module.get_url_with_papi_access('https://example.invalid/api', 'search')
        self.assertIsNone(response)
        saved = database.IndexerApiAccess.get()
        self.safe(saved.error,[secret,'request.tail'])
        self.safe(module.indexer.status.get().reason,[secret])
        self.assertIn('500',saved.error)
        # Model-level coverage also protects download and unexpected-error saves.
        access.error = 'password=invented-direct-model.tail'; access.save()
        status.reason = 'token=invented-status.tail'; status.save()
        self.safe(database.IndexerApiAccess.get().error,['direct-model.tail'])
        self.safe(module.indexer.status.get().reason,['invented-status.tail'])

    def test_debug_settings_redact_secrets_instead_of_exporting_hashes(self):
        import hashlib
        value = 'invented-export-signing-key'
        for key in ['apikey','password','username','secret','token','client_secret']:
            result = config.getAnonymizedConfigSetting(key,value)
            self.assertNotIn(value,result)
            self.assertNotIn(hashlib.md5(value.encode('utf8')).hexdigest(),result)
        result = config.getAnonymizedConfigSetting('url','https://invented-user:invented-pass@example.invalid/api?apikey=invented-query')
        self.safe(result,['invented-user','invented-pass','invented-query'])

    def test_log_view_sanitizes_old_text_without_rewriting_file(self):
        original = os.path.join(self.folder,'old-view.log')
        with io.open(original,'w',encoding='utf8') as f:
            f.write('password=invented-old-view.tail status=500')
        log.logfilename = original
        viewed = log.getLogFile()
        self.assertNotIn('old-view.tail',viewed)
        self.assertIn('status=500',viewed)
        self.assertIn('&lt;PASSWORD&gt;',viewed)

    def test_normal_notice_numeric_and_nonstring_messages(self):
        self.root.notice('ordinary status=%d duration=%.2f', 200, 1.25)
        self.root.info(123)
        output = self.output()
        self.assertIn('NOTICE',output)
        self.assertIn('status=200 duration=1.25',output)
        self.assertIn('123',output)

    def test_debug_export_sanitizes_legacy_lines_without_editing_original(self):
        original = os.path.join(self.folder,'legacy.log')
        with io.open(original,'w',encoding='utf8') as f:
            f.write('old password=invented-legacy.tail\ncontext invented-unlabelled\n')
        destination = os.path.join(self.folder,'export.txt')
        log.logfilename = original
        log.getAnonymizedLogFile([('main.apikey','invented-unlabelled')], destination)
        with io.open(destination,encoding='utf8') as f: exported=f.read()
        self.safe(exported,['invented-legacy.tail','invented-unlabelled'])
        with io.open(original,encoding='utf8') as f:
            self.assertIn('invented-legacy.tail',f.read())
        self.assertEqual(2,len(exported.splitlines()))


if __name__ == '__main__': unittest.main(verbosity=2)
