"""Actual legacy app/models, isolated SQLite, synthetic responses, no network."""
from __future__ import print_function
import os
import sys
import tempfile
import shutil
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'libs'))
from bunch import Bunch
from nzbhydra import config, database, search, indexers
from nzbhydra.database import Indexer, IndexerStatus
from nzbhydra.search_module import SearchModule
from nzbhydra.searchmodules.newznab import NewzNab


class PermanentDisableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.mkdtemp(prefix='nzbhydra-isolated-')
        database.db.init(os.path.join(cls.folder, 'synthetic.db'))
        database.db.start()
        Indexer.create_table()
        IndexerStatus.create_table()

    @classmethod
    def tearDownClass(cls):
        database.db.stop()
        database.db.close()
        shutil.rmtree(cls.folder)

    def setUp(self):
        IndexerStatus.delete().execute()
        Indexer.delete().execute()
        config.settings = Bunch.fromDict(config.initialConfig)
        self.settings = Bunch(name='synthetic', host='https://example.invalid',
                              enabled=True, accessType='both', categories=[],
                              loadLimitOnRandom=0, hitLimit=0, downloadLimit=0,
                              score=0, search_ids=[], timeout=1)
        Indexer.create(name='synthetic')
        self.module = SearchModule(self.settings)
        indexers.enabled_indexers = [self.module]

    def test_permanent_disable_blocks_internal_external_and_temporary_override(self):
        self.module.handle_indexer_failure('Synthetic authentication failure', True)
        for internal in (False, True):
            for override in (False, True):
                config.settings.searching.ignoreTemporarilyDisabled = override
                request = search.SearchRequest(type='general', query='synthetic', internal=internal)
                self.assertEqual([], search.pick_indexers(request))

    def test_success_cannot_clear_permanent_disable(self):
        self.module.handle_indexer_failure('Synthetic authentication failure', True)
        result = self.module.handle_indexer_success()
        self.assertTrue(result.disabled_permanently)
        self.assertTrue(self.module.indexer.status.get().disabled_permanently)

    def test_explicit_reset_restores_selection(self):
        self.module.handle_indexer_failure('Synthetic authentication failure', True)
        status = self.module.indexer.status.get()
        status.disabled_permanently = False
        status.disabled_until = None
        status.save()  # Same explicit reset semantics as the enable-indexer API.
        request = search.SearchRequest(type='general', query='synthetic', internal=True)
        self.assertEqual([self.module], search.pick_indexers(request))

    def test_status_is_still_disabled_on_fresh_model_read(self):
        self.module.handle_indexer_failure('Synthetic authentication failure', True)
        fresh = SearchModule(self.settings)
        self.assertTrue(fresh.indexer.status.get().disabled_permanently)

    def test_concurrent_success_and_failure_leave_authentication_disabled(self):
        threads = [threading.Thread(target=self.module.handle_indexer_success),
                   threading.Thread(target=lambda: self.module.handle_indexer_failure('Synthetic failure', True))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)
            self.assertFalse(thread.is_alive())
        self.assertTrue(self.module.indexer.status.get().disabled_permanently)

    def test_http_200_does_not_clear_authentication_disable_before_body_validation(self):
        self.module.handle_indexer_failure('Synthetic failure', True)
        response = Bunch(text='<error code="100" description="synthetic"/>')
        response.raise_for_status = lambda: None
        self.module.get = lambda *args, **kwargs: response
        returned, _, status = self.module.get_url_with_papi_access('https://example.invalid/api', 'search', saveToDb=False)
        self.assertIs(returned, response)
        self.assertIsNone(status)
        self.assertTrue(self.module.indexer.status.get().disabled_permanently)


if __name__ == '__main__':
    unittest.main(verbosity=2)
