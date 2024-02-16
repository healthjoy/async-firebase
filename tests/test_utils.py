import pytest

from async_firebase.messages import (
    AndroidConfig,
    AndroidNotification,
    APNSConfig,
    APNSPayload,
    Aps,
    ApsAlert,
    Message,
    Notification,
    PushNotification,
)
from async_firebase.utils import (
    cleanup_firebase_message,
    join_url,
    remove_null_values,
)

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "data, exp_result",
    (
        (
            {
                "android": {},
                "apns": {},
                "condition": None,
                "data": {},
                "notification": {},
                "token": None,
                "topic": None,
                "webpush": None,
            },
            {},
        ),
        ({"key_1": None, "key_2": "value_2", "key_3": []}, {"key_2": "value_2"}),
        (
            {
                "falsy_string": "",
                "falsy_int": 0,
                "falsy_bool": False,
                "falsy_float": 0.0,
                "falsy_dict": {},
                "falsy_list": [],
            },
            {
                "falsy_string": "",
                "falsy_int": 0,
                "falsy_bool": False,
                "falsy_float": 0.0,
            },
        ),
        ({}, {}),
        (
            {
                "key_1": {
                    "sub_key_1": {},
                    "sub_key_2": None,
                    "sub_key_3": [],
                },
                "key_2": None,
            },
            {"key_1": {"sub_key_1": {}, "sub_key_2": None, "sub_key_3": []}},
        ),
    ),
)
def test_remove_null_values(data, exp_result):
    result = remove_null_values(data)
    assert result == exp_result


@pytest.mark.parametrize(
    "firebase_message, exp_result",
    (
        (
            AndroidNotification(title="push-title", body="push-body"),
            {"title": "push-title", "body": "push-body"},
        ),
        (
            AndroidConfig(collapse_key="group", priority="normal", ttl="3600s"),
            {"collapse_key": "group", "priority": "normal", "ttl": "3600s"},
        ),
        (
            ApsAlert(title="push-title", body="push-body"),
            {"title": "push-title", "body": "push-body"},
        ),
        (Aps(alert="alert", badge=9), {"alert": "alert", "badge": 9}),
        (
            APNSPayload(aps=Aps(alert="push-text", custom_data={"foo": "bar"})),
            {"aps": {"alert": "push-text", "custom_data": {"foo": "bar"}}},
        ),
        (
            APNSConfig(headers={"x-header": "x-data"}),
            {"headers": {"x-header": "x-data"}},
        ),
        (
            Notification(title="push-title", body="push-body"),
            {"title": "push-title", "body": "push-body"},
        ),
        (
            Notification(title="push-title", body="push-body", image="https://cdn.domain.com/public.image.png"),
            {"title": "push-title", "body": "push-body", "image": "https://cdn.domain.com/public.image.png"},
        ),
        (
            Message(
                token="qwerty",
                notification=Notification(title="push-title", body="push-body"),
                apns=APNSConfig(
                    headers={"hdr": "qwe"},
                    payload=APNSPayload(
                        aps=Aps(
                            sound="generic",
                        ),
                    ),
                ),
            ),
            {
                "token": "qwerty",
                "notification": {"title": "push-title", "body": "push-body"},
                "apns": {
                    "headers": {"hdr": "qwe"},
                    "payload": {"aps": {"sound": "generic"}},
                },
            },
        ),
        (
            PushNotification(
                message=Message(
                    token="secret-token",
                    notification=Notification(title="push-title", body="push-body"),
                    android=AndroidConfig(
                        collapse_key="group",
                        notification=AndroidNotification(title="android-push-title", body="android-push-body"),
                    ),
                )
            ),
            {
                "message": {
                    "token": "secret-token",
                    "notification": {"title": "push-title", "body": "push-body"},
                    "android": {
                        "collapse_key": "group",
                        "notification": {
                            "title": "android-push-title",
                            "body": "android-push-body",
                        },
                    },
                },
                "validate_only": False,
            },
        ),
        (
            PushNotification(
                message=Message(
                    token="secret-token",
                    android=AndroidConfig(
                        collapse_key="group",
                        notification=AndroidNotification(title="android-push-title", body="android-push-body"),
                    ),
                    apns=APNSConfig(
                        headers={
                            "apns-expiration": "1621594859",
                            "apns-priority": "5",
                            "apns-collapse-id": "ENTITY_UPDATED",
                        },
                        payload={
                            "aps": {
                                "alert": "push-text",
                                "badge": 5,
                                "sound": "default",
                                "content-available": True,
                                "category": "NEW_MESSAGE",
                                "mutable-content": False,
                            },
                            "custom_attr_1": "value_1",
                            "custom_attr_2": 42,
                        },
                    ),
                )
            ),
            {
                "message": {
                    "token": "secret-token",
                    "android": {
                        "collapse_key": "group",
                        "notification": {
                            "title": "android-push-title",
                            "body": "android-push-body",
                        },
                    },
                    "apns": {
                        "headers": {
                            "apns-expiration": "1621594859",
                            "apns-priority": "5",
                            "apns-collapse-id": "ENTITY_UPDATED",
                        },
                        "payload": {
                            "aps": {
                                "alert": "push-text",
                                "badge": 5,
                                "sound": "default",
                                "content-available": True,
                                "category": "NEW_MESSAGE",
                                "mutable-content": False,
                            },
                            "custom_attr_1": "value_1",
                            "custom_attr_2": 42,
                        },
                    },
                },
                "validate_only": False,
            },
        ),
    ),
)
def test_cleanup_firebase_message(firebase_message, exp_result):
    result = cleanup_firebase_message(firebase_message)
    assert result == exp_result


@pytest.mark.parametrize(
    "base, parts, params, leading_slash, trailing_slash, exp_result",
    (
        ("http://base.ai", ["a", "b"], None, False, False, "http://base.ai/a/b"),
        ("http://base.ai", ["foo", 42], None, False, False, "http://base.ai/foo/42"),
        (
            "http://base.ai",
            ["foo", "bar"],
            {"q": "test"},
            False,
            False,
            "http://base.ai/foo/bar?q=test",
        ),
        (
            "base_path/path_1",
            ["foo", "bar"],
            None,
            True,
            False,
            "/base_path/path_1/foo/bar",
        ),
        (
            "http://base.ai",
            ["foo", "bar"],
            None,
            False,
            True,
            "http://base.ai/foo/bar/",
        ),
        (
            "base_path/path_1",
            ["foo", 42],
            {"q": "test"},
            True,
            True,
            "/base_path/path_1/foo/42/?q=test",
        ),
        (
            "base_path/path_1",
            [],
            {"q": "test"},
            True,
            False,
            "/base_path/path_1?q=test",
        ),
        (
            "http://base",
            ["message:send"],
            None,
            False,
            False,
            "http://base/message:send",
        ),
    ),
)
def test_join_url_common_flows(base, parts, params, leading_slash, trailing_slash, exp_result):
    result = join_url(base, *parts, params=params, leading_slash=leading_slash, trailing_slash=trailing_slash)
    assert result == exp_result
