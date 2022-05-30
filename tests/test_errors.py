import pytest

from async_firebase.errors import (
    DeadlineExceededError,
    NotFoundError,
    PermissionDeniedError,
    ResourceExhaustedError,
    UnauthenticatedError,
    UnavailableError,
    UnknownError,
)


@pytest.mark.parametrize("err_cls", (
    DeadlineExceededError,
    NotFoundError,
    PermissionDeniedError,
    ResourceExhaustedError,
    UnauthenticatedError,
    UnavailableError,
    UnknownError,
))
def test_create_firebase_error(err_cls):
    with pytest.raises(err_cls) as e:
        raise err_cls("MESSAGE")
    assert e.type is err_cls
