"""Abstract session management for repositories"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar, Type

from convoke.configs import BaseConfig


@dataclass(repr=False)
class AbstractSession(ABC):
    """An abstract base sesssion for repositories

    A session manages the connection with an underlying storage,
    tracks the proposed changes for a repository, and commits those
    changes when complete, or otherwise rolls them back.

    Subclasses should override the abstract methods:

    - begin()
    - end()
    - commit()
    - rollback()

    """

    config: BaseConfig = field(init=False)
    config_class: ClassVar[Type[BaseConfig]] = BaseConfig

    def __post_init__(self):
        self.config = self.config_class()

    @abstractmethod
    async def begin(self):  # pragma: nocover
        """Begin the session.

        This should set up any resources necessary for interacting
        with the underlying storage.

        """
        raise NotImplementedError

    @abstractmethod
    async def end(self):  # pragma: nocover
        """End the session.

        This should tear down any resources necessary for interacting
        with the underlying storage.
        """
        raise NotImplementedError

    @abstractmethod
    async def commit(self):  # pragma: nocover
        """Commit proposed changes to the storage."""
        raise NotImplementedError

    @abstractmethod
    async def rollback(self):  # pragma: nocover
        """Roll back and forget any uncommitted changes.

        All sessions will be rolled back before ending, even if they
        have been previously committed.
        """
        raise NotImplementedError
