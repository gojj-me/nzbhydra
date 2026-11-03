"""Persisted provider cooldown helpers, compatible with Python 2.7."""
from __future__ import absolute_import, division, print_function, unicode_literals
import datetime
import re
import threading
from email.utils import parsedate_tz, mktime_tz
import arrow

REASON_PREFIX = 'Rate limited; next permitted attempt: '
FALLBACK_SECONDS = 15 * 60
_locks = {}
_locks_guard = threading.Lock()


def request_lock(indexer_id):
    with _locks_guard:
        if indexer_id not in _locks:
            _locks[indexer_id] = threading.Lock()
        return _locks[indexer_id]


def active(status, now=None):
    return bool(status and (status.reason or '').startswith(REASON_PREFIX) and
                status.disabled_until and status.disabled_until > (now or arrow.utcnow()))


def retry_at(value, now=None):
    now = now or arrow.utcnow()
    try:
        value = value.strip()
        if len(value) > 128:
            raise ValueError('Oversized retry header')
        if re.match(r'^[0-9]+$', value):
            # A minimum one-second cooldown prevents an immediate retry burst.
            seconds = max(1, int(value))
            try:
                deadline = arrow.get(now.datetime + datetime.timedelta(seconds=seconds))
            except OverflowError:
                # Do not retry early when a valid integer exceeds datetime range.
                deadline = arrow.get(datetime.datetime.max.replace(tzinfo=now.datetime.tzinfo))
        else:
            parsed = parsedate_tz(value)
            if parsed is None or parsed[9] is None:
                raise ValueError('Invalid retry date')
            deadline = arrow.get(mktime_tz(parsed))
            if deadline <= now:
                raise ValueError('Past retry date')
        return deadline
    except (AttributeError, TypeError, ValueError, OverflowError):
        return arrow.get(now.datetime + datetime.timedelta(seconds=FALLBACK_SECONDS))
