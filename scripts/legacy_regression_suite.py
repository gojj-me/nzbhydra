"""Python 2.7 inner runner. Use run_legacy_regressions.py for network/data isolation."""
from __future__ import print_function
import json
import os
import platform
import signal
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, ROOT + '/libs']
SUITES = ['platform_cleanup', 'metadata_credentials', 'tls', 'binsearch', 'nzbindex_details',
          'nzbindex', 'search_lock', 'redaction', 'rate_limit', 'indexer_disable', 'retention',
          'release_readiness']


def run(command):
    with tempfile.TemporaryFile() as output:
        child = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, preexec_fn=os.setsid)
        deadline = time.time() + 90
        while child.poll() is None and time.time() < deadline:
            time.sleep(.05)
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            raise RuntimeError('Suite exceeded 90-second limit')
        output.seek(0)
        text = output.read()
        sys.stdout.write(text if child.returncode else "\n".join(text.splitlines()[-4:]) + "\n")
        sys.stdout.flush()
        if child.returncode:
            raise RuntimeError('Suite failed')


if __name__ == '__main__':
    if sys.version_info[:2] != (2, 7):
        raise RuntimeError('Application suites require Python 2.7')
    import requests
    import peewee
    print(json.dumps({'python': platform.python_version(), 'openssl': ssl.OPENSSL_VERSION,
                      'sqlite': sqlite3.sqlite_version, 'requests': requests.__version__,
                      'peewee': peewee.__version__}, sort_keys=True))
    for name in SUITES:
        print('SUITE ' + name)
        run([sys.executable, '-B', ROOT + '/tests/test_' + name + '.py'])
    # Safe inherited suites: explicit allowlist, no historical recordings/performance workloads.
    code = "import sys,unittest; sys.path[:0]=[%r,%r]; s=unittest.defaultTestLoader.loadTestsFromNames(['nzbhydra.tests.test_Update','nzbhydra.tests.test_Categories']); r=unittest.TextTestRunner(verbosity=2).run(s); sys.exit(not r.wasSuccessful())" % (ROOT, ROOT + '/libs')
    print('SUITE inherited update/categories')
    run([sys.executable, '-B', '-c', code])
    print('Legacy behavioral regression run passed')
