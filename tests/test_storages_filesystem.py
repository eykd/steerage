import pytest
import yaml
from steerage.dbs.filesystem import (ConfigStorage, YamlDirStorage,
                                     YamlFileListStorage)


@pytest.fixture
def yaml_dir_db(tmpdir):
    return YamlDirStorage(tmpdir)


@pytest.fixture
def yaml_fn(tmpdir):
    return tmpdir / 'foo.yaml'


@pytest.fixture
def yaml_file_db(tmpdir, yaml_fn):
    return YamlFileListStorage(yaml_fn)


@pytest.fixture
def config_fn(tmpdir):
    return tmpdir / 'foo.ini'


@pytest.fixture
def config_file_db(tmpdir, config_fn):
    return ConfigStorage(config_fn)


class TestYamlDirStorage:
    def test_it_should_store_yaml_in_a_directory(self, yaml_dir_db):
        ident = "foobar"
        document = {"foo": "bar"}
        yaml_dir_db.store_document(ident, document)
        fn = yaml_dir_db.get_filepath(ident)
        assert fn.exists()
        assert "foo: bar" in fn.read_text()

    def test_it_should_remove_yaml_from_a_directory(self, yaml_dir_db):
        ident = "foobar"
        document = {"foo": "bar"}
        yaml_dir_db.store_document(ident, document)
        yaml_dir_db.remove_document(ident)
        fn = yaml_dir_db.get_filepath(ident)
        assert not fn.exists()

    def test_it_should_not_remove_nonexistent_yaml_from_a_directory(self, yaml_dir_db):
        ident = "foobar"
        with pytest.raises(yaml_dir_db.DoesNotExist):
            yaml_dir_db.remove_document(ident)

    def test_it_should_retrieve_stored_yaml(self, yaml_dir_db):
        ident = "foobar"
        document = {"foo": "bar"}
        yaml_dir_db.store_document(ident, document)
        result = yaml_dir_db.retrieve_document(ident)
        assert result == document

    def test_it_should_list_keys_of_stored_yaml(self, yaml_dir_db):
        document = {}
        yaml_dir_db.store_document('foo', document)
        yaml_dir_db.store_document('bar', document)
        result = yaml_dir_db.list_keys()
        assert set(result) == {'foo', 'bar'}

    def test_it_should_not_retrieve_nonexistent_yaml(self, yaml_dir_db):
        ident = "foobar"
        with pytest.raises(yaml_dir_db.DoesNotExist):
            yaml_dir_db.retrieve_document(ident)


class TestYamlFileListStorage:
    def test_it_should_store_yaml_in_a_file(self, yaml_file_db, yaml_fn):
        ident = "foobar"
        document = {"foo": "bar"}
        yaml_file_db.store_document(ident, document)
        assert yaml_fn.exists()
        result = list(yaml.safe_load_all(yaml_fn.read_text()))
        assert result == [{"id": ident, "document": document}]
        ident2 = "foobar2"
        document2 = {"foo2": "bar"}
        yaml_file_db.store_document(ident2, document2)
        result = list(yaml.safe_load_all(yaml_fn.read_text()))
        assert result == [
            {"id": ident, "document": document},
            {"id": ident2, "document": document2},
        ]

    def test_it_should_prepend_yaml_in_a_file(self, yaml_file_db, yaml_fn):
        ident = "foobar"
        document = {"foo": "bar"}
        yaml_file_db.append_document(ident, document)
        ident2 = "foobar2"
        document2 = {"foo2": "bar"}
        yaml_file_db.prepend_document(ident2, document2)
        result = list(yaml.safe_load_all(yaml_fn.read_text()))
        assert result == [
            {"id": ident2, "document": document2},
            {"id": ident, "document": document},
        ]

    def test_it_should_store_multiple_yaml_in_a_file(self, yaml_file_db, yaml_fn):
        ident = "foobar"
        document = {"foo": "bar"}
        yaml_file_db.append_document(ident, document)
        ident2 = "blah"
        document2 = {"boo": "baz"}
        yaml_file_db.append_document(ident2, document2)
        assert yaml_fn.exists()
        result = list(yaml.safe_load_all(yaml_fn.read_text()))
        assert result == [
            {"id": ident, "document": document},
            {"id": ident2, "document": document2},
        ]

    def test_it_should_remove_yaml_from_a_file(self, yaml_file_db, yaml_fn):
        ident = "foobar"
        document = {"foo": "bar"}
        yaml_file_db.append_document(ident, document)
        ident2 = "blah"
        document2 = {"boo": "baz"}
        yaml_file_db.append_document(ident2, document2)
        yaml_file_db.remove_document(ident2)
        assert yaml_fn.exists()
        result = list(yaml.safe_load_all(yaml_fn.read_text()))
        assert result == [{"id": ident, "document": document}]
        yaml_file_db.remove_document(ident)
        result = list(yaml.safe_load_all(yaml_fn.read_text()))
        assert result == []

    def test_it_should_not_remove_nonexistent_yaml_from_a_directory(self, yaml_file_db):
        ident = "foobar"
        with pytest.raises(yaml_file_db.DoesNotExist):
            yaml_file_db.remove_document(ident)

    def test_it_should_retrieve_stored_yaml(self, yaml_file_db):
        ident = "foobar"
        document = {"foo": "bar"}
        yaml_file_db.append_document(ident, document)
        ident2 = "blah"
        document2 = {"boo": "baz"}
        yaml_file_db.append_document(ident2, document2)
        result = yaml_file_db.retrieve_document(ident)
        assert result == document
        result = yaml_file_db.retrieve_document(ident2)
        assert result == document2

    def test_it_should_not_retrieve_nonexistent_yaml(self, yaml_file_db):
        ident = "foobar"
        with pytest.raises(yaml_file_db.DoesNotExist):
            yaml_file_db.retrieve_document(ident)

    def test_it_should_list_keys_of_stored_yaml(self, yaml_file_db):
        document = {}
        yaml_file_db.store_document('foo', document)
        yaml_file_db.store_document('bar', document)
        result = yaml_file_db.list_keys()
        assert set(result) == {'foo', 'bar'}


class TestConfigStorage:
    def test_it_should_store_data_in_a_config_file(self, config_file_db, config_fn):
        ident = "foobar"
        document = {"foo": "bar"}
        config_file_db.store_document(ident, document)
        assert config_fn.exists()
        assert "foo = bar" in config_fn.read_text()

    def test_it_should_remove_data_from_a_config_file(self, config_file_db, config_fn):
        ident = "foobar"
        document = {"foo": "bar"}
        config_file_db.store_document(ident, document)
        config_file_db.remove_document(ident)
        assert "foo = bar" not in config_fn.read_text()

    def test_it_should_not_remove_nonexistent_data_from_a_config_file(self, config_file_db):
        ident = "foobar"
        with pytest.raises(config_file_db.DoesNotExist):
            config_file_db.remove_document(ident)

    def test_it_should_retrieve_stored_data(self, config_file_db):
        ident = "foobar"
        document = {"foo": "bar"}
        config_file_db.store_document(ident, document)
        result = config_file_db.retrieve_document(ident)
        assert result == document

    def test_it_should_list_keys_of_stored_data(self, config_file_db):
        document = {}
        config_file_db.store_document('foo', document)
        config_file_db.store_document('bar', document)
        result = config_file_db.list_keys()
        assert set(result) == {'foo', 'bar'}

    def test_it_should_not_retrieve_nonexistent_data(self, config_file_db):
        ident = "foobar"
        with pytest.raises(config_file_db.DoesNotExist):
            config_file_db.retrieve_document(ident)
