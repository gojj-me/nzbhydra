#!/usr/bin/env python3
"""Offline attribution-evidence checks; not a legal-compliance certification."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

NOTICE_ROOT = 'libs/third_party_notices'


def notice_hashes(manifest):
    if not isinstance(manifest, dict) or manifest.get('schema') != 1:
        raise ValueError('Unsupported third-party notice manifest')
    components = manifest.get('components')
    if not isinstance(components, list) or not components:
        raise ValueError('Missing third-party components')
    result = {}
    identities = set()
    for component in components:
        identity = component.get('id')
        if not isinstance(identity, str) or not identity or identity in identities:
            raise ValueError('Missing or duplicate component identity')
        identities.add(identity)
        notices = component.get('notices')
        if not isinstance(notices, list) or not notices:
            raise ValueError('Component has no restored notice')
        for notice in notices:
            name, digest = notice.get('file'), notice.get('sha256')
            if not isinstance(name, str):
                raise ValueError('Invalid notice path')
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name or str(path) != name:
                raise ValueError('Unsafe notice path')
            if not isinstance(digest, str) or len(digest) != 64 or any(x not in '0123456789abcdef' for x in digest):
                raise ValueError('Invalid notice digest')
            full = NOTICE_ROOT + '/' + name
            if full in result and result[full] != digest:
                raise ValueError('Conflicting notice hashes')
            result[full] = digest
    return result


def verify_archive_notices(hashes, manifest):
    expected = notice_hashes(manifest)
    for name, digest in expected.items():
        if hashes.get(name) != digest:
            raise ValueError('Missing or altered third-party notice: ' + name)
    allowed = set(expected) | {NOTICE_ROOT + '/manifest.json', NOTICE_ROOT + '/README.md'}
    actual = {name for name in hashes if name.startswith(NOTICE_ROOT + '/')}
    if actual != allowed:
        raise ValueError('Missing notice index or unexpected notice-directory content')


def verify_checkout(root):
    folder = root / NOTICE_ROOT
    manifest = json.loads((folder / 'manifest.json').read_text())
    expected = notice_hashes(manifest)
    for name, digest in expected.items():
        path = root / name
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Missing or altered third-party notice: ' + name)
    for name in manifest.get('original_notice_files', []):
        if not (root / name).is_file():
            raise ValueError('Original notice removed: ' + name)
    scopes = [scope for component in manifest['components'] for scope in component.get('scopes', [])]
    excluded = set(manifest.get('excluded_trivial_files', []))
    tracked = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z', 'libs']).decode().split('\0')
    for name in tracked:
        if not name or name.startswith(NOTICE_ROOT + '/') or not (root / name).is_file():
            continue
        if name in excluded:
            if (root / name).read_bytes():
                raise ValueError('Excluded namespace marker is no longer empty')
            continue
        if not any(name == scope or name.startswith(scope.rstrip('/') + '/') for scope in scopes):
            raise ValueError('Unassociated vendored file: ' + name)
    for mapfile in ('static/js/alllibs.js.map', 'static/css/alllibs.css.map'):
        data = json.loads((root / mapfile).read_text())
        for source in data['sources']:
            if mapfile + '::' + source not in scopes:
                raise ValueError('Unassociated compiled input: ' + source)
    for asset in manifest.get('compiled_assets', []):
        path = root / asset['file']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != asset['sha256']:
            raise ValueError('Compiled asset changed; review attribution: ' + asset['file'])
    for component in manifest['components']:
        for witness in component.get('source_matches', []):
            name, separator, source = witness['local'].partition('::')
            path = root / name
            if not path.is_file():
                raise ValueError('Missing attribution witness: ' + name)
            if separator:
                mapping = json.loads(path.read_text())
                contents = mapping['sourcesContent'][mapping['sources'].index(source)].encode()
            else:
                contents = path.read_bytes()
            if hashlib.sha256(contents).hexdigest() != witness['sha256']:
                raise ValueError('Attribution witness changed; review evidence: ' + name)
    return len(manifest['components']), len(expected)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    components, notices = verify_checkout(args.root)
    print('Verified %d component records and %d notice files; source-revision uncertainties remain explicit.' % (components, notices))
