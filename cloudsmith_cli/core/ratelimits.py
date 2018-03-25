"""Core rate limit utilities."""
from __future__ import absolute_import, print_function, unicode_literals

import atexit
import copy
import datetime
import threading
import time

from future.utils import python_2_unicode_compatible


# FIXME: Globals aren't great, do this properly later.
LAST_CLIENT = threading.local()
LAST_CLIENT = None
LAST_HEADERS = threading.local()
LAST_HEADERS = None


@python_2_unicode_compatible
class RateLimitsInfo(object):
    """Data for rate limits."""

    interval = None
    limit = None
    remaining = None
    reset = None
    throttled = None

    def __str__(self):
        """Get rate limit information as text."""
        return (
            'Throttled: %(throttled)s, Remaining: %(remaining)d/%(limit)d, '
            'Interval: %(interval)f, Reset: %(reset)s' % {
                'throttled': 'Yes' if self.throttled else 'No',
                'remaining': self.remaining,
                'limit': self.limit,
                'interval': self.interval,
                'reset': self.reset
            }
        )

    @classmethod
    def from_dict(cls, data):
        info = RateLimitsInfo()

        if 'interval' in data:
            info.interval = float(data['interval'])
        if 'limit' in data:
            info.limit = int(data['limit'])
        if 'remaining' in data:
            info.remaining = int(data['remaining'])
        if 'reset' in data:
            info.reset = datetime.datetime.utcfromtimestamp(int(data['reset']))
        if 'throtted' in data:
            info.throttled = bool(data['throttled'])
        else:
            info.throttled = info.remaining == 0

        return info

    @classmethod
    def from_headers(cls, headers):
        """Extract rate info from headers."""
        try:
            data = {
                'interval': headers['X-RateLimit-Interval'],
                'limit': headers['X-RateLimit-Limit'],
                'remaining': headers['X-RateLimit-Remaining'],
                'reset': headers['X-RateLimit-Reset']
            }
        except KeyError:
            data = {}

        return cls.from_dict(data)


@atexit.register
def maybe_rate_limit_atexit():
    """Pause the process at exit based on rate limit interval (if any)."""
    rate_limit(LAST_CLIENT, LAST_HEADERS)


def maybe_rate_limit(client, headers):
    """Optionally pause the process based on suggested rate interval."""
    global LAST_CLIENT, LAST_HEADERS

    if LAST_CLIENT and LAST_HEADERS:
        # Wait based on previous client/headers
        rate_limit(LAST_CLIENT, LAST_HEADERS)

    LAST_CLIENT = copy.copy(client)
    LAST_HEADERS = copy.copy(headers)


def rate_limit(client, headers):
    """Pause the process based on suggested rate interval."""
    if not client or not headers:
        return False

    if not getattr(client.config, 'rate_limit', False):
        return False

    rate_info = RateLimitsInfo.from_headers(headers)
    if not rate_info or not rate_info.interval:
        return False

    if rate_info.interval:
        cb = getattr(client.config, 'rate_limit_callback', None)
        if cb and callable(cb):
            cb(rate_info)
        time.sleep(rate_info.interval)
    return True
