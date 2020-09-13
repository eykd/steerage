from steerage.base import DocumentStorage


class MemoryObjectStorage(DocumentStorage):
    prefix = ""

    def __init__(self):
        self.objects = {}

    def store_document(self, identifier, document):
        self.objects[identifier] = document

    def retrieve_document(self, identifier):
        try:
            return self.objects[identifier]
        except KeyError:
            raise self.DoesNotExist(identifier)

    def remove_document(self, identifier):
        try:
            del self.objects[identifier]
        except KeyError:
            raise self.DoesNotExist(identifier)

    def list_keys(self):
        return self.objects.keys()
