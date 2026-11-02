#!/usr/bin/env python3
"""Build deterministic legacy release assets from an immutable Git tag; never publish."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

ROOTS = {'libs', 'nzbhydra', 'static', 'templates', 'onlinehelp', 'maintenance'}
FILES = {'nzbhydra.py', 'version.txt', 'changelog.md', 'LICENSE'}


def build(repo, tag, output):
    if not re.fullmatch(r'0\.2\.[0-9]+', tag):
        raise ValueError('Only numeric legacy release tags are allowed')
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args])
    commit = git('rev-parse', '--verify', 'refs/tags/' + tag + '^{commit}').decode().strip()
    version = git('show', commit + ':version.txt').decode().strip()
    log = git('show', commit + ':changelog.md').decode()
    first = re.search(r'^###\s+([^\r\n]+)', log.split('----------', 1)[-1], re.MULTILINE)
    if version != tag or not first or first.group(1).strip() != tag:
        raise ValueError('Tag, application version, and changelog must agree')
    fixes = json.loads(git('show', commit + ':release-fixes.json'))
    if not isinstance(fixes, list) or any(type(x) is not int or x <= 0 for x in fixes):
        raise ValueError('Invalid included issue references')
    output.mkdir(parents=True, exist_ok=True)
    name = 'nzbhydra-' + tag + '.tar.gz'
    archive = output / name
    hashes = {}
    source = io.BytesIO(git('archive', '--format=tar', commit))
    with archive.open('wb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as target, tarfile.open(fileobj=source, mode='r:') as bundle:
            for member in bundle:
                parts = member.name.split('/')
                if parts[0] not in ROOTS and member.name not in FILES: continue
                if any(x in ('tests', 'test', 'testsuite', '__pycache__', '.git') for x in parts): continue
                if member.name.endswith(('.pyc', '.pyo')) or member.isdir(): continue
                if not member.isfile(): raise ValueError('Non-regular release content')
                data = bundle.extractfile(member).read()
                hashes[member.name] = hashlib.sha256(data).hexdigest()
                info = tarfile.TarInfo('nzbhydra-' + commit + '/' + member.name)
                info.size = len(data); info.mode = 0o644; info.mtime = 0
                target.addfile(info, io.BytesIO(data))
    if not FILES.issubset(hashes): raise ValueError('Required application files are missing')
    descriptor = {'source_commit': commit, 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                  'application_version': tag, 'target_release': tag, 'channel': 'stable',
                  'included_fixes': fixes, 'archive_asset': name}
    for filename, value in [('maintenance.json', descriptor), ('source-manifest.json', hashes)]:
        (output / filename).write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
    (output / 'SHA256SUMS').write_text(''.join(hashlib.sha256((output / n).read_bytes()).hexdigest() + '  ' + n + '\n'
                                           for n in [name, 'maintenance.json', 'source-manifest.json']))
    return descriptor


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[1], args.tag, args.output), sort_keys=True))
