import typing
from datetime import datetime, timezone
from decimal import Decimal

from marshmallow import fields


class Timestamp(fields.Field):
    """Field that serializes a datetime to an integer timestamp and back again.
    """

    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return 0
        return Decimal(value.timestamp())

    def _deserialize(self, value, attr, data, **kwargs):
        if value == 0:
            return None
        return datetime.fromtimestamp(float(value), tz=timezone.utc)


class Set(fields.List):
    """A set field, composed with another `Field` class or
    instance.

    Example: ::

        numbers = fields.Set(fields.Float())

    :param cls_or_instance: A field class or instance.
    :param kwargs: The same keyword arguments that :class:`Field` receives.

    .. versionchanged:: 2.0.0
        The ``allow_none`` parameter now applies to deserialization and
        has the same semantics as the other fields.

    .. versionchanged:: 3.0.0rc9
        Does not serialize scalar values to single-item sets.
    """

    default_error_messages = {"invalid": "Not a valid set."}

    def _deserialize(self, value, attr, data, **kwargs) -> typing.Set[typing.Any]:
        return set(super()._deserialize(value, attr, data, **kwargs))


class FrozenSet(fields.List):
    """A frozenset field, composed with another `Field` class or
    instance.

    Example: ::

        numbers = fields.FrozenSet(fields.Float())

    :param cls_or_instance: A field class or instance.
    :param kwargs: The same keyword arguments that :class:`Field` receives.

    .. versionchanged:: 2.0.0
        The ``allow_none`` parameter now applies to deserialization and
        has the same semantics as the other fields.

    .. versionchanged:: 3.0.0rc9
        Does not serialize scalar values to single-item frozensets.
    """

    default_error_messages = {"invalid": "Not a valid frozenset."}

    def _deserialize(self, value, attr, data, **kwargs) -> typing.FrozenSet[typing.Any]:
        return frozenset(super()._deserialize(value, attr, data, **kwargs))


class FrozenList(fields.List):
    """A flexible-length tuple field, composed with another `Field` class or
    instance.

    Example: ::

        numbers = fields.Tuple(fields.Float())

    :param cls_or_instance: A field class or instance.
    :param kwargs: The same keyword arguments that :class:`Field` receives.

    .. versionchanged:: 2.0.0
        The ``allow_none`` parameter now applies to deserialization and
        has the same semantics as the other fields.

    .. versionchanged:: 3.0.0rc9
        Does not serialize scalar values to single-item tuples.
    """

    default_error_messages = {"invalid": "Not a valid tuple."}

    def _deserialize(self, value, attr, data, **kwargs) -> typing.Tuple[typing.Any]:
        return tuple(super()._deserialize(value, attr, data, **kwargs))
