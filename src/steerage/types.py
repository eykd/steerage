"""Typing helpers"""
from typing import TypeVar
from uuid import UUID

UUIDorStr = UUID | str

TEntity = TypeVar("TEntity")
