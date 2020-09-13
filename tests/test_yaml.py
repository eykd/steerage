from collections import OrderedDict

import pytest
from steerage import yaml


@pytest.fixture
def tmpstream(tmpdir):
    with open(tmpdir / 'foo.yaml', 'w+') as fo:
        yield fo


def test_it_should_dump_a_document(tmpstream):
    yaml.dump_document_to_yaml({'foo': {'bar': 'blah', 'baz': 'boo'}}, tmpstream)
    tmpstream.seek(0)
    assert tmpstream.read() == 'foo:\n  bar: blah\n  baz: boo\n'


def test_it_should_dump_an_ordered_dict(tmpstream):
    yaml.dump_document_to_yaml(OrderedDict({'foo': {'bar': 'blah', 'baz': 'boo'}}), tmpstream)
    tmpstream.seek(0)
    assert tmpstream.read() == 'foo:\n  bar: blah\n  baz: boo\n'
