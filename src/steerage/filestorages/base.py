"""Base adapters for storing files"""
# NOTE: We have complete test coverage for all file storages, but
# commonly want to skip slow tests, and file storages are slow, so we
# mark this with nocover.
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from io import BufferedIOBase
from typing import ClassVar

from convoke.configs import BaseConfig

from steerage.exceptions import AlreadyExists, NotFound


@dataclass
class AbstractFileStorage(ABC):  # pragma: nocover
    """Base class for file storage implementations

    Subclasses should override the abstract methods:

    - write()
    - read()
    - delete()
    """

    config: BaseConfig = field(init=False)
    active: bool = field(init=False, default=False)

    config_class: ClassVar[BaseConfig] = BaseConfig
    protocol: ClassVar[str]

    AlreadyExists = AlreadyExists
    NotFound = NotFound

    def __post_init__(self):
        self.config = self.config_class()

    @abstractmethod
    async def write(self, key: str, buffer: BufferedIOBase) -> None:  # pragma: nocover
        """Write a bytestream to the underlying storage.

        The `key` parameter corresponds to a filename.
        """
        ...

    @abstractmethod
    async def read(self, key: str) -> bytes:  # pragma: nocover
        """Read bytes from the underlying storage.

        The `key` parameter corresponds to a filename.

        If the key does not exist, raise `NotFound`.
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:  # pragma: nocover
        """Delete a stored file corresponding with the given key.

        The `key` parameter corresponds to a filename.

        If the key does not exist, calling delete(key) should be a
        no-op.
        """
        ...
