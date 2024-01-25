"""An ephemeral in-memory implementation of file storage"""
# NOTE: We have complete test coverage for all file storages, but
# commonly want to skip slow tests, and file storages are slow, so we
# mark this with nocover.
from contextlib import asynccontextmanager
from dataclasses import dataclass
from io import BufferedIOBase
from typing import TYPE_CHECKING

from steerage.filestorages.base import AbstractFileStorage

if TYPE_CHECKING:  # pragma: nocover
    from pytest import FixtureRequest


@dataclass
class InMemoryFileStorage(AbstractFileStorage):  # pragma: nocover
    """An ephemeral in-memory implementation of file storage

    Useful for testing
    """

    protocol = "memory"

    async def write(self, key: str, buffer: BufferedIOBase):
        """Write a bytestream to in-memory ephemeral storage.

        The `key` parameter corresponds to a filename.
        """
        DATABASE[key] = buffer.read()

    async def read(self, key: str) -> bytes:
        """Read bytes from memory.

        The `key` parameter corresponds to a filename.

        If the key does not exist, raise `NotFound`.
        """
        try:
            return DATABASE[key]
        except KeyError as exc:
            raise self.NotFound(key) from exc

    async def delete(self, key: str) -> None:
        """Delete a stored file corresponding with the given key.

        The `key` parameter corresponds to a filename.

        If the key does not exist, calling delete(key) should be a
        no-op.
        """
        try:
            del DATABASE[key]
        except KeyError:
            pass


DATABASE = {}


@asynccontextmanager
async def build_memdb_test_repo(request: "FixtureRequest"):  # pragma: nocover
    """Async context manager to build and tear down an InMemoryFileStorage"""
    yield InMemoryFileStorage()

    DATABASE.clear()
