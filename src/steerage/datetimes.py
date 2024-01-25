"""Utilities for generating and working with datetime objects

One advantage of using these instead of the stdlib datetime is that
these functions can be monkeypatched in tests to return deterministic
values:

    from unittest.mock import patch
    import datetime as dt

    fake_date = dt.datetime(1999, 12, 31, tzinfo=dt.timezone.utc)
    with patch('steerage.datetimes.utcnow', fake_date):
        now = datetimes.utcnow()

    assert now == fake_date
"""
from datetime import datetime

import pytz


def utcnow():
    """Create a timezone-aware datetime instance for the current time in UTC."""
    return datetime.now(pytz.utc)
