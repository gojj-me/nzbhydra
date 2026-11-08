"""Real startup/restart and settings persistence, with disposable synthetic state."""
from __future__ import print_function
import copy
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, ROOT + '/libs']
from bunch import Bunch
from nzbhydra import config, database, update


class ReadinessTests(unittest.TestCase):
    def test_application_version_comparison(self):
        for a,b in [('0.2.99','0.2.100'), ('0.2.233','0.2.300'), ('0.2.300','0.2.301'),
                    ('0.2.999','0.3.0'), ('0.3.9','0.3.10')]:
            self.assertLess(update.versiontuple(a), update.versiontuple(b))
        self.assertEqual(update.versiontuple('0.2.300'), update.versiontuple('0.2.300'))

    def test_settings_and_database_survive_process_restart(self):
        folder = tempfile.mkdtemp(prefix='hydra-readiness-')
        child = None
        output = None
        try:
            settings = Bunch.fromDict(copy.deepcopy(config.initialConfig))
            settings.indexers = []
            settings.downloaders = []
            settings.main.apikey = 'invented-regression-key'
            settings.main.secret = 'invented-session-secret'
            settings.main.downloadCounterExecuted = True
            settings.main.isFirstStart = False
            settings.main.debug = False
            settings.main.flaskReloader = False
            settings.main.port = 5075
            settings.main.host = '127.0.0.1'
            path = folder + '/settings.cfg'
            with open(path, 'w') as target:
                json.dump(settings.toDict(), target)
            dbpath = folder + '/synthetic.db'
            for restart in range(2):
                listener = socket.socket(); listener.bind(('127.0.0.1',0))
                port = listener.getsockname()[1]; listener.close()
                output = open(folder + '/output', 'w+')
                env = dict(os.environ, NZBHYDRA_SESSION_DIR=folder+'/session')
                child = subprocess.Popen([sys.executable, '-B', ROOT+'/nzbhydra.py', '--nobrowser',
                    '--host', '127.0.0.1', '--port', str(port), '--config', path,
                    '--database', dbpath, '--logfile', folder+'/app.log'],
                    cwd=folder, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.time()+20
                url = 'http://127.0.0.1:%d/api?t=caps&apikey=invented-regression-key' % port
                ready = False
                while time.time() < deadline and child.poll() is None:
                    try:
                        response = urllib2.urlopen(url, timeout=.5)
                        body = response.read(); response.close()
                        if '<caps' in body:
                            ready = True; break
                    except (urllib2.URLError, socket.timeout):
                        time.sleep(.1)
                if not ready:
                    self.fail('Synthetic application did not become ready; exit=%r' % child.poll())
                # The real API must reject an invalid credential as well.
                try:
                    response = urllib2.urlopen(url.replace('invented-regression-key','wrong-key'),timeout=2)
                    denied = response.read(); response.close()
                    self.assertIn('<error', denied)
                except urllib2.HTTPError as error:
                    self.assertIn(error.code, (401,403))
                child.terminate(); child.wait(); child = None
                output.close(); output = None
                with open(path) as source:
                    saved = json.load(source)
                self.assertEqual('invented-regression-key', saved['main']['apikey'])
                self.assertEqual([], saved['indexers'])
                with sqlite3.connect(dbpath) as conn:
                    self.assertEqual(database.DATABASE_VERSION, conn.execute('SELECT version FROM versioninfo').fetchone()[0])
                    if restart == 0:
                        conn.execute("INSERT INTO movieidcache (imdb,tmdb,title) VALUES ('0000123','123','Synthetic persistent title')")
                    else:
                        self.assertEqual('Synthetic persistent title',conn.execute("SELECT title FROM movieidcache WHERE tmdb='123'").fetchone()[0])
        finally:
            if child is not None:
                child.kill(); child.wait()
            if output is not None: output.close()
            shutil.rmtree(folder)


if __name__ == '__main__': unittest.main(verbosity=2)
