"""Credential redaction for diagnostic text, never for live request data."""
from __future__ import absolute_import, division, print_function, unicode_literals
import re
try:
    from urllib import unquote
except ImportError:
    from urllib.parse import unquote
try:
    text_type = unicode
except NameError:
    text_type = str

_KEYS = ('apikey', 'api', 'api_key', 'api-key', 'key', 'user', 'username',
         'password', 'passwd', 'pwd', 'token', 'access_token', 'refresh_token',
         'secret', 'client_secret', 'authorization', 'proxy-authorization',
         'cookie', 'set-cookie', 'sessionid', 'signature', 'sig',
         'x-amz-signature', 'x-amz-credential', 'x-amz-security-token',
         'x-goog-signature', 'x-goog-credential')
_NORMAL_KEYS = set(re.sub(r'[^a-z0-9]', '', key) for key in _KEYS)
_KEY_PATTERN = '|'.join(re.escape(key) for key in sorted(_KEYS, key=len, reverse=True))
# Quoted values include escaped quotes/backslashes; bare values extend through
# punctuation and percent escapes, ending only at an actual text/query boundary.
_ASSIGNMENT = re.compile(
    r"""(?<![\w-])(?P<prefix>(?:[ub])?['"]?(?P<key>""" + _KEY_PATTERN +
    r""")['"]?\s*[:=]\s*)(?P<value>(?:[ub])?"(?:\\.|[^"\\])*"|(?:[ub])?'(?:\\.|[^'\\])*'|[^&\s'"<>]+)""", re.I)
_QUERY = re.compile(r'''(?P<prefix>[?&])(?P<key>[^=&#\s]+)=(?P<value>[^&\s'"<>]+)''')
_ENCODED_ASSIGNMENT = re.compile(
    r'(?P<prefix>%3f|%26|%3b|(?<![\w-]))(?P<key>' + _KEY_PATTERN + r')%3d(?:(?!%26|%23)[^\s<>])+', re.I)
_HEADERS = re.compile(r'\b(authorization|proxy-authorization|cookie|set-cookie)\s*[:=]\s*[^\r\n]+', re.I)
_USERINFO = re.compile(r'([a-z][a-z0-9+.-]*://)[^/\s]+@', re.I)
_BEARER = re.compile(r'\b(Bearer|Basic)\s+[a-z0-9._~+/%=-]+', re.I)


def normalize(key):
    return re.sub(r'[^a-z0-9]', '', unquote(as_text(key)).lower())


def is_sensitive_key(key):
    return normalize(key) in _NORMAL_KEYS


def marker(key):
    key = normalize(key)
    if key in ('api', 'apikey', 'key'):
        return '<APIKEY>'
    if key in ('user', 'username'):
        return '<USER>'
    if key in ('password', 'passwd', 'pwd'):
        return '<PASSWORD>'
    return '<REDACTED>'


def as_text(value):
    if isinstance(value, text_type):
        return value
    if isinstance(value, bytes):
        return value.decode('utf-8', 'replace')
    return text_type(value)


def redact_text(value):
    if value is None:
        return None
    try:
        value = as_text(value)
        value = _USERINFO.sub(r'\1<USER>:<PASSWORD>@', value)
        def query(match):
            if normalize(match.group('key')) in _NORMAL_KEYS:
                return match.group('prefix') + match.group('key') + '=' + marker(match.group('key'))
            return match.group(0)
        value = _QUERY.sub(query, value)
        value = _ENCODED_ASSIGNMENT.sub(lambda m: m.group('prefix') + m.group('key') + '%3D' + marker(m.group('key')), value)
        value = _ASSIGNMENT.sub(lambda m: m.group('prefix') + marker(m.group('key')), value)
        value = _HEADERS.sub(lambda m: m.group(1) + ': <REDACTED>', value)
        return _BEARER.sub(r'\1 <REDACTED>', value)
    except Exception:
        # Rendering/redaction failures must never fall back to the original text.
        return '<REDACTED: diagnostic rendering failed>'


def redact_structure(value, depth=0):
    if depth > 20:
        return '<REDACTED: nested value>'
    if isinstance(value, dict):
        return dict((key, marker(key) if normalize(key) in _NORMAL_KEYS else
                     redact_structure(item, depth + 1)) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        values = [redact_structure(item, depth + 1) for item in value]
        return tuple(values) if isinstance(value, tuple) else values
    if isinstance(value, (text_type, bytes)):
        return redact_text(value)
    return value
