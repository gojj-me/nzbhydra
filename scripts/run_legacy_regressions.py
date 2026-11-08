#!/usr/bin/env python3
"""Run selected legacy tests in an already installed, explicitly pinned Docker image."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, help='Existing local sha256 image ID; never pulled')
    parser.add_argument('--timeout', type=int, default=600, help='Whole run limit in seconds')
    args = parser.parse_args()
    import re
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', args.image) or args.timeout <= 0:
        parser.error('Use a full sha256 image ID and a positive timeout')
    subprocess.run(['docker', 'image', 'inspect', args.image], check=True, stdout=subprocess.DEVNULL)
    name = 'nzbhydra-regression-' + uuid.uuid4().hex
    # A temporary copy avoids exposing checkout-private files or requiring shared filesystem paths.
    with tempfile.TemporaryDirectory(prefix='nzbhydra-regression-') as folder:
        archive = Path(folder) / 'source.tar'
        subprocess.run(['git', '-C', str(ROOT), 'archive', '--format=tar', '-o', str(archive), 'HEAD'], check=True)
        revision = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
        print(json.dumps({'source_commit': revision, 'image_id': args.image}), flush=True)
        command = ['docker', 'run', '--name', name, '--label', 'nzbhydra.test=legacy-regression',
                   '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                   '--pids-limit', '128', '--memory', '512m', '--cpus', '2',
                   '--tmpfs', '/tmp:rw,mode=1777,size=256m', '--tmpfs', '/work:rw,size=128m',
                   '-e', 'NZBHYDRA_SESSION_DIR=/tmp/session', '-e', 'PYTHONDONTWRITEBYTECODE=1',
                   '--entrypoint', '/bin/sh', '-i', args.image, '-c',
                   'tar -xf - -C /work && cd /work && python -B scripts/legacy_regression_suite.py']
        try:
            with archive.open('rb') as source:
                subprocess.run(command, stdin=source, check=True, timeout=args.timeout)
        finally:
            # Exact generated identity only. --rm alone misses containers left in Created state.
            found = subprocess.run(['docker', 'inspect', name], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            if found.returncode == 0:
                info = json.loads(found.stdout)[0]
                if info['Config']['Labels'].get('nzbhydra.test') != 'legacy-regression':
                    raise RuntimeError('Unexpected container identity; refusing cleanup')
                subprocess.run(['docker', 'rm', '-f', '-v', name], check=True, stdout=subprocess.DEVNULL)
            remaining = subprocess.run(['docker', 'inspect', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if remaining.returncode == 0:
                raise RuntimeError('Disposable container cleanup failed')


if __name__ == '__main__':
    main()
