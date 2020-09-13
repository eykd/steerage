import pytest
from steerage import base


def test_it_should_not_instantiate_document_storage():
    with pytest.raises(TypeError):
        base.DocumentStorage()
