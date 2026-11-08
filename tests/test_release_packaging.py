import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import sys
from test_maintenance import m

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'scripts'))
spec = importlib.util.spec_from_file_location('packager', root / 'scripts/package_release.py')
packager = importlib.util.module_from_spec(spec); spec.loader.exec_module(packager)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp()); self.repo = self.temp / 'repo'; self.repo.mkdir()
        subprocess.check_call(['git', 'init', '--quiet', str(self.repo)])
        for name in ('nzbhydra.py', 'LICENSE'):
            (self.repo / name).write_text('synthetic source\n')
        (self.repo / 'version.txt').write_text('0.2.300')
        (self.repo / 'changelog.md').write_text('# Changes\n----------\n### 0.2.300\nFixed: synthetic\n')
        (self.repo / 'release-fixes.json').write_text('[9]')
        for folder in ('libs', 'static', 'templates', 'onlinehelp', 'nzbhydra'):
            (self.repo / folder).mkdir(); (self.repo / folder / 'fixture.txt').write_text('synthetic')
        (self.repo / 'maintenance').mkdir()
        for name in ('maintenance.py', 'tool_launcher.py', 'bootstrap.sh', '50-nzbhydra-maintenance.sh'):
            shutil.copy2(root / 'maintenance' / name, self.repo / 'maintenance' / name)
        notices = self.repo / 'libs/third_party_notices'; notices.mkdir()
        (notices / 'README.md').write_text('synthetic notice index')
        (notices / 'SYNTHETIC_LICENSE.txt').write_text('synthetic attribution')
        import hashlib
        manifest = {'schema': 1, 'components': [{'id': 'synthetic',
            'notices': [{'file': 'SYNTHETIC_LICENSE.txt',
                'sha256': hashlib.sha256(b'synthetic attribution').hexdigest()}]}]}
        (notices / 'manifest.json').write_text(json.dumps(manifest))
        (self.repo / '.env').write_text('INVENTED_TEST_VALUE=not-a-credential')
        self.git('add', '.')
        self.git('-c', 'user.name=Synthetic test', '-c', 'user.email=test@example.invalid', 'commit', '--quiet', '-m', 'synthetic')
        self.git('tag', '0.2.300')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args])

    def tearDown(self): shutil.rmtree(self.temp)

    def test_reproducible_artifacts_can_be_staged_by_updater(self):
        a = packager.build(self.repo, '0.2.300', self.temp / 'a')
        b = packager.build(self.repo, '0.2.300', self.temp / 'b')
        self.assertEqual(a, b)
        manifest = json.loads((self.temp / 'a/source-manifest.json').read_text())
        self.assertNotIn('.env', manifest)
        self.assertIn('libs/fixture.txt', manifest)
        self.assertIn('maintenance/tool_launcher.py', manifest)
        target = str(self.temp / 'installed'); m.setup(target)
        shutil.copy2(self.temp / 'a' / a['archive_asset'], Path(target) / 'cache' / (a['source_commit'] + '.tar.gz'))
        path = m.stage(target, a)
        self.assertEqual(a, m.verify_release(path))
        self.assertFalse(os.path.exists(os.path.join(path, '.env')))

    def changed_notice_tag(self):
        self.git('add', '-A')
        self.git('-c', 'user.name=Synthetic test', '-c', 'user.email=test@example.invalid',
                 'commit', '--quiet', '-m', 'synthetic notice change')
        self.git('tag', '-f', '0.2.300')

    def test_missing_notice_manifest_blocks_maintenance_release(self):
        (self.repo / 'libs/third_party_notices/manifest.json').unlink()
        self.changed_notice_tag()
        with self.assertRaises(ValueError):
            packager.build(self.repo, '0.2.300', self.temp / 'no-manifest')

    def test_non_lf_notice_bytes_survive_archive_and_stage(self):
        import hashlib
        body = b'synthetic attribution' + bytes([13, 10]) + b'second line' + bytes([13, 10])
        (self.repo / '.gitattributes').write_text('* text=auto eol=lf' + chr(10) + 'libs/third_party_notices/** -text' + chr(10))
        (self.repo / 'libs/third_party_notices/SYNTHETIC_LICENSE.txt').write_bytes(body)
        path = self.repo / 'libs/third_party_notices/manifest.json'
        manifest = json.loads(path.read_text())
        manifest['components'][0]['notices'][0]['sha256'] = hashlib.sha256(body).hexdigest()
        path.write_text(json.dumps(manifest))
        self.changed_notice_tag()
        descriptor = packager.build(self.repo, '0.2.300', self.temp / 'crlf')
        target = str(self.temp / 'crlf-installed'); m.setup(target)
        shutil.copy2(self.temp / 'crlf' / descriptor['archive_asset'],
                     Path(target) / 'cache' / (descriptor['source_commit'] + '.tar.gz'))
        installed = m.stage(target, descriptor)
        self.assertEqual(body, (Path(installed) / 'libs/third_party_notices/SYNTHETIC_LICENSE.txt').read_bytes())

    def test_missing_notice_blocks_release(self):
        (self.repo / 'libs/third_party_notices/SYNTHETIC_LICENSE.txt').unlink()
        self.changed_notice_tag()
        with self.assertRaises(ValueError):
            packager.build(self.repo, '0.2.300', self.temp / 'missing')

    def test_changed_notice_blocks_release(self):
        (self.repo / 'libs/third_party_notices/SYNTHETIC_LICENSE.txt').write_text('altered synthetic attribution')
        self.changed_notice_tag()
        with self.assertRaises(ValueError):
            packager.build(self.repo, '0.2.300', self.temp / 'changed')

    def test_unlisted_notice_directory_content_blocks_release(self):
        (self.repo / 'libs/third_party_notices/unlisted.txt').write_text('synthetic unrelated data')
        self.changed_notice_tag()
        with self.assertRaises(ValueError):
            packager.build(self.repo, '0.2.300', self.temp / 'unlisted')

    def test_version_mismatch_prevents_packaging(self):
        self.git('tag', '0.2.301')
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            packager.build(self.repo, '0.2.301', self.temp / 'bad')


if __name__ == '__main__': unittest.main(verbosity=2)
