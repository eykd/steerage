"""A simple dbm implementation of entity storage

This module is best used for early development when you don't want the
hassle of a relational database yet.
"""
import operator as op
import os
import shelve
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Callable,
    ClassVar,
    Type,
    TypeVar,
    Union,
)
from uuid import UUID

import funcy as fn
from convoke.configs import BaseConfig, env_field
from convoke.plugins import ABCPluginMount
from pyrsistent import discard, freeze, thaw
from pyrsistent.typing import PMap, PSet

from steerage.repositories.base import (
    CMP_OPERATORS,
    AbstractBaseQuery,
    AbstractEntityRepository,
)
from steerage.repositories.sessions import AbstractSession
from steerage.types import TEntity, UUIDorStr

if TYPE_CHECKING:  # pragma: nocover
    from pytest import FixtureRequest

T = TypeVar("T")


class ShelveConfig(BaseConfig):
    """Configuration for dbm-backed repositories"""

    SHELVE_DB_PATH: Path = env_field(doc="Path to the dbm storage file")


@dataclass(repr=False)
class ShelveSession(AbstractSession):
    """Session tracking for a dbm implementation of entity storage

    Useful for for early development when you don't want the hassle of
    a relational database yet.
    """

    data: PMap[str, PMap[str, Any]] = field(default_factory=lambda: freeze({}))
    deleted_keys: PSet = field(default_factory=lambda: freeze(set()))

    shelf: shelve.Shelf = field(init=False)

    config_class: ClassVar[Type[ShelveConfig]] = ShelveConfig

    async def begin(self):
        """Begin the session.

        This creates the dbm client at `self.shelf`.
        """
        self.shelf = shelve.open(str(self.config.SHELVE_DB_PATH), flag="c")

    async def end(self):
        """End the session.

        This destroys the dbm client at `self.shelf`.
        """
        self.shelf.close()
        del self.shelf

    async def commit(self) -> None:
        """Commit proposed changes to the dbm database."""
        for key, value in self.data.items():
            self.shelf[key] = value
        for key in self.deleted_keys:
            del self.shelf[key]
        self.data = freeze({})
        self.deleted_keys = freeze(set())

    async def rollback(self) -> None:
        """Roll back and forget any uncommitted changes.

        Note that this is called at the end of every session.
        """
        self.data = freeze({})
        self.deleted_keys = freeze(set())


class AbstractShelveQuery(AbstractBaseQuery):
    """Abstract base class for implementing repository queries against the in-memory database.

    Subclasses must define `table_name` and `entity_class` class variables.
    """

    table_name: ClassVar[str]

    async def run_data_query(self) -> AsyncGenerator[dict, None]:
        """Run this query against the ShelveDB database.

        NOTE: This query is *extremely* inefficient on large datasets, and
        should only be used in development.
        """
        table_key = f"{self.table_name}:"
        rows = (row for key, row in self.session.shelf.items() if key.startswith(table_key))

        for key, operator, value in self.filters:
            op_fn = CMP_OPERATORS[operator]
            rows = (row for row in rows if op_fn(getattr(row, key), value))

        if self.ordering:
            # In memory multi-item sort with mixed ascending/descending! Let's go!
            #
            # First, sort on the last key:
            key, ascending = self.ordering[-1]
            rows = sorted(rows, key=op.itemgetter(key), reverse=not ascending)
            # Now, sort on preceding keys, from back to front. This works because Python sort is stable.
            # See https://stackoverflow.com/questions/11993004/
            for key, ascending in self.ordering[-2::-1]:  # <- reversed slice, penultimate through first
                rows.sort(key=op.itemgetter(key), reverse=not ascending)

        if self.offset:
            rows = fn.drop(self.offset, rows)

        if self.limit is not None:
            rows = fn.take(self.limit, rows)

        for row in rows:
            yield row


@dataclass
class AbstractShelveRepository(AbstractEntityRepository, metaclass=ABCPluginMount):
    """Abstract dbm-backed entity repository

    Concrete subclasses should define the following class variables:

    - `table_name` -- the namespace to store entity records in
    - `entity_class` -- the concrete entity class that should be used to construct results
    - `query_class` -- the concrete query class that should be used to form queries
    """

    session: ShelveSession = field(init=False, repr=False)
    table_name: ClassVar[str]
    entity_class: ClassVar[Type[TEntity]]
    session_class: ClassVar[Type[ShelveSession]] = ShelveSession
    config_class: ClassVar[Type[ShelveConfig]] = ShelveConfig

    query_class: ClassVar[Type[AbstractShelveQuery]]

    def _get_key(self, id: UUIDorStr) -> str:
        return f"{self.table_name}:{id}"

    async def get(self, id: UUIDorStr) -> TEntity:
        """Retrieve a previously-stored entity record by primary key.

        If the entity does not exist in storage, raises `NotFound`.
        """
        try:
            data = self.session.shelf[self._get_key(id)]
            return self.transform_data_to_entity(thaw(data))
        except KeyError as exc:
            raise self.NotFound from exc

    def _upsert(self, key: str, obj: TEntity) -> None:
        data = freeze(self.transform_entity_to_data(obj))
        self.session.data = self.session.data.set(key, data)
        self.session.deleted_keys = self.session.deleted_keys.discard(key)

    async def insert(self, obj: TEntity) -> None:
        """Insert an entity into the repository.

        Attempting to insert a second entity with the same primary key
        will raise `AlreadyExists`.
        """
        key = self._get_key(obj.id)
        self.validate_constraints(key, obj)
        self._upsert(key, obj)

    async def update(self, obj: TEntity) -> None:
        """Update a previously-stored entity record.

        Attempting to update an entity that has not already been
        inserted will raise `NotFound`.
        """
        key = self._get_key(obj.id)
        if key not in self.session.shelf:
            raise self.NotFound(obj.id)
        self._upsert(key, obj)

    async def delete(self, id: Union[str, UUID]):
        """Delete a previously-stored entity record by primary key.

        If the entity does not exist in storage, this is a no-op.
        """
        key = self._get_key(id)
        self.session.data = self.session.data.transform((key,), discard)
        self.session.deleted_keys = self.session.deleted_keys.add(key)

    def validate_constraints(self, key: str, obj: TEntity) -> None:
        """Template method: validate any invariant constraints for the in-memory table.

        By default, ensure that insertions do not clobber existing records.
        """
        if key in self.session.shelf:
            raise self.AlreadyExists(obj.id)


def get_shelvedb_test_repo_builder(repo_class: Type[AbstractShelveRepository]) -> Callable:
    """Return a repository builder for the given repo_class.

    The returned builder is an async context manager that will cleanly
    set up and tear down the repository and associated resources.
    """

    @asynccontextmanager
    async def build_shelvedb_test_repo(request: "FixtureRequest") -> AbstractShelveRepository:
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tempdir:
            with patch.dict(os.environ, SHELVE_DB_PATH=f"{tempdir}/shelve.db"):
                yield repo_class()

    return build_shelvedb_test_repo
