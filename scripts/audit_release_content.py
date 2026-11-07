#!/usr/bin/env python3
"""Inventory tracked dependency/build evidence; does not certify licensing or non-use."""
from pathlib import Path
import subprocess, re, json, hashlib, collections, argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
import os
os.chdir(root)
tracked = subprocess.check_output(['git', 'ls-files', '-z']).decode().split('\x00')
tracked = [p for p in tracked if p and Path(p).is_file()]
byroot = collections.Counter((p.split('/')[0] for p in tracked))
libraries = sorted({p.split('/')[1] for p in tracked if p.startswith('libs/') and len(p.split('/')) > 1 and (p != 'libs/__init__.py')})
references = collections.defaultdict(set)
for name in tracked:
    if not name.endswith('.py') or (not name.startswith(('nzbhydra/', 'maintenance/')) and name != 'nzbhydra.py'):
        continue
    if '/tests/' in name:
        continue
    text = Path(name).read_text(errors='replace')
    for m in re.finditer('^\\s*(?:from\\s+([A-Za-z_]\\w*)[\\w.]*\\s+import|import\\s+([A-Za-z_]\\w*))', text, re.M):
        references[m.group(1) or m.group(2)].add(name)
components = []
for name in libraries:
    prefix = 'libs/' + name
    files = [p for p in tracked if p == prefix or p.startswith(prefix + '/')]
    code = [p for p in files if p.endswith('.py')]
    notices = [p for p in files if re.search('(^|/)(?:licen[cs]e|copying|notice|copyright)(?:[._-].*)?$', p, re.I) or p.endswith('FONT_LICENSE')]
    headers = []
    license_declarations = []
    version = None
    for path in code:
        text = Path(path).read_text(errors='replace')
        if re.search('(?:__license__\\s*=|:license:|Permission is hereby granted|Redistribution and use in source)', text):
            headers.append(path)
        declaration = re.search(r"(?m)^__license__\s*=\s*['\"]([^'\"\n]{1,120})['\"]", text)
        if declaration:
            license_declarations.append({'path': path, 'text': declaration.group(1)})
        if path in [prefix, prefix + '/__init__.py', prefix + '/__about__.py', prefix + '/_version.py']:
            m = re.search('(?m)^(?:__version__|VERSION|version|__version)\\s*=\\s*([\\\'"])([^\\\'"\\n]+)\\1', text)
            if m and re.match('^[0-9][0-9A-Za-z.+_-]*$', m.group(2)):
                version = m.group(2)
    key = name[:-3] if name.endswith('.py') else name
    components.append({'component': name, 'files': len(files), 'bytes': sum((Path(p).stat().st_size for p in files)), 'declared_version': version, 'direct_application_references': sorted(references.get(key, [])), 'license_files': notices, 'license_declarations': license_declarations, 'source_license_indicators': headers})
maps = []
for name in tracked:
    if name.endswith('.map') and name.startswith('static/'):
        data = json.loads(Path(name).read_text())
        sources = []
        for i, source in enumerate(data.get('sources', [])):
            content = data.get('sourcesContent', [])[i] if i < len(data.get('sourcesContent', [])) else None
            sources.append({'path': source, 'source_embedded': content is not None, 'license_indicator': bool(content and re.search('(?i)license|copyright|permission is hereby granted', content)), 'sha256': hashlib.sha256(content.encode()).hexdigest() if content is not None else None})
        maps.append({'path': name, 'sources': sources})
report = {'schema': 1, 'base_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip(), 'method': 'Tracked-file inventory; literal header version strings and static import candidates. Absence of a direct reference is not proof of non-use; license indicators are not a license-completeness determination.', 'working_tree_changes': sorted(set(subprocess.check_output(['git', 'diff', '--name-only', 'HEAD']).decode().splitlines())), 'tracked_files_by_root': dict(sorted(byroot.items())), 'python_components': components, 'frontend_source_maps': maps, 'frontend_declared_dependencies': json.loads(Path('bower.json').read_text())['dependencies'], 'frontend_build_dependencies': json.loads(Path('package.json').read_text())['devDependencies']}
args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
print('Inventoried %d Python components, %d frontend declarations and %d source maps' % (len(components), len(report['frontend_declared_dependencies']), len(maps)))
