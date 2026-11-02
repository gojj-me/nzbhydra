from __future__ import print_function
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import unittest
from test_maintenance import m, patched
sys.path.insert(0, os.path.dirname(m.__file__))
import tool_launcher as tools


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(); m.setup(self.root)
        self.sha = 'a' * 40
        self.descriptor = {'source_commit': self.sha, 'archive_sha256': 'b' * 64,
                           'channel': 'stable', 'application_version': '0.2.300',
                           'target_release': '0.2.300', 'included_fixes': [9],
                           'archive_asset': 'nzbhydra-0.2.300.tar.gz'}
        self.release = {'tag_name': '0.2.300', 'draft': False, 'prerelease': False,
                        'assets': [{'name': n, 'state': 'uploaded', 'browser_download_url':
                                    'https://github.com/gojj-me/nzbhydra/releases/download/0.2.300/' + n}
                                   for n in ['maintenance.json', 'nzbhydra-0.2.300.tar.gz']]}

    def tearDown(self): shutil.rmtree(self.root)

    def remote(self, url):
        if '/releases/tags/' in url: return self.release
        if url.endswith('maintenance.json'): return self.descriptor
        if '/git/ref/' in url: return {'object': {'type': 'commit', 'sha': self.sha}}
        if '/releases?' in url: return [self.release]
        raise AssertionError(url)

    def test_stable_descriptor_and_tag_agree(self):
        with patched(remote_json=self.remote):
            self.assertEqual(self.descriptor, m.resolve_release('0.2.300'))

    def test_annotated_tag_is_resolved_to_commit(self):
        def remote(url):
            if '/git/ref/' in url: return {'object': {'type': 'tag', 'sha': 'd' * 40}}
            if '/git/tags/' in url: return {'object': {'type': 'commit', 'sha': self.sha}}
            return self.remote(url)
        with patched(remote_json=remote):
            self.assertEqual(self.descriptor, m.resolve_release('0.2.300'))

    def test_mismatched_tag_commit_rejected(self):
        self.descriptor['source_commit'] = 'c' * 40
        with patched(remote_json=self.remote):
            with self.assertRaises(ValueError): m.resolve_release('0.2.300')

    def test_draft_prerelease_missing_asset_and_foreign_origin_rejected(self):
        import copy
        original = copy.deepcopy(self.release)
        for problem in ('draft', 'prerelease', 'missing', 'origin'):
            self.release = copy.deepcopy(original)
            if problem in ('draft', 'prerelease'): self.release[problem] = True
            elif problem == 'missing': self.release['assets'] = []
            else: self.release['assets'][0]['browser_download_url'] = 'https://example.invalid/metadata'
            with patched(remote_json=self.remote):
                with self.assertRaises(ValueError): m.resolve_release('0.2.300')

    def test_new_runtime_release_rejected(self):
        with self.assertRaises(ValueError): m.resolve_release('0.3.0')

    def test_default_policy_and_pinned_test_prevent_automatic_activation(self):
        current = dict(self.descriptor, channel='test')
        m.write_json(os.path.join(self.root, 'state', 'selected.json'), current)
        def no_network(*a): raise AssertionError('Unexpected network')
        with patched(remote_json=no_network):
            self.assertFalse(m.update_stable(self.root, automatic=True)['updated'])
            m.policy(self.root, 'auto-stable')
            self.assertFalse(m.update_stable(self.root, automatic=True)['updated'])

    def test_opt_in_stable_activation(self):
        current = dict(self.descriptor, application_version='0.2.299', target_release='0.2.299')
        m.write_json(os.path.join(self.root, 'state', 'selected.json'), current)
        m.policy(self.root, 'auto-stable'); applied = []
        with patched(remote_json=self.remote, apply=lambda root, d: applied.append(d)):
            self.assertTrue(m.update_stable(self.root, automatic=True)['updated'])
        self.assertEqual([self.descriptor], applied)

    def test_release_retag_and_downgrade_rejected(self):
        current = dict(self.descriptor, source_commit='c' * 40)
        for version in ('0.2.300', '0.2.301'):
            current['application_version'] = version
            m.write_json(os.path.join(self.root, 'state', 'selected.json'), current)
            with patched(remote_json=self.remote):
                with self.assertRaises(ValueError): m.update_stable(self.root, version='0.2.300')

    def test_discovery_ignores_new_runtime_and_prereleases(self):
        variants = [dict(self.release, tag_name='0.3.0'), dict(self.release, prerelease=True, tag_name='0.2.400'), self.release]
        with patched(remote_json=lambda url: variants):
            self.assertEqual('0.2.300', m.latest_release()['tag_name'])


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(); self.root = os.path.join(self.base, 'nzbhydra-maintenance'); m.setup(self.root)
        os.mkdir(os.path.join(self.base, 'custom-cont-init.d'))
        self.bootstrap = b'#!/bin/sh\nexit 0\n'
        self.hook = b'#!/bin/sh\nexit 0\n'
        for path, value in [('bootstrap.sh', self.bootstrap), ('updater/maintenance.py', b'print("baseline")\n')]:
            with open(os.path.join(self.root, path), 'wb') as f: f.write(value)
        with open(os.path.join(self.base, 'custom-cont-init.d', '50-nzbhydra-maintenance.sh'), 'wb') as f: f.write(self.hook)

    def tearDown(self): shutil.rmtree(self.base)

    def install(self, incompatible=False):
        commit = 'a' * 40; archive = os.path.join(self.base, 'tools.tar.gz')
        with open(tools.__file__.replace('.pyc', '.py'), 'rb') as f: launcher = f.read()
        values = {'maintenance.py': b'print("candidate")\n', 'bootstrap.sh': self.bootstrap,
                  '50-nzbhydra-maintenance.sh': self.hook, 'tool_launcher.py': launcher}
        if incompatible: values['bootstrap.sh'] += b'# incompatible\n'
        with tarfile.open(archive, 'w:gz') as tar:
            for name, value in values.items():
                info = tarfile.TarInfo('nzbhydra-' + commit + '/maintenance/' + name); info.size = len(value)
                tar.addfile(info, io.BytesIO(value))
        return tools.install_tools(self.root, archive, {'source_commit': commit, 'archive_sha256': tools.sha(archive)})

    def test_complete_bundle_installs_and_verifies(self):
        value = self.install()
        self.assertEqual(value, tools.active(self.root)[1])

    def test_corrupt_candidate_falls_back_to_verified_previous(self):
        self.install()
        path, _ = tools.active(self.root)
        with open(os.path.join(path, 'maintenance.py'), 'a') as f: f.write('# corrupted')
        self.assertTrue(tools.active(self.root)[1]['revision'].startswith('baseline-'))

    def test_interrupted_upgrade_uses_previous_and_explicit_recovery(self):
        self.install()
        m.write_json(os.path.join(self.root, 'state', 'tool-pending.json'), {'candidate': 'a' * 40})
        self.assertTrue(tools.active(self.root)[1]['revision'].startswith('baseline-'))
        tools.recover_tools(self.root)
        self.assertFalse(os.path.exists(os.path.join(self.root, 'state', 'tool-pending.json')))
        self.assertTrue(tools.active(self.root)[1]['revision'].startswith('baseline-'))

    def test_incompatible_startup_interface_is_rejected(self):
        with self.assertRaises(ValueError): self.install(incompatible=True)
        self.assertFalse(os.path.exists(os.path.join(self.root, 'tools', 'current')))

    def test_tampered_trusted_bootstrap_fails_closed(self):
        self.install()
        with open(os.path.join(self.root, 'bootstrap.sh'), 'a') as f: f.write('# changed')
        with self.assertRaises(RuntimeError): tools.active(self.root)
        with open(os.path.join(self.root, 'bootstrap.sh'), 'wb') as f: f.write(self.bootstrap)
        self.assertEqual('a' * 40, tools.active(self.root)[1]['revision'])


if __name__ == '__main__': unittest.main(verbosity=2)
