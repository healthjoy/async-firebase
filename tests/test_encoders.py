import pytest

from async_firebase.encoders import aps_encoder
from async_firebase.messages import Aps, ApsAlert


@pytest.mark.parametrize(
    "aps_obj, exp_result", (
        (
            Aps(
                alert="push text",
                badge=5,
                sound="default",
                content_available=True,
                category="NEW_MESSAGE",
                mutable_content=False
            ),
            {
                "aps": {
                    "alert": "push text",
                    "badge": 5,
                    "sound": "default",
                    "content-available": True,
                    "category": "NEW_MESSAGE",
                    "thread-id": None,
                    "mutable-content": False,
                },
            }
        ),
        (
            Aps(
                alert=ApsAlert(
                    title="push-title",
                    body="push-text",
                ),
                badge=5,
                sound="default",
                content_available=True,
                category="NEW_MESSAGE",
                mutable_content=False
            ),
            {
                "aps": {
                    "alert": {
                        "title": "push-title",
                        "body": "push-text",
                        "loc-key": None,
                        "loc-args": [],
                        "title-loc-key": None,
                        "title-loc-args": [],
                        "action-loc-key": None,
                        "launch-image": None,
                    },
                    "badge": 5,
                    "sound": "default",
                    "content-available": True,
                    "category": "NEW_MESSAGE",
                    "thread-id": None,
                    "mutable-content": False,
                },
            }
        ),
        (
            Aps(
                alert="push text",
                badge=5,
                sound="default",
                content_available=True,
                category="NEW_MESSAGE",
                mutable_content=False,
                custom_data={
                    "str_attr": "value_1",
                    "int_attr": 42,
                    "float_attr": 42.42,
                    "list_attr": [1, 2, 3],
                    "dict_attr": {"a": "A", "b": "B"},
                    "bool_attr": False,
                }
            ),
            {
                "aps": {
                    "alert": "push text",
                    "badge": 5,
                    "sound": "default",
                    "content-available": True,
                    "category": "NEW_MESSAGE",
                    "thread-id": None,
                    "mutable-content": False,
                },
                "str_attr": "value_1",
                "int_attr": 42,
                "float_attr": 42.42,
                "list_attr": [1, 2, 3],
                "dict_attr": {"a": "A", "b": "B"},
                "bool_attr": False,
            }
        ),
        (None, None)
    )
)
def test_aps_encoder(aps_obj, exp_result):
    aps_dict = aps_encoder(aps_obj)
    assert aps_dict == exp_result
