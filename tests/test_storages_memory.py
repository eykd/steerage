import pytest
from steerage.dbs.memory import MemoryObjectStorage


@pytest.fixture
def memory_db():
    return MemoryObjectStorage()


class TestMemoryObjectStorage:
    def test_it_should_store_and_retrieve_data(self, memory_db):
        ident = "foobar"
        document = {"foo": "bar"}
        memory_db.store_document(ident, document)
        result = memory_db.retrieve_document(ident)
        assert result == document

    def test_it_should_list_keys_of_stored_data(self, memory_db):
        document = {}
        memory_db.store_document('foo', document)
        memory_db.store_document('bar', document)
        result = memory_db.list_keys()
        assert set(result) == {'foo', 'bar'}

    def test_it_should_not_retrieve_nonexistent_data(self, memory_db):
        ident = "foobar"
        with pytest.raises(memory_db.DoesNotExist):
            memory_db.retrieve_document(ident)

    def test_it_should_remove_data_from_memory(self, memory_db):
        ident = "foobar"
        document = {"foo": "bar"}
        memory_db.store_document(ident, document)
        memory_db.remove_document(ident)
        with pytest.raises(memory_db.DoesNotExist):
            memory_db.retrieve_document(ident)

    def test_it_should_not_remove_nonexistent_data_from_memory(self, memory_db):
        ident = "foobar"
        with pytest.raises(memory_db.DoesNotExist):
            memory_db.remove_document(ident)
