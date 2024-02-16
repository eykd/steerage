"""A local filesystem implementation of file storage"""
# NOTE: We have complete test coverage for all file storages, but
# commonly want to skip slow tests, and file storages are slow, so we
# mark this with nocover.
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from io import BufferedIOBase
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import aiofiles
from aiofiles import os as aios
from convoke.configs import BaseConfig, env_field

from steerage.filestorages.base import AbstractFileStorage

if TYPE_CHECKING:  # pragma: nocover
    from pytest import FixtureRequest


class LocalFileStorageConfig(BaseConfig):  # pragma: nocover
    """Configuration for local filesystem storage"""

    FILE_STORAGE_ROOT: Path = env_field(
        doc="""
        Path on the local filesystem to store files at.
        """
    )


@dataclass
class LocalFileStorage(AbstractFileStorage):  # pragma: nocover
    """A local filesystem implementation of file storage"""

    relative_path: str = field(default='default')

    protocol: ClassVar[str] = "file"
    config_class: ClassVar[LocalFileStorageConfig] = LocalFileStorageConfig

    def _get_path(self, key: str):
        return self.config.FILE_STORAGE_ROOT / self.relative_path / key

    async def write(self, key: str, buffer: BufferedIOBase):
        """Write a bytestream to disk storage.

        The `key` parameter corresponds to a filename.
        """
        path = self._get_path(key)
        await aios.makedirs(path.parent, exist_ok=True)

        async with aiofiles.open(path, 'wb') as fo:
            await fo.write(buffer.read())

    async def read(self, key: str) -> bytes:
        """Read bytes from disk.

        The `key` parameter corresponds to a filename.

        If the key does not exist, raise `NotFound`.
        """
        try:
            async with aiofiles.open(self._get_path(key), 'rb') as fo:
                return await fo.read()
        except FileNotFoundError as exc:
            raise self.NotFound from exc

    async def delete(self, key: str) -> None:
        """Delete a stored file corresponding with the given key.

        The `key` parameter corresponds to a filename.

        If the key does not exist, calling delete(key) should be a
        no-op.
        """
        path = self._get_path(key)
        try:
            await aios.remove(path)
        except FileNotFoundError:
            pass



@asynccontextmanager
async def build_localfiles_test_repo(request: "FixtureRequest"):  # pragma: nocover
    """Async context manager to build and tear down an LocalFileStorage"""
    async with aiofiles.tempfile.TemporaryDirectory() as tempdir:
        monkeypatch = request.getfixturevalue('monkeypatch')
        monkeypatch.setenv('FILE_STORAGE_ROOT', tempdir)
        yield LocalFileStorage()
