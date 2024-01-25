# ruff: noqa: D100, D101, D102, D103
from io import BytesIO

import pytest

from steerage.filestorages.base import AbstractFileStorage
from steerage.filestorages.memdb import build_memdb_test_repo
from steerage.filestorages.s3 import build_s3_test_repo

STORAGE_FACTORIES = [
    build_memdb_test_repo,
    build_s3_test_repo,
]


# By parametrizing the repo fixture, we can re-use the tests against
# each kind of repository:
@pytest.fixture(params=STORAGE_FACTORIES)
async def store(request, config):
    async with request.param(request) as repo_inst:
        yield repo_inst


@pytest.fixture
def key() -> str:
    return "foo"


@pytest.fixture
def value() -> bytes:
    return b"hello world"


@pytest.fixture
def buffer(value: bytes) -> BytesIO:
    return BytesIO(value)


@pytest.fixture
async def stored_buffer(store: AbstractFileStorage, key: str, buffer: BytesIO) -> BytesIO:
    await store.write(key, buffer)

    buffer.seek(0)

    return buffer


@pytest.mark.slow
class TestFileStorageImplementations:
    async def test_it_should_write_and_read_to_a_key(
        self, store: AbstractFileStorage, buffer: BytesIO, key: str, value: bytes
    ):
        await store.write(key, buffer)

        result = await store.read(key)

        assert result == value

    async def test_it_should_happily_write_to_a_key_twice(
        self, store: AbstractFileStorage, stored_buffer: BytesIO, key: str
    ):
        new_value = b"hello again"
        new_buffer = BytesIO(new_value)

        await store.write(key, new_buffer)

        result = await store.read(key)

        assert result == new_value

    async def test_it_should_delete_a_key(self, store: AbstractFileStorage, key: str, stored_buffer: BytesIO):
        await store.delete(key)

        with pytest.raises(store.NotFound):
            await store.read(key)

    async def test_it_should_happily_delete_a_nonexistent_buffer(self, store: AbstractFileStorage, key: str):
        await store.delete(key)  # this is a no-op
        with pytest.raises(store.NotFound):
            await store.read(key)

    async def test_it_should_raise_not_found_on_absent_key(self, store: AbstractFileStorage, key: str):
        with pytest.raises(store.NotFound):
            await store.read(key)
