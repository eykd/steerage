import funcy as fn
from path import Path
from steerage.base import DocumentStorage
from steerage.yaml import (dump_document_to_yaml, dump_documents_to_yaml,
                           load_document_from_yaml, load_documents_from_yaml)

from configobj import ConfigObj


class YamlDirStorage(DocumentStorage):
    prefix = ""

    def __init__(self, path):
        self.path = Path(path)
        self.path.makedirs_p()

    def store_document(self, identifier, document):
        with open(self.get_filepath(identifier), "w") as fo:
            dump_document_to_yaml(document, fo)

    def retrieve_document(self, identifier):
        try:
            with open(self.get_filepath(identifier)) as fi:
                return load_document_from_yaml(fi)
        except FileNotFoundError:
            raise self.DoesNotExist(identifier)

    def remove_document(self, identifier):
        try:
            self.get_filepath(identifier).remove()
        except FileNotFoundError:
            raise self.DoesNotExist(identifier)

    def list_keys(self):
        for name in self.path.files("*.yaml"):
            yield name.stem

    def get_filepath(self, identifier):
        return self.path / f"{self.prefix}{identifier}.yaml"


class YamlFileListStorage(DocumentStorage):
    def __init__(self, path):
        self.path = Path(path)
        self.path.dirname().makedirs_p()
        self.path.touch()

    def store_document(self, identifier, document):
        self.append_document(identifier, document)

    def append_document(self, identifier, document):
        documents = self.load()
        documents.append({"id": identifier, "document": document})
        self.write(documents)

    def prepend_document(self, identifier, document):
        documents = self.load()
        documents.insert(0, {"id": identifier, "document": document})
        self.write(documents)

    def retrieve_document(self, identifier):
        documents = self.load()
        result = fn.first(doc for doc in documents if doc["id"] == identifier)
        if result is None:
            raise self.DoesNotExist(identifier)
        else:
            return result["document"]

    def remove_document(self, identifier):
        documents = self.load()
        mod = [doc for doc in documents if doc["id"] != identifier]
        if len(mod) == len(documents):
            raise self.DoesNotExist(identifier)
        else:
            self.write(mod)

    def list_keys(self):
        documents = self.load()
        return [doc['id'] for doc in documents]

    def load(self):
        with open(self.path) as fi:
            return list(load_documents_from_yaml(fi))

    def write(self, documents):
        with open(self.path, "w") as fo:
            dump_documents_to_yaml(documents, fo)


class ConfigStorage(DocumentStorage):
    def __init__(self, path=None):
        self.config = ConfigObj(path if path is None else str(path))

    def store_document(self, identifier, document):
        self.config[identifier] = document
        self.config.write()

    def retrieve_document(self, identifier):
        try:
            return dict(self.config[identifier])
        except KeyError:
            raise self.DoesNotExist(identifier)

    def remove_document(self, identifier):
        try:
            del self.config[identifier]
        except KeyError:
            raise self.DoesNotExist(identifier)
        else:
            self.config.write()

    def list_keys(self):
        return self.config.keys()
