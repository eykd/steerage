"""Base adapters for storing entities"""
from __future__ import annotations

import copy
import operator as op
from abc import ABC, abstractmethod
from collections import namedtuple
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import (
    Any,
    AsyncGenerator,
    ClassVar,
    Generic,
    Iterable,
    Optional,
    Self,
    Type,
    TypeVar,
)

import funcy as fn
from aiostream import StreamEmpty, stream
from asyncstdlib.builtins import list as alist
from convoke.configs import BaseConfig

from steerage.exceptions import AlreadyExists, MultipleResultsFound, NotFound
from steerage.repositories.sessions import AbstractSession
from steerage.types import TEntity, UUIDorStr

CMP_OPERATORS = {
    None: op.eq,
    "lt": op.lt,
    "gt": op.gt,
    "lte": op.le,
    "gte": op.ge,
    "eq": op.eq,
    "ne": op.ne,
    "startswith": str.startswith,
    "endswith": str.endswith,
    "isnull": lambda a, b: fn.isnone(a) is b,
}

OrderBy = namedtuple("OrderBy", "key ascending")


class AbstractBaseQuery(ABC, Generic[TEntity]):
    """Abstract base class for implementing repository queries against backends

    Subclasses must:

    - implement the abstract method `run_data_query()`
    - define the class variable `entity_class`.
    """

    # This is steerage loosely on the queryish library:
    # https://github.com/wagtail/queryish/blob/8448d41c9a2a42430d73a7da858ad3852068893d/queryish/__init__.py#L5C1-L166C1

    entity_class: ClassVar[TEntity]
    max_repr: ClassVar[int] = 3

    NotFound = NotFound
    MultipleResultsFound = MultipleResultsFound

    def __init__(self, session: AbstractSession):
        self.session = session
        self._results = None
        self._count = None
        self.offset = 0
        self.limit = None
        self.filters = []
        self.ordering = ()

    @abstractmethod
    async def run_data_query(self) -> AsyncGenerator[TEntity, None]:  # pragma: nocover
        """Run this query against the backend."""
        raise NotImplementedError

    async def run_query(self) -> AsyncGenerator[TEntity, None]:
        """Run the data query and transform the resulting records into `entity_class`."""
        async for row in self.run_data_query():
            yield self.transform_data_to_entity(row)

    async def __aiter__(self) -> AsyncGenerator[TEntity, None]:
        """Iterate over (and cache) results of the query."""
        if self._results is None:
            results_list = []
            async for result in self.run_query():
                results_list.append(result)
                yield result
            self._results = results_list
        else:
            for result in self._results:
                yield result

    async def run_count(self) -> int:
        """Run a (potentially) simplified query to count results.

        This base implementation uses a simplistic algorithm that runs
        the full query and counts the results. Override this in
        subclass to implement something more efficient for the
        backend.
        """
        count = 0
        async for _ in self:
            count += 1
        return count

    async def count(self) -> int:
        """Return the result count."""
        if self._count is None:
            if self._results is None:
                self._count = await self.run_count()
            else:
                self._count = len(self._results)
        return self._count

    def clone(self, **kwargs) -> Self:
        """Return a copy of this queryset with the given keyword arguments overridden."""
        clone = copy.copy(self)
        clone._results = None
        clone._count = None
        clone.filters = self.filters.copy()
        for key, value in kwargs.items():
            setattr(clone, key, value)
        return clone

    def filter_is_valid(self, key: str, operator: str, val: Any) -> bool:
        """Validate the given filter.

        Override this in subclass to customize the behavior to the
        given model and backend.

        """
        key_ok = key in self.entity_class.model_fields
        operator_ok = operator is None or operator in CMP_OPERATORS
        return key_ok and operator_ok

    def filter(self, **kwargs) -> Self:
        """Return a filtered copy of this query."""
        clone = self.clone()
        for key, val in kwargs.items():
            key, *operator = key.split("__")
            operator = fn.first(operator)

            if self.filter_is_valid(key, operator, val):
                clone.filters.append((key, operator, val))
            else:
                raise ValueError("Invalid filter field: %s" % key)
        return clone

    def ordering_is_valid(self, key: str) -> bool:
        """Validate the given ordering key.

        Override this in subclass to customize the behavior to the
        given model and backend.

        """
        return key in self.entity_class.model_fields

    def order_by(self, *args) -> Self:
        """Return a copy of this query sorted by the given ordering keys."""
        ordering = []

        for key in args:
            ascending = True
            if key.startswith("-"):
                key = key[1:]
                ascending = False
            if self.ordering_is_valid(key):
                ordering.append(OrderBy(key, ascending))
            else:
                raise ValueError("Invalid ordering field: %s" % key)
        return self.clone(ordering=tuple(ordering))

    async def get(self, **kwargs) -> TEntity:
        """Return a single query result for the given constraints."""
        results = await stream.list(stream.take(self.filter(**kwargs), 3))
        rlen = len(results)
        if rlen == 0:
            raise NotFound()
        elif rlen > 1:
            raise MultipleResultsFound()
        else:
            return results[0]

    async def first(self) -> TEntity:
        """Return the first result of the query, or None if there are no results."""
        try:
            return await stream.take(self, 1)
        except StreamEmpty:
            return None

    def none(self) -> Iterable[TEntity]:
        """Return no results."""
        self._results = ()
        return self

    def all(self) -> Self:
        """Return the entire result set for the query."""
        return self.clone()

    async def as_list(self):
        """Reify the query as a list."""
        return await alist(self)

    @property
    def ordered(self) -> bool:
        """Check if this queryset has ordering applied or not."""
        return bool(self.ordering)

    def slice(self, start: int, stop: Optional[int] = None) -> Self:
        """Slice the query to only return a subset of results."""
        # Adjust the requested start/stop values to be relative to the full queryset
        absolute_start = (start or 0) + self.offset
        if stop is None:
            absolute_stop = None
        else:
            absolute_stop = stop + self.offset

        # find the absolute stop value corresponding to the current limit
        if self.limit is None:
            current_absolute_stop = None
        else:
            current_absolute_stop = self.offset + self.limit

        if absolute_stop is None:
            final_absolute_stop = current_absolute_stop
        elif current_absolute_stop is None:
            final_absolute_stop = absolute_stop
        else:
            final_absolute_stop = min(current_absolute_stop, absolute_stop)

        if final_absolute_stop is None:
            new_limit = None
        else:
            new_limit = final_absolute_stop - absolute_start

        clone = self.clone(offset=absolute_start, limit=new_limit)
        if self._results:
            clone._results = self._results[start:stop]
        return clone

    async def getitem(self, index) -> TEntity:
        """Pick an item from the query by sequence index.

        Negative indexing is not supported.

        Raises IndexError if the index is out of range.
        """
        if index < 0:
            raise IndexError("Negative indexing is not supported")
        if self._results is None:
            # NOTE: This will most likely not cache, since the generator
            # probably will not complete. Since we're indexing in,
            # we're taking a gamble that, if it's a long sequence,
            # the index is shallow, rather than deep.
            try:
                return await stream.take(stream.skip(self, index), 1)
            except StreamEmpty:
                raise IndexError(index)
        return self._results[index]

    def __repr__(self) -> str:
        if self._results:
            items = self._results[0 : self.max_repr + 1]
            if len(items) > self.max_repr:
                items[-1] = "...(remaining elements truncated)..."
        else:
            items = ["...Query has not run..."]
        return "<%s %r>" % (self.__class__.__name__, items)

    def transform_data_to_entity(self, data: Mapping) -> TEntity:
        """Template method: construct an entity from prepared entity data."""
        return self.entity_class.model_construct(**self.prepare_data_for_entity(data))

    def prepare_data_for_entity(self, data: Mapping) -> Mapping:
        """Template method: transform stored data into entity-ready data."""
        return data


@dataclass
class AbstractEntityRepository(ABC, Generic[TEntity]):
    """Base class for entity repository implementations

    Subclasses should override the abstract methods:

    - insert()
    - update()
    - get()
    - delete()
    """

    config: Optional[BaseConfig] = field(init=False, repr=False)
    session: AbstractSession = field(init=False, repr=False)
    active: bool = field(init=False, default=False)

    NotFound: ClassVar = NotFound
    AlreadyExists: ClassVar = AlreadyExists
    MultipleResultsFound: ClassVar = MultipleResultsFound

    entity_class: ClassVar[Type[TEntity]]
    session_class: ClassVar[Type[AbstractSession]]
    query_class: ClassVar[Type[AbstractBaseQuery]]
    config_class: ClassVar[Optional[Type[BaseConfig]]] = None

    def __post_init__(self):
        if self.config_class is not None:
            self.config = self.config_class()
        else:
            self.config = None

    @property
    def objects(self) -> AbstractBaseQuery:
        """Return a query object with the active session."""
        return self.query_class(session=self.session)

    @abstractmethod
    async def insert(self, obj: TEntity) -> None:
        """Insert an entity into the repository.

        Attempting to insert a second entity with the same primary key
        will raise `AlreadyExists`.
        """
        raise NotImplementedError  # pragma: nocover

    @abstractmethod
    async def update(self, obj: TEntity) -> None:
        """Update a previously-stored entity record.

        Attempting to update an entity that has not already been
        inserted will raise `NotFound`.
        """
        raise NotImplementedError  # pragma: nocover

    @abstractmethod
    async def get(self, id: UUIDorStr) -> TEntity:
        """Retrieve a previously-stored entity record by primary key.

        If the entity does not exist in storage, raises `NotFound`.
        """
        raise NotImplementedError  # pragma: nocover

    @abstractmethod
    async def delete(self, id: UUIDorStr) -> None:
        """Delete a previously-stored entity record by primary key.

        If the entity does not exist in storage, this is a no-op.
        """
        raise NotImplementedError  # pragma: nocover

    async def __aenter__(self):
        self.active = True
        self.session = self.session_class()
        await self.session.begin()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.end()
        del self.session
        self.active = False

    async def commit(self):
        """Commit queued changes to the repository."""
        await self.session.commit()

    async def rollback(self):
        """Roll back any queued changes.

        This is the default behavior for all repository sessions that
        are not committed.
        """
        await self.session.rollback()

    async def update_attrs(self, id: UUIDorStr, **kwargs) -> None:
        """Update the specified keyword attributes for an entity ID.

        Attempting to update an entity that has not already been
        inserted will raise `NotFound`.
        """
        entity = await self.get(id)
        entity = entity.model_copy(update=kwargs)
        await self.update(entity)

    def transform_entity_to_data(self, entity: TEntity) -> dict[str, Any]:
        """Template method: render an Entity as storage-ready data."""
        return entity.model_dump()

    def transform_data_to_entity(self, data: Mapping) -> TEntity:
        """Template method: construct an entity from prepared entity data."""
        return self.entity_class.model_construct(**self.prepare_data_for_entity(data))

    def prepare_data_for_entity(self, data: Mapping) -> Mapping:
        """Template method: transform stored data into entity-ready data."""
        return data


TRepository = TypeVar("TRepository", bound=AbstractEntityRepository)
