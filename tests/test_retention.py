"""Legacy application retention regressions: disposable SQLite, no providers."""
from __future__ import print_function
import datetime
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'libs'))
from bunch import Bunch
from playhouse.sqliteq import SqliteQueueDatabase, ResultTimeout
from nzbhydra import config, database, indexers, search, retention


class RetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.mkdtemp(prefix='hydra-retention-test-')
        cls.path = os.path.join(cls.folder, 'synthetic.db')
        database.init_db(cls.path)
        cls.indexer = database.Indexer.create(name='synthetic')

    @classmethod
    def tearDownClass(cls):
        database.db.stop()
        database.db.close()
        shutil.rmtree(cls.folder)

    def setUp(self):
        database.SearchResult.delete().execute()
        config.settings = Bunch.fromDict(config.initialConfig)
        indexers.enabled_indexers = []
        search.pseudo_cache.clear()
        self.cleaner = retention.RetentionCleaner(batch_size=25, max_batches=2, budget=0.5)

    def populate(self, old=0, fresh=0):
        today = str(datetime.date.today())
        with sqlite3.connect(self.path) as conn:
            conn.executemany('INSERT INTO searchresult '
                             '(id,indexer_id,firstFound,title,guid,link) VALUES (?,?,?,?,?,?)',
                             ((str(i), self.indexer.id, '2000-01-01' if i < old else today,
                               'synthetic', str(i), 'https://example.invalid/nzb')
                              for i in range(old + fresh)))

    def wait(self, cleaner=None):
        cleaner = cleaner or self.cleaner
        deadline = time.time() + 5
        while time.time() < deadline:
            if cleaner._lock.acquire(False):
                cleaner._lock.release()
                return
            time.sleep(0.01)
        self.fail('Retention worker did not finish within bounded test wait')

    def count(self):
        return database.SearchResult.select().count()

    def test_new_database_has_retention_index(self):
        with sqlite3.connect(self.path) as conn:
            names = [x[1].lower() for x in conn.execute('PRAGMA index_list(searchresult)')]
        self.assertIn('searchresult_firstfound', names)

    def test_existing_database_migration_is_repeatable_and_indexed(self):
        database.db.execute_sql('DROP INDEX IF EXISTS searchresult_firstFound').rowcount
        database.VersionInfo.update(version=21).execute()
        with sqlite3.connect(self.path) as conn:
            baseline = str(list(conn.execute("EXPLAIN QUERY PLAN SELECT COUNT(*) FROM searchresult WHERE firstFound < '2001-01-01'")))
        self.assertIn('SCAN TABLE', baseline.upper())
        database.update_db(self.path)
        database.ensure_retention_index()
        database.update_db(self.path)
        self.assertEqual(22, database.VersionInfo.get().version)
        with sqlite3.connect(self.path) as conn:
            plan = str(list(conn.execute("EXPLAIN QUERY PLAN SELECT COUNT(*) FROM searchresult WHERE firstFound < '2001-01-01'")))
        self.assertIn('SEARCH', plan.upper())
        self.assertIn('SEARCHRESULT_FIRSTFOUND', plan.upper())

    def test_interrupted_migration_does_not_advance_version(self):
        database.VersionInfo.update(version=21).execute()
        original = database.ensure_retention_index
        def interrupted():
            original()
            raise RuntimeError('Synthetic interruption after index creation')
        database.ensure_retention_index = interrupted
        try:
            with self.assertRaises(RuntimeError):
                database.update_db(self.path)
            self.assertEqual(21, database.VersionInfo.get().version)
        finally:
            database.ensure_retention_index = original
        database.update_db(self.path)
        self.assertEqual(22, database.VersionInfo.get().version)

    def test_bounded_batches_and_retention_boundary(self):
        self.populate(old=80, fresh=20)
        self.assertTrue(self.cleaner.schedule(database.db, 7))
        self.wait()
        self.assertEqual(50, self.count())
        self.cleaner._next_run = 0
        self.cleaner.schedule(database.db, 7)
        self.wait()
        self.assertEqual(20, self.count())
        self.assertFalse(self.cleaner.schedule(database.db, 7))

    def test_zero_days_preserves_rows_at_todays_boundary(self):
        self.populate(old=5, fresh=5)
        self.cleaner.schedule(database.db, 0)
        self.wait()
        self.assertEqual(5, self.count())

    def test_no_expired_rows_and_empty_database(self):
        self.cleaner.schedule(database.db, 7)
        self.wait()
        self.assertEqual(0, self.count())
        self.populate(fresh=5)
        self.cleaner._next_run = 0
        self.cleaner.schedule(database.db, 7)
        self.wait()
        self.assertEqual(5, self.count())

    def test_large_history_removes_only_bounded_batch(self):
        self.populate(old=100000, fresh=100)
        started = time.time()
        self.cleaner.schedule(database.db, 7)
        self.wait()
        self.assertLess(time.time() - started, 5)
        self.assertEqual(100050, self.count())

    def test_concurrent_scheduling_is_single_flight_and_nonblocking(self):
        original = self.cleaner._run
        started, release = threading.Event(), threading.Event()
        def delayed(*args):
            started.set()
            release.wait(2)
            original(*args)
        self.cleaner._run = delayed
        try:
            self.assertTrue(self.cleaner.schedule(database.db, 7))
            self.assertTrue(started.wait(1))
            outcomes = []
            threads = [threading.Thread(target=lambda: outcomes.append(self.cleaner.schedule(database.db, 7))) for i in range(20)]
            before = time.time()
            for t in threads: t.start()
            for t in threads: t.join(1)
            self.assertEqual([False] * 20, outcomes)
            self.assertLess(time.time() - before, 1)
        finally:
            release.set()
            self.wait()

    def test_locked_database_defers_without_queueing_then_recovers(self):
        self.populate(old=5)
        conn = sqlite3.connect(self.path)
        conn.execute('BEGIN IMMEDIATE')
        try:
            before = database.db.queue_size()
            started = time.time()
            self.cleaner.schedule(database.db, 7)
            self.wait()
            self.assertLess(time.time() - started, 2)
            self.assertEqual(before, database.db.queue_size())
            self.assertFalse(self.cleaner.schedule(database.db, 7))
        finally:
            conn.rollback()
            conn.close()
        self.cleaner._next_run = 0
        self.cleaner.schedule(database.db, 7)
        self.wait()
        self.assertEqual(0, self.count())

    def test_cleanup_sql_error_does_not_abort_real_search(self):
        original = retention.sqlite3.connect
        cleaner = search.retention_cleaner
        def broken(*args, **kwargs):
            raise sqlite3.OperationalError('Synthetic failure')
        cleaner._next_run = 0
        retention.sqlite3.connect = broken
        try:
            result = search.search(search.SearchRequest(type='general', query='synthetic'))
            self.assertEqual([], result['results'])
            self.wait(cleaner)
        finally:
            retention.sqlite3.connect = original

    def test_sqlite_progress_interrupt_rolls_back_unfinished_batch(self):
        self.populate(old=500)
        original = retention.sqlite3.connect
        self.cleaner.budget = 0.01
        self.cleaner.batch_size = 500
        def slow_connection(*args, **kwargs):
            conn = original(*args, **kwargs)
            conn.create_function('synthetic_delay', 0, lambda: time.sleep(0.002))
            conn.execute('CREATE TEMP TRIGGER synthetic_slow_delete BEFORE DELETE '
                         'ON searchresult BEGIN SELECT synthetic_delay(); END')
            return conn
        retention.sqlite3.connect = slow_connection
        try:
            started = time.time()
            self.cleaner.schedule(database.db, 7)
            self.wait()
            self.assertLess(time.time() - started, 2)
            self.assertEqual(500, self.count())
            self.assertFalse(self.cleaner.schedule(database.db, 7))
        finally:
            retention.sqlite3.connect = original
        self.cleaner.budget = 0.5
        self.cleaner.batch_size = 25
        self.cleaner._next_run = 0
        self.cleaner.schedule(database.db, 7)
        self.wait()
        self.assertEqual(450, self.count())

    def test_concurrent_real_searches_continue_during_cleanup(self):
        cleaner = search.retention_cleaner
        original = cleaner._run
        entered, release = threading.Event(), threading.Event()
        results, errors = [], []
        def delayed(*args):
            entered.set()
            release.wait(3)
            original(*args)
        def run(i):
            try:
                results.append(search.search(search.SearchRequest(type='general', query='synthetic-%d' % i)))
            except Exception as exc:
                errors.append(type(exc).__name__)
        cleaner._run = delayed
        cleaner._next_run = 0
        try:
            cleaner.schedule(database.db, 7)
            self.assertTrue(entered.wait(1))
            threads = [threading.Thread(target=run, args=(i,)) for i in range(5)]
            for t in threads: t.start()
            for t in threads: t.join(1)
            self.assertEqual([], errors)
            self.assertEqual(5, len(results))
            self.assertTrue(all(result['results'] == [] for result in results))
        finally:
            release.set()
            self.wait(cleaner)
            cleaner._run = original

    def test_timed_out_save_is_not_retried(self):
        class Save(object):
            calls = 0
            def save(self):
                self.calls += 1
                raise ResultTimeout('Synthetic timeout')
        item = Save()
        with self.assertRaises(ResultTimeout):
            search.saveSearch(item)
        self.assertEqual(1, item.calls)

    def test_real_queue_timeout_keeps_work_pending_until_worker_released(self):
        path = os.path.join(self.folder, 'queue-probe.db')
        queued = SqliteQueueDatabase(path, autostart=False, results_timeout=0.03)
        original = queued._SqliteQueueDatabase__execute_sql
        entered, release = threading.Event(), threading.Event()
        def delayed(*args, **kwargs):
            entered.set()
            release.wait(2)
            return original(*args, **kwargs)
        queued._SqliteQueueDatabase__execute_sql = delayed
        # Establish the connection before testing queue delay, so teardown is
        # independent of this vendored worker-start/stop connection-lock race.
        queued.connect()
        queued.start()
        try:
            cursor = queued.execute_sql('SELECT 1', require_commit=False)
            self.assertTrue(entered.wait(1))
            started = time.time()
            with self.assertRaises(ResultTimeout): cursor.fetchone()
            self.assertLess(time.time() - started, 0.5)
            self.assertFalse(cursor._event.is_set())
            self.assertTrue(queued._readers[0].is_alive())
            second = queued.execute_sql('SELECT 2', require_commit=False)
            self.assertEqual(1, queued.queue_size()[1])
            release.set()
            cursor._wait(timeout=1)
            second._wait(timeout=1)
            self.assertEqual((1,), cursor.fetchone())
            self.assertEqual((2,), second.fetchone())
        finally:
            release.set()
            queued.stop()
            queued.close()

    def test_dead_worker_diagnostic_is_distinct_from_backlog(self):
        queued = SqliteQueueDatabase(os.path.join(self.folder, 'not-started.db'), autostart=False)
        value = retention.queue_diagnostics(queued)
        self.assertIn('writer_alive=False', value)
        self.assertIn('readers_alive=0', value)
        self.assertNotIn(self.folder, value)

    def test_invalid_period_is_nonfatal_and_backed_off(self):
        self.assertFalse(self.cleaner.schedule(database.db, -1))
        self.assertFalse(self.cleaner.schedule(database.db, 7))

    def test_database_timeout_returns_controlled_503(self):
        from nzbhydra import web
        def unavailable():
            raise ResultTimeout('sensitive synthetic detail')
        web.app.add_url_rule('/synthetic-timeout', 'synthetic_timeout', unavailable)
        response = web.app.test_client().get('/synthetic-timeout')
        self.assertEqual(503, response.status_code)
        self.assertEqual('60', response.headers['Retry-After'])
        self.assertNotIn(b'sensitive', response.data)


if __name__ == '__main__':
    unittest.main(verbosity=2)
