#!/usr/bin/env python
"""Persistent legacy-image maintenance. Python 2.7/3, standard library only."""
from __future__ import print_function
import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
try:
    import urllib2 as http
    from urlparse import urlparse
except ImportError:
    import urllib.request as http
    import urllib.error
    from urllib.parse import urlparse

ROOT = '/config/nzbhydra-maintenance'
SERVICE = '/var/run/s6/services/hydra'
DATA = '/config/hydra'
SOURCE_ROOTS = ('libs', 'nzbhydra', 'static', 'templates', 'onlinehelp')
SOURCE_FILES = ('nzbhydra.py', 'version.txt', 'changelog.md', 'LICENSE')
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024


def read_json(path):
    with open(path) as stream:
        return json.load(stream)


def write_json(path, value):
    data = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode('utf-8')
    atomic_write(path, data, 0o600)


def atomic_write(path, data, mode=0o644):
    fd, temporary = tempfile.mkstemp(prefix='.maintenance-', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.rename(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def digest(path):
    result = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def validate_descriptor(value):
    if not re.match(r'^[0-9a-f]{40}$', value.get('source_commit', '')):
        raise ValueError('An immutable 40-character commit is required')
    if not re.match(r'^[0-9a-f]{64}$', value.get('archive_sha256', '')):
        raise ValueError('A pinned archive SHA-256 is required')
    if value.get('channel') not in ('test', 'stable'):
        raise ValueError('Unknown deployment channel')
    if not re.match(r'^0\.2\.[0-9]+$', value.get('application_version', '')):
        raise ValueError('Only legacy 0.2.x application builds may use this updater')
    if value.get('channel') == 'stable' and value.get('target_release') != value['application_version']:
        raise ValueError('Stable application and target versions must agree')
    fixes = value.get('included_fixes', [])
    if not isinstance(fixes, list) or any(not isinstance(x, int) or x <= 0 for x in fixes):
        raise ValueError('Fix references must be positive issue numbers')
    return value


def download(url, destination):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('codeload.github.com', 'api.github.com'):
        raise ValueError('Untrusted download origin')
    partial = destination + '.partial'
    try:
        result = subprocess.call(['curl', '--silent', '--show-error', '--fail',
                                  '--proto', '=https', '--proto-redir', '=https',
                                  '--connect-timeout', '10', '--max-time', '120',
                                  '--retry', '2', '--max-filesize', str(MAX_ARCHIVE),
                                  '--output', partial, url])
        if result != 0:
            raise RuntimeError('Verified HTTPS download failed (curl %d)' % result)
        if os.path.getsize(partial) > MAX_ARCHIVE:
            raise ValueError('Download is too large')
        os.rename(partial, destination)
    finally:
        if os.path.exists(partial):
            os.unlink(partial)


def extract_source(archive, destination, commit):
    """Extract regular allowlisted source files only; reject links and traversal."""
    total = 0
    count = 0
    seen = set()
    with tarfile.open(archive, 'r:gz') as bundle:
        for member in bundle:
            parts = member.name.split('/')
            if any(x in ('.', '..') for x in parts) or member.name.startswith('/'):
                raise ValueError('Unsafe archive path')
            if not parts[0].endswith('-' + commit):
                raise ValueError('Archive source revision does not match the descriptor')
            if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                raise ValueError('Archive contains a link or special file')
            if len(parts) < 2 or not parts[1]:
                continue
            relative = '/'.join(parts[1:]).rstrip('/')
            if relative in seen:
                raise ValueError('Duplicate archive path')
            seen.add(relative)
            count += 1
            total += member.size
            if count > 20000 or total > MAX_EXPANDED:
                raise ValueError('Expanded archive limit exceeded')
            allowed = parts[1] in SOURCE_ROOTS or relative in SOURCE_FILES
            if not allowed or any(x in ('tests', 'test', 'testsuite', '__pycache__', '.git') for x in parts[1:]):
                continue
            if relative.endswith(('.pyc', '.pyo')):
                continue
            target = os.path.join(destination, relative)
            if member.isdir():
                if not os.path.isdir(target):
                    os.makedirs(target, 0o755)
            else:
                parent = os.path.dirname(target)
                if not os.path.isdir(parent):
                    os.makedirs(parent, 0o755)
                with contextlib.closing(bundle.extractfile(member)) as source, open(target, 'wb') as output:
                    shutil.copyfileobj(source, output)
                os.chmod(target, 0o644)
    for required in SOURCE_FILES:
        if not os.path.isfile(os.path.join(destination, required)):
            raise ValueError('Missing required application file: ' + required)


def release_path(root, descriptor):
    return os.path.join(root, 'releases', descriptor['source_commit'])


def verify_release(path):
    manifest = read_json(os.path.join(path, 'FILES.json'))
    if not manifest or 'BUILD.json' not in manifest:
        raise ValueError('Missing release manifest')
    for relative, expected in manifest.items():
        if relative.startswith('/') or '..' in relative.split('/'):
            raise ValueError('Unsafe manifest path')
        full = os.path.join(path, relative)
        if os.path.islink(full) or not os.path.isfile(full) or digest(full) != expected:
            raise ValueError('Installed release verification failed: ' + relative)
    return read_json(os.path.join(path, 'BUILD.json'))


def stage(root, descriptor):
    validate_descriptor(descriptor)
    final = release_path(root, descriptor)
    if os.path.isdir(final):
        info = verify_release(final)
        if info != descriptor:
            raise ValueError('Existing revision has different deployment metadata')
        return final
    archive = os.path.join(root, 'cache', descriptor['source_commit'] + '.tar.gz')
    if not os.path.isfile(archive) or digest(archive) != descriptor['archive_sha256']:
        url = 'https://codeload.github.com/gojj-me/nzbhydra/tar.gz/' + descriptor['source_commit']
        download(url, archive)
    if digest(archive) != descriptor['archive_sha256']:
        raise ValueError('Downloaded archive checksum mismatch')
    temporary = tempfile.mkdtemp(prefix='.stage-', dir=os.path.join(root, 'releases'))
    try:
        extract_source(archive, temporary, descriptor['source_commit'])
        with open(os.path.join(temporary, 'version.txt')) as stream:
            if stream.read().strip() != descriptor['application_version']:
                raise ValueError('Application version does not match descriptor')
        write_json(os.path.join(temporary, 'BUILD.json'), descriptor)
        os.chmod(os.path.join(temporary, 'BUILD.json'), 0o644)
        hashes = {}
        for directory, _, filenames in os.walk(temporary):
            for filename in filenames:
                full = os.path.join(directory, filename)
                hashes[os.path.relpath(full, temporary)] = digest(full)
        write_json(os.path.join(temporary, 'FILES.json'), hashes)
        os.chmod(os.path.join(temporary, 'FILES.json'), 0o644)
        os.chmod(temporary, 0o755)
        os.rename(temporary, final)
        return final
    finally:
        if os.path.isdir(temporary):
            shutil.rmtree(temporary)


def select(root, name, path):
    root = os.path.realpath(root)
    path = os.path.realpath(path)
    link = os.path.join(root, name)
    temporary = link + '.new'
    if os.path.lexists(temporary):
        os.unlink(temporary)
    os.symlink(os.path.relpath(path, root), temporary)
    os.rename(temporary, link)


def configure_service(root):
    # Runtime service dir is a copy of /etc/services.d in this s6-overlay image.
    text = '''#!/usr/bin/with-contenv bash
set -eu
export NZBHYDRA_SESSION_DIR=/config/hydra/flask_session
exec s6-setuidgid abc python %s/current/nzbhydra.py --nobrowser --config /config/hydra/settings.cfg --database /config/hydra/nzbhydra.db --logfile /config/hydra/nzbhydra.log
''' % root
    for path in ('/etc/services.d/hydra/run', SERVICE + '/run'):
        if os.path.isdir(os.path.dirname(path)):
            atomic_write(path, text.encode('utf-8'), 0o755)


def service(up):
    subprocess.check_call(['s6-svc', '-u' if up else '-d', SERVICE])
    limit = time.time() + 30
    while time.time() < limit:
        state = subprocess.check_output(['s6-svstat', SERVICE]).decode('utf-8')
        if state.startswith('up ' if up else 'down '):
            return
        time.sleep(0.2)
    raise RuntimeError('Application service did not change state within 30 seconds')


def restore_data_ownership(path):
    subprocess.check_call(['chown', '-R', 'abc:abc', path])


class NoRedirect(http.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def health(descriptor, timeout=60):
    settings = read_json('/config/hydra/settings.cfg')['main']
    url = '%s://127.0.0.1:%s%s/' % ('https' if settings.get('ssl') else 'http',
                                    settings.get('port', 5075), (settings.get('urlBase') or '').rstrip('/'))
    opener = http.build_opener(NoRedirect())
    limit = time.time() + timeout
    while time.time() < limit:
        response = None
        try:
            try:
                response = opener.open(url, timeout=3)
            except http.HTTPError as error:
                response = error
            if response.code in (200, 301, 302, 303, 401, 403) and response.headers.get('X-NZBHydra-Build') == descriptor['source_commit']:
                return
        except (IOError, OSError):
            pass
        finally:
            if response is not None:
                response.close()
        time.sleep(1)
    raise RuntimeError('Application build health check failed')


def setup(root):
    for name in ('releases', 'cache', 'state', 'backups', 'updater'):
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            os.makedirs(path)
    os.chmod(root, 0o755)
    for directory, dirs, files in os.walk(root):
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            os.chown(directory, 0, 0)
            for filename in files:
                full = os.path.join(directory, filename)
                if not os.path.islink(full):
                    os.chown(full, 0, 0)
    for name in ('state', 'backups', 'cache'):
        os.chmod(os.path.join(root, name), 0o700)


@contextlib.contextmanager
def locked(root):
    with open(os.path.join(root, 'state', 'update.lock'), 'a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise RuntimeError('Another maintenance operation is active')
        yield


def apply(root, descriptor):
    target = stage(root, descriptor)  # No service disruption before validation.
    current = os.path.join(root, 'current')
    previous = os.path.realpath(current) if os.path.exists(current) else '/app/hydra'
    old_descriptor = read_json(os.path.join(root, 'state', 'selected.json')) if os.path.exists(os.path.join(root, 'state', 'selected.json')) else None
    if old_descriptor == descriptor and os.path.realpath(current) == target:
        health(descriptor)
        return descriptor
    service(False)
    stamp = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%S%fZ')
    backup = os.path.join(root, 'backups', stamp)
    os.makedirs(backup, 0o700)
    backup_ready = False
    try:
        # Snapshot all application data while its writer is stopped; preserve WALs.
        shutil.copytree(DATA, os.path.join(backup, 'data'))
        write_json(os.path.join(backup, 'selection.json'), {'path': previous, 'descriptor': old_descriptor})
        backup_ready = True
        write_json(os.path.join(root, 'state', 'transaction.json'), {'backup': backup, 'previous': previous, 'previous_descriptor': old_descriptor})
        select(root, 'previous', previous)
        select(root, 'current', target)
        configure_service(root)
        write_json(os.path.join(root, 'state', 'pending.json'), descriptor)
        service(True)
        health(descriptor)
        write_json(os.path.join(root, 'state', 'selected.json'), descriptor)
        os.unlink(os.path.join(root, 'state', 'pending.json'))
        write_json(os.path.join(root, 'state', 'last-transaction.json'), {'backup': backup, 'previous': previous, 'previous_descriptor': old_descriptor, 'installed': descriptor})
        os.unlink(os.path.join(root, 'state', 'transaction.json'))
    except Exception:
        if not backup_ready:
            service(True)
            raise
        service(False)
        select(root, 'current', previous)
        if old_descriptor is None:
            original = os.path.join(root, 'state', 'original-run')
            if os.path.isfile(original):
                for path in ('/etc/services.d/hydra/run', SERVICE + '/run'):
                    atomic_write(path, open(original, 'rb').read(), 0o755)
        else:
            configure_service(root)
        # Code and data must roll back together, including possible startup migrations.
        failed = os.path.join(backup, 'failed-data')
        os.rename(DATA, failed)
        shutil.copytree(os.path.join(backup, 'data'), DATA)
        restore_data_ownership(DATA)
        if old_descriptor is not None:
            write_json(os.path.join(root, 'state', 'selected.json'), old_descriptor)
        else:
            selected = os.path.join(root, 'state', 'selected.json')
            if os.path.exists(selected):
                os.unlink(selected)
        pending = os.path.join(root, 'state', 'pending.json')
        if os.path.exists(pending):
            os.unlink(pending)
        service(True)
        if old_descriptor is not None:
            health(old_descriptor)
        transaction = os.path.join(root, 'state', 'transaction.json')
        if os.path.exists(transaction):
            os.unlink(transaction)
        raise
    return descriptor


def recover(root):
    """Restore an interrupted transaction's matching application/data baseline."""
    transaction_path = os.path.join(root, 'state', 'transaction.json')
    if not os.path.isfile(transaction_path):
        raise RuntimeError('No recoverable transaction record; use the verified external baseline backup')
    transaction = read_json(transaction_path)
    backup = os.path.realpath(transaction['backup'])
    if not backup.startswith(os.path.realpath(os.path.join(root, 'backups')) + os.sep):
        raise ValueError('Recovery backup is outside maintenance storage')
    selection = read_json(os.path.join(backup, 'selection.json'))
    previous = os.path.realpath(transaction['previous'])
    descriptor = transaction.get('previous_descriptor')
    if selection != {'path': transaction['previous'], 'descriptor': descriptor}:
        raise ValueError('Transaction and backup selection disagree')
    if descriptor is not None:
        validate_descriptor(descriptor)
        if previous != os.path.realpath(release_path(root, descriptor)) or verify_release(previous) != descriptor:
            raise ValueError('Previous application build failed verification')
    elif previous != '/app/hydra' or not os.path.isfile(os.path.join(root, 'state', 'original-run')):
        raise ValueError('Original image startup baseline is unavailable')
    source = os.path.join(backup, 'data')
    if not os.path.isdir(source) or not os.path.isfile(os.path.join(source, 'settings.cfg')):
        raise ValueError('Recovery data snapshot is incomplete')
    # Copy before displacing current data; a copy failure must leave it intact.
    staged = tempfile.mkdtemp(prefix='.hydra-recovery-', dir=os.path.dirname(DATA))
    shutil.rmtree(staged)
    try:
        shutil.copytree(source, staged)
        restore_data_ownership(staged)
        service(False)
        if os.path.exists(DATA):
            displaced = os.path.join(backup, 'displaced-' + str(int(time.time() * 1000000)))
            os.rename(DATA, displaced)
        os.rename(staged, DATA)
        select(root, 'current', previous)
        if descriptor is None:
            with open(os.path.join(root, 'state', 'original-run'), 'rb') as stream:
                script = stream.read()
            for path in ('/etc/services.d/hydra/run', SERVICE + '/run'):
                atomic_write(path, script, 0o755)
            # Return recreation startup to the stock image for this baseline.
            hook = '/config/custom-cont-init.d/50-nzbhydra-maintenance.sh'
            if os.path.isfile(hook):
                os.rename(hook, os.path.join(root, 'state', 'recovered-startup-hook'))
            selected = os.path.join(root, 'state', 'selected.json')
            if os.path.exists(selected):
                os.unlink(selected)
        else:
            configure_service(root)
            write_json(os.path.join(root, 'state', 'selected.json'), descriptor)
        service(True)
        if descriptor is not None:
            health(descriptor)
        for name in ('pending.json', 'transaction.json'):
            path = os.path.join(root, 'state', name)
            if os.path.exists(path):
                os.unlink(path)
        return {'recovered': descriptor, 'baseline': previous}
    finally:
        if os.path.isdir(staged):
            shutil.rmtree(staged)


def boot(root):
    selected_path = os.path.join(root, 'state', 'selected.json')
    pending_path = os.path.join(root, 'state', 'pending.json')
    if os.path.exists(pending_path):
        raise RuntimeError('Interrupted deployment requires recovery; refusing an unverified selection')
    if not os.path.isfile(selected_path):
        raise RuntimeError('No selected build; refusing uncontrolled startup')
    descriptor = validate_descriptor(read_json(selected_path))
    try:
        target = stage(root, descriptor)
    except Exception:
        previous = os.path.realpath(os.path.join(root, 'previous'))
        old = verify_release(previous)
        validate_descriptor(old)
        target = previous
        descriptor = old
        write_json(selected_path, descriptor)
    select(root, 'current', target)
    configure_service(root)
    return descriptor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=ROOT)
    parser.add_argument('command', choices=('stage', 'apply', 'boot', 'status', 'check', 'recover'))
    parser.add_argument('--descriptor')
    args = parser.parse_args()
    if args.command == 'status':
        result = read_json(os.path.join(args.root, 'state', 'selected.json'))
        result = dict(result, verified=verify_release(os.path.join(args.root, 'current')) == result)
    elif args.command == 'check':
        # Check only: never activate a moving branch or a new runtime automatically.
        fd, path = tempfile.mkstemp(prefix='nzbhydra-stable-'); os.close(fd)
        try:
            download('https://api.github.com/repos/gojj-me/nzbhydra/releases?per_page=30', path)
            releases = [x for x in read_json(path) if not x.get('draft') and not x.get('prerelease') and re.match(r'^0\.2\.[0-9]+$', x.get('tag_name', ''))]
            result = {'stable_legacy_release': max(releases, key=lambda x: tuple(int(y) for y in x['tag_name'].split('.')))['tag_name'] if releases else None, 'activation': 'explicit only'}
        finally:
            os.unlink(path)
    else:
        setup(args.root)
        with locked(args.root):
            if args.command == 'recover':
                result = recover(args.root)
            elif args.command == 'boot':
                result = boot(args.root)
            else:
                if not args.descriptor:
                    parser.error('--descriptor is required')
                descriptor = validate_descriptor(read_json(args.descriptor))
                result = {'staged': stage(args.root, descriptor)} if args.command == 'stage' else apply(args.root, descriptor)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Maintenance failed: %s' % error, file=sys.stderr)
        sys.exit(1)
