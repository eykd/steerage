"""A simple relational database implementation of entity storage

This gives you the basic CRUD operations steerage on top of SQLAlchemy's
wide support of relational database engines.

For an example implementation, see `tb.users.repositories.sqldb`.

For the simplest approach, all tables should be defined through
`steerage.repositories.sqldb.BASE_SCHEMA`.

If you need something more complex than this, then you already know
what you're doing.

Migrations should be handled by Alembic. You will find an example
migration setup in `tb.sqldb`.

"""
from collections.abc import Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, AsyncGenerator, ClassVar, Type, TypeVar

import pytz
import sqlalchemy as sa
from convoke.configs import BaseConfig, env_field
from convoke.plugins import ABCPluginMount
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from steerage.repositories.base import (
    CMP_OPERATORS,
    AbstractBaseQuery,
    AbstractEntityRepository,
)
from steerage.repositories.sessions import AbstractSession
from steerage.types import TEntity

if TYPE_CHECKING:  # pragma: nocover
    from pytest import FixtureRequest

TESTING_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

T = TypeVar("T")


BASE_SCHEMA = sa.MetaData()


class SQLConfig(BaseConfig):
    """Connection configuration for the relational database connection"""

    DATABASE_URL: str = env_field(
        default=TESTING_DATABASE_URL,
        doc="""
        URL to connect with the database server

        Be sure to use an async driver, e.g. `aiosqlite` or `asincpg`.

        For kickstarting local dev, use something like:

            sqlite+aiosqlite:///db.sqlite

        This will create an sqlite3 file in your project root, which
        will be ignored by git.
        """,
    )
    DATABASE_ECHO: bool = env_field(
        default=False,
        doc="""
        Should database queries be echoed to the log?
        """,
    )


@dataclass(repr=False)
class SQLSession(AbstractSession):
    """Session tracking for a relational database implementation of entity storage

    Backed by SQLAlchemy, with support for any relational db client
    that library supports.
    """

    _engine: ClassVar[AsyncEngine]
    _sa_session: AsyncSession = field(init=False)

    config_class: ClassVar[Type[SQLConfig]] = SQLConfig

    @property
    def engine(self):
        """Provide the SQLAlchemy asynchronous engine for connecting to the database.

        Note that this is a lazy property that defers to a class
        variable engine.

        """
        try:
            return self._engine
        except AttributeError:
            self.__class__._engine = create_async_engine(
                self.config.DATABASE_URL,
                echo=self.config.DATABASE_ECHO,
                # Use pessimistic disconnect handling:
                # https://docs.sqlalchemy.org/en/20/core/pooling.html#disconnect-handling-pessimistic
                pool_pre_ping=True,
            )
            return self._engine

    async def begin(self):
        """Begin the session.

        This creates the underlying SQLAlchemy asynchronous session.
        """
        session = async_sessionmaker(self.engine)
        self._sa_session = await session.begin().__aenter__()

    async def end(self):
        """End the session.

        This closes and destroys the underlying SQLAlchemy
        asynchronous session.
        """
        self._sa_session = await self._sa_session.close()
        del self._sa_session

    async def commit(self) -> None:
        """Commit proposed changes to the SQL database."""
        await self._sa_session.commit()

    async def rollback(self) -> None:
        """Roll back and forget any uncommitted changes.

        Note that this is called at the end of every session.
        """
        await self._sa_session.rollback()


class AbstractSQLQuery(AbstractBaseQuery):
    """Abstract base class for implementing repository queries against the in-memory database.

    Subclasses must define `table_name` and `entity_class` class variables.
    """

    table: ClassVar[sa.Table]

    async def run_insert_query(self, data: Mapping) -> None:  # pragma: nocover
        """Run an insert query against the backend."""
        try:
            await self._execute_sql(sa.insert(self.table).values(**data))
        except IntegrityError as exc:
            raise self.AlreadyExists from exc

    async def run_update_query(self, **kwargs) -> int:
        """Run this as an update query against the backend."""
        sa_query = sa.update(self.table)
        sa_query = await self._build_sa_query(sa_query)
        sa_query = sa_query.values(**kwargs)

        return (await self._execute_sql(sa_query)).rowcount

    async def run_delete_query(self, **kwargs) -> int:
        """Run this as a deletion query against the backend."""
        sa_query = sa.delete(self.table)
        sa_query = await self._build_sa_query(sa_query)

        return (await self._execute_sql(sa_query)).rowcount

    async def run_selection_query(self) -> AsyncGenerator[TEntity, None]:
        """Run this query against a relational database."""
        sa_query = sa.select(self.table)
        sa_query = await self._build_sa_query(sa_query)

        for row in await self._execute_sql(sa_query):
            yield row._asdict()

    async def run_count(self) -> int:
        """Run a (potentially) simplified query to count results.

        This base implementation uses a simplistic algorithm that runs
        the full query and counts the results. Override this in
        subclass to implement something more efficient for the
        backend.
        """
        sa_query = sa.select(sa.func.count()).select_from(self.table)
        sa_query = await self._build_sa_query(sa_query)

        result = await self._execute_sql(sa_query)
        return result.scalar()

    async def _execute_sql(self, *args, **kwargs):
        return await self.session._sa_session.execute(*args, **kwargs)

    async def _build_sa_query(self, sa_query):
        if self.filters:
            filters = []
            for key, operator, value in self.filters:
                column = getattr(self.table.c, key)
                match operator:
                    case "startswith":
                        filters.append(column.startswith(value))
                    case "endswith":
                        filters.append(column.endswith(value))
                    case "isnull":
                        if value is True:
                            filters.append(column == sa.null())
                        else:
                            filters.append(column != sa.null())
                    case _:
                        # NOTE: any remaining operators *must* be compatible
                        # with Column object comparisons, e.g. `op.eq(column, value)`
                        # being the same as `column == value`:
                        filters.append(CMP_OPERATORS[operator](column, value))
            sa_query = sa_query.where(*filters)

        if self.ordering:
            ordering = []
            for key, ascending in self.ordering:
                column = getattr(self.table.c, key)
                if ascending:
                    ordering.append(column)
                else:
                    ordering.append(sa.desc(column))
            sa_query = sa_query.order_by(*ordering)

        if self.offset:
            sa_query = sa_query.offset(self.offset)

        if self.limit:
            sa_query = sa_query.limit(self.limit)

        return sa_query


@dataclass
class AbstractSQLRepository(AbstractEntityRepository, metaclass=ABCPluginMount):
    """Abstract relational database-backed entity repository

    Concrete subclasses should define the following class variables:

    - `table_name` -- the namespace to store entity records in
    - `entity_class` -- the concrete entity class that should be used to construct results
    """

    session: SQLSession = field(init=False)

    table_name: ClassVar[str]
    entity_class: ClassVar[Type[TEntity]]

    table: ClassVar[sa.Table]
    schema: ClassVar[sa.MetaData]
    session_class: ClassVar[Type[SQLSession]] = SQLSession
    query_class: ClassVar[Type[AbstractSQLQuery]]


class AwareDateTime(sa.types.TypeDecorator):
    """SQLAlchemy type for handling offset-aware datetimes

    Offset-aware datetimes are converted to and stored as naive
    datetimes in UTC.
    """

    impl = sa.types.DateTime

    cache_ok = True

    def process_bind_param(self, value: datetime, dialect):
        """Convert an offset-aware datetime to a UTC naive datetime."""
        return value if value is None else value.astimezone(pytz.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        """Convert a naive UTC datetime to an offset-aware datetime."""
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=pytz.utc)

        return value


def get_sqldb_test_repo_builder(repo_class):
    """Return a repository builder for the given repo_class.

    The returned builder is an async context manager that will cleanly
    set up and tear down the repository and associated resources.
    """

    @asynccontextmanager
    async def build_sqldb_test_repo(request: "FixtureRequest"):
        session = SQLSession()
        engine = session.engine
        async with engine.begin() as conn:
            await conn.run_sync(repo_class.schema.create_all)
            await conn.commit()

        yield repo_class()

        async with engine.begin() as conn:
            await conn.run_sync(repo_class.schema.drop_all)
            await conn.commit()

    return build_sqldb_test_repo
