import datetime as dt
from decimal import Decimal

import pytest
from marshmallow import Schema
from marshmallow.fields import Str
from steerage import fields


@pytest.fixture
def timestamp_schema():
    class TimestampSchema(Schema):
        created = fields.Timestamp(allow_none=True)

    return TimestampSchema()


def test_it_should_round_trip_a_timestamp(timestamp_schema):
    data = {'created': dt.datetime(2020, 1, 1, 1, 1, 1, tzinfo=dt.timezone.utc)}
    dump = timestamp_schema.dump(data)
    assert dump == {'created': Decimal('1577840461')}

    restored = timestamp_schema.load(dump)

    assert restored == data


def test_it_should_round_trip_a_null_timestamp(timestamp_schema):
    data = {'created': None}
    dump = timestamp_schema.dump(data)
    assert dump == {'created': 0}

    restored = timestamp_schema.load(dump)

    assert restored == data


@pytest.fixture
def set_schema():
    class SetSchema(Schema):
        items = fields.Set(Str(), allow_none=True)

    return SetSchema()


def test_it_should_round_trip_a_set(set_schema):
    data = {'items': {'foo', 'bar'}}
    dump = set_schema.dump(data)
    assert dump == {'items': list(data['items'])}

    restored = set_schema.load(dump)

    assert restored == data


def test_it_should_round_trip_a_null_set(set_schema):
    data = {'items': None}
    dump = set_schema.dump(data)
    assert dump == {'items': None}

    restored = set_schema.load(dump)

    assert restored == data


@pytest.fixture
def frozenset_schema():
    class FrozenSetSchema(Schema):
        items = fields.FrozenSet(Str(), allow_none=True)

    return FrozenSetSchema()


def test_it_should_round_trip_a_frozenset(frozenset_schema):
    data = {'items': frozenset({'foo', 'bar'})}
    dump = frozenset_schema.dump(data)
    assert dump == {'items': list(data['items'])}

    restored = frozenset_schema.load(dump)

    assert restored == data


def test_it_should_round_trip_a_null_frozenset(frozenset_schema):
    data = {'items': None}
    dump = frozenset_schema.dump(data)
    assert dump == {'items': None}

    restored = frozenset_schema.load(dump)

    assert restored == data


@pytest.fixture
def frozenlist_schema():
    class FrozenListSchema(Schema):
        items = fields.FrozenList(Str(), allow_none=True)

    return FrozenListSchema()


def test_it_should_round_trip_a_frozenlist(frozenlist_schema):
    data = {'items': ('foo', 'bar')}
    dump = frozenlist_schema.dump(data)
    assert dump == {'items': list(data['items'])}

    restored = frozenlist_schema.load(dump)

    assert restored == data


def test_it_should_round_trip_a_null_frozenlist(frozenlist_schema):
    data = {'items': None}
    dump = frozenlist_schema.dump(data)
    assert dump == {'items': None}

    restored = frozenlist_schema.load(dump)

    assert restored == data
