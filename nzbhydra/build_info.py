"""Public identity of an immutable maintenance build (no deployment secrets)."""
import json
import os

_cached = None


def get_build_info():
    global _cached
    if _cached is None:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'BUILD.json')
        try:
            with open(path) as stream:
                value = json.load(stream)
            _cached = dict((key, value[key]) for key in
                           ('source_commit', 'application_version', 'target_release',
                            'channel', 'included_fixes') if key in value)
        except (IOError, ValueError, TypeError):
            _cached = {}
    return dict(_cached)
