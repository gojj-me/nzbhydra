"""Best-effort, bounded retention on a dedicated SQLite connection (Python 2.7)."""
from __future__ import absolute_import, division, print_function, unicode_literals

import datetime
import logging
import os
import sqlite3
import threading
import time

logger = logging.getLogger('root')
clock = getattr(time, 'monotonic', time.time)


def queue_diagnostics(database):
    """Only structural diagnostics; never SQL, parameters, or database paths."""
    try:
        writes, reads = database.queue_size()
        writer = database._writer.is_alive()
        readers = sum(1 for worker in database._readers if worker.is_alive())
        return "write_queue=%d read_queue=%d writer_alive=%s readers_alive=%d" % (
            writes, reads, writer, readers)
    except Exception:
        return "queue_state=unavailable"


def timeout_context(traceback):
    """Emit only fixed labels for known application call sites; no source text."""
    labels = {
        ('search.py', 'search'): 'search',
        ('search.py', 'saveSearch'): 'save-search',
        ('search.py', 'tryGetOrCreateSearchResultDbEntry'): 'persist-result',
        ('search.py', 'search_and_handle_db'): 'persist-provider-response',
        ('search_module.py', 'saveIndexerStatus'): 'save-provider-status',
        ('search_module.py', 'handle_indexer_failure'): 'provider-failure',
        ('search_module.py', 'handle_rate_limit'): 'provider-rate-limit',
        ('search_module.py', 'handle_indexer_success'): 'provider-success',
        ('web.py', 'api_search'): 'api-search',
        ('web.py', 'internalapi_search'): 'ui-search',
    }
    found = []
    while traceback is not None:
        code = traceback.tb_frame.f_code
        for (filename, function), label in labels.items():
            if code.co_filename.replace('\\\\', '/').endswith('/nzbhydra/' + filename) and code.co_name == function:
                if label not in found:
                    found.append(label)
                break
        traceback = traceback.tb_next
    return '>'.join(found) if found else 'unclassified'


class RetentionCleaner(object):
    def __init__(self, batch_size=250, max_batches=4, budget=1.0,
                 interval=60.0, failure_interval=300.0):
        self.batch_size = batch_size
        self.max_batches = max_batches
        self.budget = budget
        self.interval = interval
        self.failure_interval = failure_interval
        self._lock = threading.Lock()
        self._next_run = 0

    def schedule(self, database, keep_days):
        # Hold this lock through the worker's finally block: a slow/blocked job
        # can never be replaced by another job after a caller-side timeout.
        if not self._lock.acquire(False):
            return False
        try:
            if clock() < self._next_run:
                self._lock.release()
                return False
            if isinstance(keep_days, bool) or int(keep_days) != keep_days or keep_days < 0:
                raise ValueError('Invalid retention period')
            cutoff = datetime.date.today() - datetime.timedelta(days=int(keep_days))
            path = database.database
            if not path or path == ':memory:' or not os.path.isfile(path):
                raise ValueError('Retention requires an existing file database')
            worker = threading.Thread(target=self._run, args=(database, path, cutoff))
            worker.daemon = True
            worker.start()
            return True
        except Exception as exc:
            self._next_run = clock() + self.failure_interval
            self._lock.release()
            logger.warning("Retention not scheduled (%s); %s", type(exc).__name__, queue_diagnostics(database))
            return False

    def _run(self, database, path, cutoff):
        started = clock()
        deleted = 0
        failed = False
        connection = None
        try:
            # Independent connection: cleanup never queues work on the application's
            # writer/reader workers. A busy database yields instead of being retried.
            connection = sqlite3.connect(path, timeout=min(0.25, self.budget))
            connection.set_progress_handler(lambda: int(clock() - started >= self.budget), 1000)
            for unused in range(self.max_batches):
                if clock() - started >= self.budget:
                    break
                cursor = connection.execute(
                    'DELETE FROM searchresult WHERE id IN '
                    '(SELECT id FROM searchresult WHERE firstFound < ? '
                    'ORDER BY firstFound LIMIT ?)', (str(cutoff), self.batch_size))
                connection.commit()
                deleted += cursor.rowcount
                if cursor.rowcount < self.batch_size:
                    break
            logger.debug("Retention completed: deleted=%d elapsed_ms=%d; %s", deleted,
                         int((clock() - started) * 1000), queue_diagnostics(database))
        except Exception as exc:
            failed = True
            # SQLite progress interruption rolls back the unfinished statement;
            # committed earlier batches remain committed. Never retry this job.
            logger.warning("Retention deferred (%s): elapsed_ms=%d; %s",
                           type(exc).__name__, int((clock() - started) * 1000),
                           queue_diagnostics(database))
        finally:
            try:
                if connection is not None:
                    connection.close()
            finally:
                self._next_run = clock() + (self.failure_interval if failed else self.interval)
                self._lock.release()


retention_cleaner = RetentionCleaner()
