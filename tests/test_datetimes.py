# ruff: noqa: D100, D101, D102, D103
import pytz
from steerage import datetimes

def test_it_should_create_a_timezone_aware_datetime_in_UTC():
    result = datetimes.utcnow()
    assert result.tzinfo == pytz.UTC
