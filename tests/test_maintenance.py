from __future__ import print_function
import contextlib
import io
import os
import shutil
import tarfile
import tempfile
import unittest

MODULE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'maintenance', 'maintenance.py')
try:
    from importlib.util import spec_from_file_location, module_from_spec
except ImportError:
    import imp
    m = imp.load_source('maintenance_under_test', MODULE)
else:
    spec = spec_from_file_location('maintenance_under_test', MODULE)
    m = module_from_spec(spec)
    spec.loader.exec_module(m)


@contextlib.contextmanager
def patched(**values):
    originals = dict((name, getattr(m, name)) for name in values)
    for name, value in values.items():
        setattr(m, name, value)
    try:
        yield
    finally:
        for name, value in originals.items():
            setattr(m, name, value)


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix='maintenance-test-'))
        m.setup(self.root)

    def tearDown(self):
        shutil.rmtree(self.root)

    def fixture(self, commit='a' * 40, extra=None):
        path = os.path.join(self.root, 'cache', commit + '.tar.gz')
        with tarfile.open(path, 'w:gz') as tar:
            for name in m.SOURCE_FILES:
                value = b'0.2.233' if name == 'version.txt' else b'synthetic test data\n'
                info = tarfile.TarInfo('nzbhydra-' + commit + '/' + name)
                info.size = len(value)
                tar.addfile(info, io.BytesIO(value))
            if extra:
                tar.addfile(extra)
        return {'source_commit': commit, 'archive_sha256': m.digest(path),
                'channel': 'test', 'application_version': '0.2.233',
                'target_release': '0.2.300', 'included_fixes': [9]}

    def test_stage_and_verified_cached_restore_are_offline(self):
        d = self.fixture()
        with patched(download=lambda *a: self.fail('Unexpected network access')):
            path = m.stage(self.root, d)
            self.assertEqual(d, m.verify_release(path))
            shutil.rmtree(path)
            self.assertEqual(path, m.stage(self.root, d))

    def test_checksum_failure_never_activates_source(self):
        d = self.fixture(); d['archive_sha256'] = '0' * 64
        with patched(download=lambda *a: None):
            with self.assertRaises(ValueError):
                m.stage(self.root, d)
        self.assertFalse(os.path.lexists(os.path.join(self.root, 'current')))

    def test_traversal_and_symlinks_are_rejected(self):
        for kind in ('traversal', 'symlink'):
            info = tarfile.TarInfo('nzbhydra-' + 'a' * 40 + ('/../escape' if kind == 'traversal' else '/libs/link'))
            if kind == 'symlink':
                info.type = tarfile.SYMTYPE; info.linkname = '/etc/passwd'
            d = self.fixture(extra=info)
            with self.assertRaises(ValueError):
                m.stage(self.root, d)

    def test_tampered_installed_file_fails_verification(self):
        path = m.stage(self.root, self.fixture())
        with open(os.path.join(path, 'nzbhydra.py'), 'w') as stream:
            stream.write('tampered')
        with self.assertRaises(ValueError):
            m.verify_release(path)

    def test_new_runtime_is_not_installed_into_legacy_image(self):
        d = self.fixture(); d['application_version'] = '0.3.0'
        with self.assertRaises(ValueError):
            m.stage(self.root, d)

    def test_failed_health_restores_matching_code_and_data(self):
        old = self.fixture(); oldpath = m.stage(self.root, old)
        m.select(self.root, 'current', oldpath)
        m.write_json(os.path.join(self.root, 'state', 'selected.json'), old)
        new = self.fixture('b' * 40)
        data = os.path.join(self.root, 'synthetic-data'); os.mkdir(data)
        with open(os.path.join(data, 'database'), 'w') as stream:
            stream.write('before')
        calls = []
        def health(d, **kwargs):
            if d == new:
                with open(os.path.join(data, 'database'), 'w') as stream:
                    stream.write('changed-during-startup')
                raise RuntimeError('Synthetic unhealthy build')
        with patched(DATA=data, service=lambda up: calls.append(up),
                     configure_service=lambda root: None, health=health,
                     restore_data_ownership=lambda path: None):
            with self.assertRaises(RuntimeError):
                m.apply(self.root, new)
        self.assertEqual(oldpath, os.path.realpath(os.path.join(self.root, 'current')))
        self.assertEqual(old, m.read_json(os.path.join(self.root, 'state', 'selected.json')))
        with open(os.path.join(data, 'database')) as stream:
            self.assertEqual('before', stream.read())
        self.assertEqual([False, True, False, True], calls)

    def test_interrupted_deployment_is_not_silently_promoted(self):
        m.write_json(os.path.join(self.root, 'state', 'pending.json'), self.fixture())
        with self.assertRaises(RuntimeError):
            m.boot(self.root)


if __name__ == '__main__':
    unittest.main(verbosity=2)
