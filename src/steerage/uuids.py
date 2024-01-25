"""Utilities for working with universally-unique IDs

Steerage repositories tend to use a lot of UUIDs, especially as
primary keys.
"""
from uuid import UUID

from steerage.types import UUIDorStr


def ensure_uuid(id: UUIDorStr) -> UUID:
    """Given a UUID or a string representing a UUID, return a UUID."""
    if isinstance(id, str):
        id = UUID(id)
    return id
