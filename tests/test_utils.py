import pytest

from async_firebase.messages import (
    AndroidConfig,
    AndroidNotification,
    APNSConfig,
    APNSPayload,
    Aps,
    ApsAlert,
    Message,
    MulticastMessage,
    Notification,
    PushNotification,
)
from async_firebase.utils import (
    cleanup_firebase_message,
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
        (
            MulticastMessage(
                tokens=["qwerty_1", "query_2"],
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
                "tokens": ["qwerty_1", "query_2"],
                "notification": {"title": "push-title", "body": "push-body"},
                "apns": {
                    "headers": {"hdr": "qwe"},
                    "payload": {"aps": {"sound": "generic"}},
                },
            },
        ),
(
            PushNotification(
                message=MulticastMessage(
                    tokens=["secret-token-1", "secret-token-2"],
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
                    "tokens": ["secret-token-1", "secret-token-2"],
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
