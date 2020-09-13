from collections import OrderedDict

import yaml
from yaml import YAMLError  # noqa: F401


class CustomYamlDumper(yaml.SafeDumper):
    def represent_dict_preserve_order(self, data):
        return self.represent_dict(data.items())


CustomYamlDumper.add_representer(
    OrderedDict, CustomYamlDumper.represent_dict_preserve_order
)


_yaml_kwargs = {"sort_keys": False, "indent": 2, "Dumper": CustomYamlDumper}


def dump_document_to_yaml(data, stream=None):
    return yaml.dump(data, stream, **_yaml_kwargs)


def dump_documents_to_yaml(documents, stream=None):
    return yaml.dump_all(documents, stream, **_yaml_kwargs)


def load_document_from_yaml(stream):
    return yaml.safe_load(stream)


def load_documents_from_yaml(stream):
    return yaml.safe_load_all(stream)
