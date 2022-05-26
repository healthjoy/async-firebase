import pytest
from async_firebase.errors import UnknownError


def test_create_firebase_error():
    with pytest.raises(UnknownError) as e:
        raise UnknownError('MESSAGE')
    assert isinstance(e.value, UnknownError)
