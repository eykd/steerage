# ruff: noqa: D100, D101, D102, D103
from datetime import datetime, timedelta
from uuid import UUID, uuid5

import factory
import pytest
import pytz
import sqlalchemy as sa
from asyncstdlib.builtins import list as alist
from asyncstdlib.builtins import set as aset
from faker import Faker
from pydantic import BaseModel, ConfigDict, Field
from pydantic.types import AwareDatetime

from steerage.repositories.base import AbstractEntityRepository
from steerage.repositories.memdb import (
    AbstractInMemoryQuery,
    AbstractInMemoryRepository,
)
from steerage.repositories.memdb import Database as InMemoryDatabase
from steerage.repositories.memdb import get_memdb_test_repo_builder
from steerage.repositories.shelvedb import (
    AbstractShelveQuery,
    AbstractShelveRepository,
    get_shelvedb_test_repo_builder,
)
from steerage.repositories.sqldb import (
    AbstractSQLQuery,
    AbstractSQLRepository,
    AwareDateTime,
    get_sqldb_test_repo_builder,
)
from steerage.datetimes import utcnow

NAMESPACE = UUID("dbe2dff9-122e-4718-924f-710073c33b53")


class Entity(BaseModel):
    id: UUID
    foo: str
    num: int
    is_odd: bool
    oddish: bool | None
    created_at: AwareDatetime = Field(default_factory=utcnow)
    finished_at: AwareDatetime | None = None

    model_config = ConfigDict(frozen=True)


class EntityFactory(factory.Factory):
    class Meta:
        model = Entity

    id = factory.Sequence(lambda n: uuid5(NAMESPACE, str(n)))
    num = factory.Sequence(lambda n: n)
    is_odd = factory.Sequence(lambda n: bool(n % 2))
    foo = factory.LazyAttribute(lambda obj: f"baz{obj.num}" if obj.is_odd else f"bar{obj.num}")
    oddish = factory.LazyAttribute(lambda obj: True if obj.is_odd else None)
    created_at = factory.Sequence(lambda n: datetime(2023, 12, 15, 12, 0, tzinfo=pytz.UTC) - timedelta(hours=n))


class InMemoryEntityQuery(AbstractInMemoryQuery):
    table_name: str = "entities"
    entity_class = Entity


class InMemoryEntityRepository(AbstractInMemoryRepository):
    table_name: str = "entities"
    entity_class = Entity
    query_class = InMemoryEntityQuery


class ShelveEntityQuery(AbstractShelveQuery):
    table_name: str = "entities"
    entity_class = Entity


class ShelveEntityRepository(AbstractShelveRepository):
    table_name: str = "entities"
    entity_class = Entity
    query_class = ShelveEntityQuery


SQL_SCHEMA = sa.MetaData()
ENTITY_TABLE = sa.Table(
    "entities",
    SQL_SCHEMA,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("foo", sa.String),
    sa.Column("num", sa.Integer),
    sa.Column("is_odd", sa.Boolean),
    sa.Column("oddish", sa.Boolean, nullable=True),
    sa.Column("created_at", AwareDateTime, nullable=True),
    sa.Column("finished_at", AwareDateTime, nullable=True),
)


class SQLEntityQuery(AbstractSQLQuery):
    table = ENTITY_TABLE
    entity_class = Entity


class SQLEntityRepository(AbstractSQLRepository):
    entity_class = Entity
    query_class = SQLEntityQuery

    schema = SQL_SCHEMA
    table = ENTITY_TABLE


REPO_FACTORIES = [
    get_memdb_test_repo_builder(InMemoryEntityRepository),
    get_shelvedb_test_repo_builder(ShelveEntityRepository),
    get_sqldb_test_repo_builder(SQLEntityRepository),
]


# By parametrizing the repo fixture, we can re-use the tests against
# each kind of repository:
@pytest.fixture(params=REPO_FACTORIES)
async def repo(request, config):
    async with request.param(request) as repo_inst:
        yield repo_inst


@pytest.fixture(autouse=True)
def entity_factory_reset():
    EntityFactory.reset_sequence(0)


@pytest.fixture
def entity(faker):
    return EntityFactory.build()


@pytest.fixture
async def stored_entity(repo: AbstractEntityRepository, entity: Entity):
    async with repo:
        await repo.insert(entity)
        await repo.commit()
    return entity


@pytest.fixture
def entities(entity):
    return [entity] + [EntityFactory.build() for _ in range(5)]


@pytest.fixture
async def stored_entities(repo: AbstractEntityRepository, entities: list[Entity]) -> list[Entity]:
    async with repo:
        for entity in entities:
            await repo.insert(entity)
        await repo.commit()
    return entities


class TestEntityRepositoryImplementations:
    async def test_it_should_insert_and_retrieve_an_entity(self, repo: AbstractEntityRepository, entity: Entity):
        async with repo:
            await repo.insert(entity)
            await repo.commit()

        async with repo:
            result = await repo.get(entity.id)

        assert result == entity

    async def test_it_should_fail_to_insert_twice(self, repo: AbstractEntityRepository, stored_entity: Entity):
        async with repo:
            with pytest.raises(repo.AlreadyExists):
                await repo.insert(stored_entity)

    async def test_it_should_delete_a_entity(self, repo: AbstractEntityRepository, stored_entity: Entity):
        async with repo:
            await repo.delete(stored_entity.id)
            await repo.commit()

        async with repo:
            with pytest.raises(repo.NotFound):
                await repo.get(stored_entity.id)

    async def test_it_should_update_an_entity(self, repo: AbstractEntityRepository, stored_entity: Entity):
        entity = stored_entity.model_copy(update={"foo": "blah"})
        async with repo:
            await repo.update(entity)
            await repo.commit()

        async with repo:
            result = await repo.get(stored_entity.id)

        assert result.foo == "blah"

    async def test_it_should_fail_to_update_a_nonexistent_entity(
        self, repo: AbstractEntityRepository, entity: Entity
    ):
        async with repo:
            with pytest.raises(repo.NotFound):
                await repo.update(entity)

    async def test_it_should_update_entity_attrs(self, repo: AbstractEntityRepository, stored_entity: Entity):
        async with repo:
            await repo.update_attrs(stored_entity.id, foo="blah")
            await repo.commit()

        async with repo:
            result = await repo.get(stored_entity.id)

        assert result.foo == "blah"

    async def test_it_should_happily_delete_a_nonexistent_entity(self, repo: AbstractEntityRepository, faker: Faker):
        async with repo:
            await repo.delete(faker.uuid4())  # this is a no-op

    async def test_it_should_raise_not_found_on_absent_entity_id(self, repo: AbstractEntityRepository, faker: Faker):
        async with repo:
            with pytest.raises(repo.NotFound):
                await repo.get(faker.uuid4())

    async def test_it_should_roll_back(self, repo: AbstractEntityRepository, entity: Entity):
        async with repo:
            await repo.insert(entity)
            await repo.rollback()

        async with repo:
            with pytest.raises(repo.NotFound):
                await repo.get(entity.id)


class TestConcreteBaseQueryImplementations:
    """Test the concrete AbstractBaseQuery implementations thoroughly.

    Don't worry about AbstractBasequery coverage here. We'll cover
    that in the next suite
    """

    async def test_it_should_get_all_entities(self, repo, stored_entities):
        async with repo:
            results = await repo.objects.all().as_list()
            assert set(results) == set(stored_entities)

    async def test_it_should_count_results_for_uncached_query(self, repo, stored_entities):
        async with repo:
            query = repo.objects.all()
            assert await query.count() == 6
            InMemoryDatabase.clear()
            # Use cached result:
            assert await query.count() == 6

    async def test_it_should_filter_entities_by_value(self, repo, stored_entities):
        async with repo:
            query = repo.objects.filter(foo="baz1")

            assert await aset(query) == {stored_entities[1]}
            # Should cache:
            assert await aset(query) == {stored_entities[1]}

    async def test_it_should_filter_entities_less_than(self, repo, stored_entities):
        async with repo:
            query = repo.objects.filter(num__lt=2)

            assert await aset(query) == set(stored_entities[:2])
            # Should cache:
            assert await aset(query) == set(stored_entities[:2])

    async def test_it_should_filter_entities_less_than_equal(self, repo, stored_entities):
        async with repo:
            query = repo.objects.filter(num__lte=2)

            assert await aset(query) == set(stored_entities[:3])
            # Should cache:
            assert await aset(query) == set(stored_entities[:3])

    async def test_it_should_filter_entities_greater_than(self, repo, stored_entities):
        async with repo:
            query = repo.objects.filter(num__gt=1)

            assert await aset(query) == set(stored_entities[2:])
            # Should cache:
            assert await aset(query) == set(stored_entities[2:])

    async def test_it_should_filter_entities_greater_than_equal(self, repo, stored_entities):
        async with repo:
            query = repo.objects.filter(num__gte=1)

            assert await aset(query) == set(stored_entities[1:])
            # Should cache:
            assert await aset(query) == set(stored_entities[1:])

    async def test_it_should_filter_entities_equal(self, repo, stored_entities):
        async with repo:
            query = repo.objects.filter(num__eq=1)

            assert await aset(query) == {stored_entities[1]}
            # Should cache:
            assert await aset(query) == {stored_entities[1]}

    async def test_it_should_filter_entities_not_equal(self, repo, stored_entities):
        async with repo:
            query = repo.objects.filter(num__ne=1)

            assert await aset(query) == set(stored_entities) - {stored_entities[1]}
            # Should cache:
            assert await aset(query) == set(stored_entities) - {stored_entities[1]}

    async def test_it_should_filter_entities_startswith(self, repo, stored_entities):
        async with repo:
            query = repo.objects.filter(foo__startswith="bar")

            assert await aset(query) == set(stored_entities[0::2])
            # Should cache:
            assert await aset(query) == set(stored_entities[0::2])

    async def test_it_should_filter_entities_endswith(self, repo, stored_entities):
        async with repo:
            query = repo.objects.filter(foo__endswith="1")

            assert await aset(query) == {stored_entities[1]}
            # Should cache:
            assert await aset(query) == {stored_entities[1]}

    async def test_it_should_filter_entities_isnull(self, repo, stored_entities):
        async with repo:
            query = repo.objects.filter(oddish__isnull=True)

            assert await aset(query) == set(stored_entities[0::2])
            # Should cache:
            assert await aset(query) == set(stored_entities[0::2])

    async def test_it_should_filter_entities_is_not_null(self, repo, stored_entities):
        async with repo:
            query = repo.objects.filter(oddish__isnull=False)

            assert await aset(query) == set(stored_entities[1::2])
            # Should cache:
            assert await aset(query) == set(stored_entities[1::2])

    async def test_it_should_order_by(self, repo, stored_entities):
        async with repo:
            query = repo.objects.order_by("created_at")
            assert await alist(query) == list(reversed(stored_entities))
            # Should cache:
            assert await alist(query) == list(reversed(stored_entities))

    async def test_it_should_order_by_descending(self, repo, stored_entities):
        async with repo:
            query = repo.objects.order_by("-num")

            assert await alist(query) == list(reversed(stored_entities))
            # Should cache:
            assert await alist(query) == list(reversed(stored_entities))

    async def test_it_should_order_by_mixed_ascending_descending(self, repo, stored_entities):
        async with repo:
            query = repo.objects.order_by("is_odd", "-num")
            expected = [
                stored_entities[4],
                stored_entities[2],
                stored_entities[0],
                stored_entities[5],
                stored_entities[3],
                stored_entities[1],
            ]
            assert await alist(query) == expected
            # Should cache:
            assert await alist(query) == expected

    async def test_it_should_get_an_open_slice(self, repo, stored_entities):
        async with repo:
            result = await repo.objects.order_by("num").slice(2).as_list()
            assert result == stored_entities[2:]

    async def test_it_should_get_a_closed_slice(self, repo, stored_entities):
        async with repo:
            result = await alist(repo.objects.order_by("num").slice(1, 3))
            assert result == stored_entities[1:3]

    async def test_it_should_get_a_closed_slice_with_no_offset(self, repo, stored_entities):
        async with repo:
            result = await repo.objects.order_by("num").slice(0, 3).as_list()
            assert result == stored_entities[:3]


class TestInMemoryBaseQuery:
    """Test the InMemoryBaseQuery (and underlying AbstractBasequery) very thoroughly.

    We only do this on the in-memory implementation because it's much
    faster. Between this and the previous test suite, we should have
    complete coverage.

    """

    @pytest.fixture
    async def repo(self, request):
        builder = get_memdb_test_repo_builder(InMemoryEntityRepository)
        async with builder(request) as repo_inst:
            yield repo_inst

    async def test_it_should_count_results_for_cached_query(self, repo, stored_entities):
        async with repo:
            query = repo.objects
            await query.as_list()
            # Use cached results to count:
            assert await query.count() == 6
            InMemoryDatabase.clear()
            # Use cached result:
            assert await query.count() == 6

    async def test_it_should_fail_to_filter_entities_by_bad_field(self, repo, stored_entities, entity):
        async with repo:
            with pytest.raises(ValueError):
                repo.objects.filter(blah="boo")

    async def test_it_should_order_by(self, repo, stored_entities):
        async with repo:
            query = repo.objects.order_by("created_at")

            assert await alist(query) == list(reversed(stored_entities))
            # Should cache:
            assert await alist(query) == list(reversed(stored_entities))

    async def test_it_should_fail_to_order_by_bad_field(self, repo, stored_entities):
        async with repo:
            with pytest.raises(ValueError):
                repo.objects.order_by("fhqwgds")

    async def test_it_should_know_if_it_is_ordered_or_not(self, repo, stored_entities):
        async with repo:
            assert repo.objects.order_by("created_at").ordered
            assert not repo.objects.filter(foo__startswith="bar").ordered

    async def test_it_should_get_an_entity(self, repo, stored_entities):
        async with repo:
            result = await repo.objects.get(foo="baz1")
            assert result == stored_entities[1]

    async def test_it_should_fail_to_get_an_entity_when_multiple_returned(self, repo, stored_entities):
        async with repo:
            with pytest.raises(repo.MultipleResultsFound):
                await repo.objects.get(foo__lte="bar3")

    async def test_it_should_fail_to_get_an_entity_when_none_returned(self, repo, stored_entities):
        async with repo:
            with pytest.raises(repo.objects.NotFound):
                await repo.objects.get(foo__lt="bar0")

    async def test_it_should_get_the_first_of_filtered_entities(self, repo, stored_entities):
        async with repo:
            result = await repo.objects.filter(foo__gt="bar1").order_by("foo").first()

            assert result == stored_entities[2]

    async def test_it_should_get_none_of_filtered_entities(self, repo, stored_entities):
        async with repo:
            result = repo.objects.filter(foo__gt="bar1").order_by("foo").none()

            assert await alist(result) == []

    async def test_it_should_get_none_for_first_of_empty_query(self, repo, stored_entities):
        async with repo:
            result = await repo.objects.filter(foo__lt="bar0").order_by("foo").first()

            assert result is None

    async def test_it_should_get_by_index(self, repo, stored_entities):
        async with repo:
            result = await repo.objects.order_by("num").getitem(2)
            assert result == stored_entities[2]

    async def test_it_should_get_by_index_from_cached_query(self, repo, stored_entities):
        async with repo:
            query = repo.objects.order_by("num")
            await alist(query)
            result = await query.getitem(2)
            assert result == stored_entities[2]

    async def test_it_should_fail_to_get_by_out_of_range_index(self, repo, stored_entities):
        async with repo:
            with pytest.raises(IndexError):
                await repo.objects.order_by("num").getitem(99)

    async def test_it_should_fail_to_get_by_negative_index(self, repo, stored_entities):
        async with repo:
            with pytest.raises(IndexError):
                await repo.objects.order_by("num").getitem(-2)

    async def test_it_should_fail_to_get_by_non_integer_index(self, repo, stored_entities):
        async with repo:
            with pytest.raises(TypeError):
                await repo.objects.order_by("num").getitem("foo")

    async def test_it_should_get_a_slice_of_a_closed_slice(self, repo, stored_entities):
        async with repo:
            result = await repo.objects.order_by("num").slice(1, 5).slice(1, 2).as_list()
            assert result == stored_entities[1:5][1:2]

    async def test_it_should_slice_a_cached_query(self, repo, stored_entities):
        async with repo:
            query = repo.objects.order_by("num").all()
            await alist(query)
            result = await query.slice(1, 3).as_list()
            assert result == stored_entities[1:3]

    async def test_it_should_repr_an_uncached_query(self, repo, stored_entities):
        async with repo:
            query = repo.objects.filter(num__lt=2).order_by("num")
            result = repr(query)
            expected = "<InMemoryEntityQuery ['...Query has not run...']>"
            assert result == expected

    async def test_it_should_repr_a_short_cached_query(self, repo, stored_entities):
        async with repo:
            query = repo.objects.filter(num__lt=2).order_by("num")
            await alist(query)
            result = repr(query)
            expected = "<InMemoryEntityQuery [Entity(id=UUID('de509355-5376-5405-a36d-91caed2ba8d1'), foo='bar0', num=0, is_odd=False, oddish=None, created_at=datetime.datetime(2023, 12, 15, 12, 0, tzinfo=<UTC>), finished_at=None), Entity(id=UUID('8db9b404-f276-5674-8006-12b74a8c62e3'), foo='baz1', num=1, is_odd=True, oddish=True, created_at=datetime.datetime(2023, 12, 15, 11, 0, tzinfo=<UTC>), finished_at=None)]>"
            assert result == expected

    async def test_it_should_repr_a_long_cached_query(self, repo, stored_entities):
        async with repo:
            query = repo.objects.order_by("num").all()
            await alist(query)
            result = repr(query)
            expected = "<InMemoryEntityQuery [Entity(id=UUID('de509355-5376-5405-a36d-91caed2ba8d1'), foo='bar0', num=0, is_odd=False, oddish=None, created_at=datetime.datetime(2023, 12, 15, 12, 0, tzinfo=<UTC>), finished_at=None), Entity(id=UUID('8db9b404-f276-5674-8006-12b74a8c62e3'), foo='baz1', num=1, is_odd=True, oddish=True, created_at=datetime.datetime(2023, 12, 15, 11, 0, tzinfo=<UTC>), finished_at=None), Entity(id=UUID('745da407-8c19-59d1-9a0e-8be54c7ac605'), foo='bar2', num=2, is_odd=False, oddish=None, created_at=datetime.datetime(2023, 12, 15, 10, 0, tzinfo=<UTC>), finished_at=None), '...(remaining elements truncated)...']>"
            assert result == expected
