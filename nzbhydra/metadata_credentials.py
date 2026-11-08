"""Read operator-owned metadata credentials without persisting/exporting them."""
from __future__ import absolute_import, division, print_function, unicode_literals
import os
import stat

DEFAULT_TMDB_KEY_FILE = '/config/nzbhydra-maintenance/secrets/tmdb-api-key'


class MetadataCredentialUnavailable(Exception):
    pass


def tmdb_api_key():
    """Explicit empty overrides fail closed; the key file is read per lookup."""
    value = os.environ.get('NZBHYDRA_TMDB_API_KEY')
    if value is None:
        path = os.environ.get('NZBHYDRA_TMDB_API_KEY_FILE', DEFAULT_TMDB_KEY_FILE)
        if not path:
            raise MetadataCredentialUnavailable()
        descriptor = None
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise MetadataCredentialUnavailable()
            with os.fdopen(descriptor, 'rb') as source:
                descriptor = None
                value = source.read(4099)
                if len(value) > 4098:
                    raise MetadataCredentialUnavailable()
        except (IOError, OSError):
            raise MetadataCredentialUnavailable()
        finally:
            if descriptor is not None:
                os.close(descriptor)
    try:
        value = value.decode('ascii') if isinstance(value, bytes) else value
        value = value.strip()
        if not value or len(value) > 4096 or any(ord(char) < 33 or ord(char) > 126 for char in value):
            raise MetadataCredentialUnavailable()
        return value
    except (UnicodeError, AttributeError):
        raise MetadataCredentialUnavailable()
