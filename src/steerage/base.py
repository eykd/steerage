from abc import ABC, abstractmethod

from steerage.exceptions import DoesNotExist


class DocumentStorage(ABC):
    DoesNotExist = DoesNotExist

    @abstractmethod
    def store_document(self, identifier, document):  # pragma: no cover
        pass

    @abstractmethod
    def retrieve_document(self, identifier):  # pragma: no cover
        pass

    @abstractmethod
    def remove_document(self, identifier):  # pragma: no cover
        pass

    @abstractmethod
    def list_keys(self):  # pragma: no cover
        pass
