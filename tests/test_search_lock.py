"""Synthetic search lock recovery and fixed-label timeout diagnostics, Python 2.7."""
from __future__ import print_function
import os, sys, tempfile, shutil, threading, unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0]=[ROOT, ROOT+'/libs']
from bunch import Bunch
from playhouse.sqliteq import ResultTimeout
from nzbhydra import config,database,search,databaseLock
from nzbhydra.search_module import SearchModule
from nzbhydra.retention import timeout_context


class SearchLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.mkdtemp(prefix='hydra-lock-test-')
        database.init_db(cls.folder+'/synthetic.db')
        database.Indexer.create(name='synthetic')

    @classmethod
    def tearDownClass(cls):
        database.db.stop();database.db.close();shutil.rmtree(cls.folder)

    def setUp(self):
        config.settings=Bunch.fromDict(config.initialConfig)
        search.pseudo_cache.clear()
        self.provider=SearchModule(Bunch(name='synthetic'))
        self.originals=(search.pick_indexers,search.search_and_handle_db,
                        search.tryGetOrCreateSearchResultDbEntry,search.retention_cleaner.schedule)
        search.pick_indexers=lambda request:[self.provider]
        search.retention_cleaner.schedule=lambda *args:False
        self.result=Bunch(results=[],didsearch=True,has_more=False,total=0,total_known=True,
                          indexerSearchEntry=None,rejected={},loaded_results=0)
        search.search_and_handle_db=lambda *args:{'results':{self.provider:self.result}}

    def tearDown(self):
        (search.pick_indexers,search.search_and_handle_db,
         search.tryGetOrCreateSearchResultDbEntry,search.retention_cleaner.schedule)=self.originals
        if databaseLock.locked():
            databaseLock.release()
            self.fail('Search leaked its database lock')

    def run_search(self):
        return search.search(search.SearchRequest(type='general',query='synthetic'))

    def fail_result(self, exception):
        self.result.results=[Bunch(title='synthetic',link='https://example.invalid/nzb',indexerguid='synthetic-guid')]
        def fail(*args): raise exception
        search.tryGetOrCreateSearchResultDbEntry=fail

    def test_timeout_releases_lock_and_next_search_completes(self):
        self.fail_result(ResultTimeout('invented-sensitive-detail'))
        with self.assertRaises(ResultTimeout):self.run_search()
        self.assertFalse(databaseLock.locked())
        self.result.results=[]
        self.assertEqual([],self.run_search()['results'])

    def test_unexpected_exception_also_releases_lock(self):
        self.fail_result(ValueError('synthetic result failure'))
        with self.assertRaises(ValueError):self.run_search()
        self.assertFalse(databaseLock.locked())

    def test_success_releases_lock(self):
        self.assertEqual([],self.run_search()['results'])
        self.assertFalse(databaseLock.locked())

    def test_waiting_thread_acquires_after_timeout(self):
        entered,release,acquired=threading.Event(),threading.Event(),threading.Event()
        failures=[]
        self.fail_result(ResultTimeout('synthetic'))
        def delayed(*args):
            entered.set();release.wait(2);raise ResultTimeout('synthetic')
        search.tryGetOrCreateSearchResultDbEntry=delayed
        def run():
            try:self.run_search()
            except ResultTimeout:pass
            except Exception as exc:failures.append(type(exc).__name__)
        def waiter():
            with databaseLock:acquired.set()
        first=threading.Thread(target=run);first.daemon=True
        second=threading.Thread(target=waiter);second.daemon=True
        first.start()
        try:
            self.assertTrue(entered.wait(1))
            second.start()
            self.assertFalse(acquired.wait(0.02))
        finally:
            release.set();first.join(3);second.join(3)
        self.assertTrue(acquired.is_set())
        self.assertFalse(first.is_alive());self.assertFalse(second.is_alive())
        self.assertEqual([],failures)

    def test_timeout_diagnostic_and_controlled_handler(self):
        from nzbhydra import web
        self.fail_result(ResultTimeout('apikey=invented-detail-tail'))
        messages=[]
        original=web.logger.error
        web.logger.error=lambda template,*args:messages.append(template % args)
        try:
            try:self.run_search()
            except ResultTimeout as exc:
                labels=timeout_context(sys.exc_info()[2])
                response=web.database_timeout_handler(exc)
            self.assertEqual('search',labels)
            self.assertEqual(503,response[1])
            self.assertIn('operation=search',messages[0])
            self.assertNotIn('invented-detail',messages[0])
            self.assertNotIn(ROOT,messages[0])
        finally:web.logger.error=original

    def test_real_persistence_callsite_has_fixed_label(self):
        # Compile a synthetic failing get() at the known production helper call.
        original=search.SearchResult
        class Failed(object):
            def get(self,*args,**kwargs):raise ResultTimeout('apikey=invented-tail')
        Failed.id=original.id
        Failed.DoesNotExist=original.DoesNotExist
        search.SearchResult=Failed
        try:
            try:search.tryGetOrCreateSearchResultDbEntry('synthetic',1,None)
            except ResultTimeout:
                self.assertEqual('persist-result',timeout_context(sys.exc_info()[2]))
        finally:search.SearchResult=original

    def test_unknown_traceback_is_not_exposed(self):
        try:raise ResultTimeout('password=invented-tail')
        except ResultTimeout:
            self.assertEqual('unclassified',timeout_context(sys.exc_info()[2]))
        self.assertEqual('unclassified',timeout_context(None))


if __name__=='__main__':unittest.main(verbosity=2)
