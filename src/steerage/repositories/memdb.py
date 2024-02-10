"""An ephemeral in-memory implementation of entity storage"""
from __future__ import annotations

import operator as op
from collections.abc import Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
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
from convoke.plugins import ABCPluginMount
from pyrsistent import discard, freeze, thaw
from pyrsistent.typing import PMap

from steerage.repositories.base import (
    CMP_OPERATORS,
    AbstractBaseQuery,
    AbstractEntityRepository,
)
from steerage.repositories.sessions import AbstractSession
from steerage.types import TEntity

if TYPE_CHECKING:  # pragma: nocover
    from pytest import FixtureRequest

T = TypeVar("T")


@dataclass
class InMemorySession(AbstractSession):
    """Session tracking for an ephemeral in-memory implementation of entity storage

    Useful for testing
    """

    tables: PMap[str, PMap[str, Any]] = field(default_factory=lambda: Database.tables)

    async def begin(self):
        """Begin the session.

        Since in-memory storage doesn't require much ceremony, this is a no-op.
        """
        pass

    async def end(self):
        """End the session.

        Since in-memory storage doesn't require much ceremony, this is a no-op.
        """
        pass

    async def commit(self) -> None:
        """Commit proposed changes to the in-memory database."""
        Database.tables = self.tables

    async def rollback(self) -> None:
        """Roll back and forget proposed changes."""
        self.tables = Database.tables


class AbstractInMemoryQuery(AbstractBaseQuery):
    """Abstract base class for implementing repository queries against the in-memory database.

    Subclasses must define `table_name` and `entity_class` class variables.
    """

    table_name: ClassVar[str]

    async def run_insert_query(self, data: Mapping) -> None:  # pragma: nocover
        """Run an insert query against the backend."""
        self.validate_constraints(data)
        self._upsert(data)

    async def run_update_query(self, **kwargs) -> int:
        """Run this as an update query against the backend."""
        count = 0
        async for entity in self:
            new_entity = entity.model_copy(update=kwargs)
            self._upsert(self.transform_entity_to_data(new_entity))
            count += 1
        return count

    async def run_delete_query(self, **kwargs) -> int:
        """Run this as a deletion query against the backend."""
        count = 0
        async for entity in self:
            self.session.tables = self.session.tables.transform((self.table_name, str(entity.id)), discard)
            count += 1
        return count

    async def run_selection_query(self) -> AsyncGenerator[Mapping, None]:
        """Run this selection query against the in-memory database."""
        rows = Database.tables[self.table_name].values()

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
            yield thaw(row)

    def validate_constraints(self, data: Mapping) -> None:
        """Template method: validate any invariant constraints for the in-memory table.

        By default, ensure that insertions do not clobber existing records.
        """
        if str(data["id"]) in self.session.tables[self.table_name]:
            raise self.AlreadyExists(data["id"])

    def _upsert(self, data: Mapping) -> None:
        data = freeze(data)
        self.session.tables = self.session.tables.transform((self.table_name, str(data["id"])), data)


class Database:
    """Simple in-memory global database singleton

    There's no point in instantiating this class, as all table data is
    stored at the class level.

    The table data uses immutable data structures from the
    `pyrsistent` library. It is best to only access this data through
    a concrete implementation of `AbstractInMemoryRepository`.

    """

    tables: PMap[str, PMap[str, PMap[str, Any]]] = freeze({})

    @classmethod
    def clear(cls) -> None:
        """Clear the in-memory data tables.

        Note: When testing, this should be performed after each test
        to ensure a clean test environment.

        """
        cls.tables = freeze({name: {} for name in AbstractInMemoryRepository._get_table_names()})


@dataclass(repr=False)
class AbstractInMemoryRepository(AbstractEntityRepository, metaclass=ABCPluginMount):
    """Abstract in-memory entity repository

    Concrete subclasses should define the following class variables:

    - `table_name` -- the namespace to store entities in
    - `entity_class` -- the concrete entity class that should be used to construct results
    - `query_class` -- the concrete query class that should be used to form queries
    """

    session: InMemorySession = field(init=False, repr=False)
    table_name: ClassVar[str]
    session_class: ClassVar[Type[InMemorySession]] = InMemorySession
    query_class: ClassVar[Type[AbstractInMemoryQuery]]
    entity_class: ClassVar[Type[TEntity]]
    database: ClassVar[Type[Database]] = Database

    @classmethod
    def _get_table_names(cls) -> set[str]:
        return {plug.table_name for plug in cls.plugins}


def get_memdb_test_repo_builder(repo_class: Type[AbstractInMemoryRepository]) -> Callable:
    """Return a repository builder for the given repo_class.

    The returned builder is an async context manager that will cleanly
    set up and tear down the repository.
    """

    @asynccontextmanager
    async def build_memdb_test_repo(request: "FixtureRequest") -> AbstractInMemoryRepository:
        from steerage.repositories.memdb import Database

        # Need to explicitly clear right here to ensure that the db has
        # our new `entities` table name:
        Database.clear()

        yield repo_class()

        Database.clear()

    return build_memdb_test_repo
