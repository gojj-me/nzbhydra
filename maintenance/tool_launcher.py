#!/usr/bin/env python
"""Stable interface-1 launcher. Trust starts with the reviewed local installation."""
from __future__ import print_function
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

FILES = ('maintenance.py', 'bootstrap.sh', '50-nzbhydra-maintenance.sh', 'tool_launcher.py')
ROOT = '/config/nzbhydra-maintenance'


def sha(path):
    with open(path, 'rb') as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def read(path):
    with open(path) as stream:
        return json.load(stream)


def replace(path, value):
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(path))
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, sort_keys=True); stream.flush(); os.fsync(stream.fileno())
    os.chmod(temporary, 0o644)
    os.rename(temporary, path)


def point(root, name, target):
    path = os.path.join(root, name); temporary = path + '.new'
    if os.path.lexists(temporary): os.unlink(temporary)
    os.symlink(os.path.basename(target), temporary)
    os.rename(temporary, path)


def verify(path):
    if os.path.islink(os.path.join(path, 'TOOLS.json')):
        raise ValueError('Tool manifest must not be a symlink')
    value = read(os.path.join(path, 'TOOLS.json'))
    if value.get('interface') != 1 or set(value.get('files', {})) != set(FILES):
        raise ValueError('Unsupported maintenance interface/manifest')
    if set(os.listdir(path)) != set(FILES) | set(['TOOLS.json']):
        raise ValueError('Unexpected maintenance bundle content')
    for name in FILES:
        full = os.path.join(path, name)
        if os.path.islink(full) or not os.path.isfile(full) or sha(full) != value['files'][name]:
            raise ValueError('Maintenance bundle failed verification: ' + name)
    return value


def active(root):
    tools = os.path.join(root, 'tools')
    pending = os.path.join(root, 'state', 'tool-pending.json')
    names = ('previous',) if os.path.exists(pending) else ('current', 'previous')
    for name in names:
        path = os.path.realpath(os.path.join(tools, name))
        if not path.startswith(os.path.realpath(tools) + os.sep): continue
        try:
            value = verify(path)
            for filename, installed in [('bootstrap.sh', os.path.join(root, 'bootstrap.sh')),
                                        ('50-nzbhydra-maintenance.sh', os.path.join(os.path.dirname(root), 'custom-cont-init.d', '50-nzbhydra-maintenance.sh')),
                                        ('tool_launcher.py', os.path.join(root, 'updater', 'maintenance.py'))]:
                if sha(installed) != value['files'][filename]:
                    raise ValueError('Trusted startup interface changed: ' + filename)
            return path, value
        except (IOError, ValueError, OSError):
            continue
    raise RuntimeError('No verified maintenance tool version; restore the trusted startup interface from backup')


def recover_tools(root):
    tools = os.path.join(root, 'tools')
    path = os.path.realpath(os.path.join(tools, 'previous'))
    value = verify(path)
    if not path.startswith(os.path.realpath(tools) + os.sep):
        raise ValueError('Previous tool selection is outside maintenance storage')
    point(tools, 'current', path)
    pending = os.path.join(root, 'state', 'tool-pending.json')
    if os.path.exists(pending): os.unlink(pending)
    return value


def install_tools(root, archive, descriptor):
    if sha(archive) != descriptor['archive_sha256']:
        raise ValueError('Maintenance source archive checksum mismatch')
    tools = os.path.join(root, 'tools')
    if not os.path.isdir(tools): os.makedirs(tools, 0o755)
    revision = descriptor['source_commit']
    target = os.path.join(tools, revision)
    staged = tempfile.mkdtemp(prefix='.tools-', dir=tools)
    try:
        found = set()
        with tarfile.open(archive, 'r:gz') as bundle:
            for member in bundle:
                pieces = member.name.split('/')
                if len(pieces) == 3 and pieces[0].endswith('-' + revision) and pieces[1] == 'maintenance' and pieces[2] in FILES:
                    name = pieces[2]
                    if name in found or not member.isfile() or member.size > 1024 * 1024:
                        raise ValueError('Invalid maintenance source entry')
                    found.add(name)
                    source = bundle.extractfile(member)
                    try:
                        with open(os.path.join(staged, name), 'wb') as output:
                            shutil.copyfileobj(source, output)
                    finally: source.close()
        if found != set(FILES): raise ValueError('Maintenance source is incomplete')
        for name in ('maintenance.py', 'tool_launcher.py'):
            with open(os.path.join(staged, name), 'rb') as stream:
                compile(stream.read(), name, 'exec')
        for name in ('bootstrap.sh', '50-nzbhydra-maintenance.sh'):
            subprocess.check_call(['bash', '-n', os.path.join(staged, name)])
        with open(os.devnull, 'w') as sink:
            subprocess.check_call([sys.executable, '-B', os.path.join(staged, 'maintenance.py'), '--help'], stdout=sink)
        # Interface 1 is fixed: changing the trusted launcher/hook requires a separate migration.
        expected = [('bootstrap.sh', os.path.join(root, 'bootstrap.sh')),
                    ('50-nzbhydra-maintenance.sh', os.path.join(os.path.dirname(root), 'custom-cont-init.d', '50-nzbhydra-maintenance.sh'))]
        for name, path in expected:
            if sha(path) != sha(os.path.join(staged, name)):
                raise ValueError('Candidate requires an incompatible startup interface')
        launcher = os.path.join(root, 'updater', 'maintenance.py')
        if os.path.islink(os.path.join(tools, 'current')):
            old, _ = active(root)
            if sha(launcher) != sha(os.path.join(staged, 'tool_launcher.py')):
                raise ValueError('Candidate changes the trusted launcher')
        else:
            # Preserve the original flat tool as a verified recovery bundle.
            old = os.path.join(tools, 'baseline-' + sha(launcher))
            if not os.path.isdir(old):
                os.makedirs(old, 0o755)
                shutil.copy2(launcher, os.path.join(old, 'maintenance.py'))
                for name in FILES[1:]: shutil.copy2(os.path.join(staged, name), os.path.join(old, name))
                replace(os.path.join(old, 'TOOLS.json'), {'interface': 1, 'revision': os.path.basename(old), 'files': dict((n, sha(os.path.join(old, n))) for n in FILES)})
        value = {'interface': 1, 'revision': revision, 'files': dict((n, sha(os.path.join(staged, n))) for n in FILES)}
        replace(os.path.join(staged, 'TOOLS.json'), value)
        os.chmod(staged, 0o755)
        for name in FILES: os.chmod(os.path.join(staged, name), 0o644)
        if os.path.isdir(target):
            if verify(target) != value: raise ValueError('Tool revision already exists with different contents')
        else:
            os.rename(staged, target)
        point(tools, 'previous', old)
        replace(os.path.join(root, 'state', 'tool-pending.json'), {'candidate': revision, 'previous': os.path.basename(old)})
        point(tools, 'current', target)
        # One-time installation of the fixed launcher is the final executable-file change.
        fd, temporary = tempfile.mkstemp(dir=os.path.dirname(launcher))
        with os.fdopen(fd, 'wb') as output, open(os.path.join(target, 'tool_launcher.py'), 'rb') as source:
            output.write(source.read()); output.flush(); os.fsync(output.fileno())
        os.chmod(temporary, 0o644); os.rename(temporary, launcher)
        verify(target)
        os.unlink(os.path.join(root, 'state', 'tool-pending.json'))
        active(root)
        return value
    finally:
        if os.path.isdir(staged): shutil.rmtree(staged)


def main():
    root = ROOT
    args = sys.argv[1:]
    if '--root' in args: root = args[args.index('--root') + 1]
    if 'tools-recover' in args:
        import fcntl
        with open(os.path.join(root, 'state', 'update.lock'), 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            print(json.dumps(recover_tools(root), sort_keys=True)); return
    path, value = active(root)
    if '--verify-tools' in args:
        print(json.dumps(value, sort_keys=True)); return
    os.environ['NZBHYDRA_TOOL_REVISION'] = value['revision']
    os.execv(sys.executable, [sys.executable, '-B', os.path.join(path, 'maintenance.py')] + args)


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print('Maintenance launcher failed: %s' % error, file=sys.stderr); sys.exit(1)
