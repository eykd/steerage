"""An ephemeral in-memory implementation of entity storage"""
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
from steerage.types import TEntity, UUIDorStr

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

    async def run_data_query(self) -> AsyncGenerator[Mapping, None]:
        """Run this query against the in-memory database."""
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

    @classmethod
    def _get_table_names(cls) -> set[str]:
        return {plug.table_name for plug in cls.plugins}

    async def get(self, id: UUIDorStr) -> TEntity:
        """Retrieve a previously-stored entity record by primary key.

        If the entity does not exist in storage, raises `NotFound`.
        """
        try:
            data = self.session.tables[self.table_name][str(id)]
            return self.transform_data_to_entity(thaw(data))
        except KeyError as exc:
            raise self.NotFound from exc

    def _upsert(self, obj: TEntity) -> None:
        data = freeze(self.transform_entity_to_data(obj))
        self.session.tables = self.session.tables.transform((self.table_name, str(obj.id)), data)

    async def insert(self, obj: TEntity) -> None:
        """Insert an entity into the repository.

        Attempting to insert a second entity with the same primary key
        will raise `AlreadyExists`.
        """
        self.validate_constraints(obj)
        self._upsert(obj)

    async def update(self, obj: TEntity) -> None:
        """Update a previously-stored entity record.

        Attempting to update an entity that has not already been
        inserted will raise `NotFound`.
        """
        if str(obj.id) not in self.session.tables[self.table_name]:
            raise self.NotFound(obj.id)
        self._upsert(obj)

    async def delete(self, id: Union[str, UUID]):
        """Delete a previously-stored entity record by primary key.

        If the entity does not exist in storage, this is a no-op.
        """
        self.session.tables = self.session.tables.transform((self.table_name, str(id)), discard)

    def validate_constraints(self, obj: TEntity) -> None:
        """Template method: validate any invariant constraints for the in-memory table.

        By default, ensure that insertions do not clobber existing records.
        """
        if str(obj.id) in self.session.tables[self.table_name]:
            raise self.AlreadyExists(obj.id)


class Database:
    """Simple in-memory global database singleton

    There's no point in instantiating this class, as all table data is
    stored at the class level.

    The table data uses immutable data structures from the
    `pyrsistent` library. It is best to only access this data through
    a concrete implementation of `AbstractInMemoryRepository`.

    """

    tables: PMap[str, PMap[str, PMap[str, Any]]] = freeze(
        {name: {} for name in AbstractInMemoryRepository._get_table_names()}
    )

    @classmethod
    def clear(cls) -> None:
        """Clear the in-memory data tables.

        Note: When testing, this should be performed after each test
        to ensure a clean test environment.

        """
        cls.tables = freeze({name: {} for name in AbstractInMemoryRepository._get_table_names()})


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
