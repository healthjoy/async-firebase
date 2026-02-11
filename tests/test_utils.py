from unittest import mock

import httpx
import pytest

from async_firebase.errors import (
    AsyncFirebaseError,
    DeadlineExceededError,
    InternalError,
    InvalidArgumentError,
    QuotaExceededError,
    SenderIdMismatchError,
    ThirdPartyAuthError,
    UnavailableError,
    UnknownError,
    UnregisteredError,
)
from async_firebase.messages import (
    AndroidConfig,
    AndroidNotification,
    APNSConfig,
    APNSPayload,
    Aps,
    ApsAlert,
    FCMResponse,
    Message,
    Notification,
    PushNotification,
)
from async_firebase.utils import (
    FCMResponseHandler,
    FCM_ERROR_TYPE_PREFIX,
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
        (
            "https://fcm.googleapis.com",
            ["/v1/projects/my-project", "messages:send"],
            None,
            False,
            False,
            "https://fcm.googleapis.com/v1/projects/my-project/messages:send",
        ),
    ),
)
def test_join_url_common_flows(base, parts, params, leading_slash, trailing_slash, exp_result):
    result = join_url(base, *parts, params=params, leading_slash=leading_slash, trailing_slash=trailing_slash)
    assert result == exp_result


# ── FCMResponseHandler error handling ───────────────────────────────


def _make_http_status_error(status_code, json_body=None, content=b""):
    """Helper to create an httpx.HTTPStatusError with a mock response."""
    request = httpx.Request("POST", "https://fcm.googleapis.com/v1/test")
    response = httpx.Response(status_code, request=request, content=content)

    if json_body is not None:
        # Mock the json() method to return our data
        response = mock.MagicMock(spec=httpx.Response)
        response.status_code = status_code
        response.content = content
        response.json.return_value = json_body

    return httpx.HTTPStatusError(
        message=f"Server error {status_code}",
        request=request,
        response=response,
    )


class TestFCMResponseHandler:
    """Tests for FCMResponseHandler error dispatch."""

    def test_handle_timeout_error(self):
        handler = FCMResponseHandler()
        error = httpx.ReadTimeout("Connection read timed out")
        result = handler.handle_error(error)

        assert isinstance(result, FCMResponse)
        assert not result.success
        assert isinstance(result.exception, DeadlineExceededError)
        assert "Timed out" in str(result.exception)

    def test_handle_connect_error(self):
        handler = FCMResponseHandler()
        error = httpx.ConnectError("Failed to connect")
        result = handler.handle_error(error)

        assert isinstance(result, FCMResponse)
        assert not result.success
        assert isinstance(result.exception, UnavailableError)
        assert "Failed to establish a connection" in str(result.exception)

    def test_handle_generic_http_error_without_response(self):
        handler = FCMResponseHandler()
        error = httpx.DecodingError("decode failure")
        result = handler.handle_error(error)

        assert isinstance(result, FCMResponse)
        assert not result.success
        assert isinstance(result.exception, UnknownError)
        assert "Unknown error" in str(result.exception)

    def test_handle_http_status_error_with_fcm_error_type(self):
        """When the response contains an FCM-specific error type, use the FCM error mapping."""
        handler = FCMResponseHandler()
        error = _make_http_status_error(
            400,
            json_body={
                "error": {
                    "code": 400,
                    "message": "The registration token is not a valid FCM registration token",
                    "status": "INVALID_ARGUMENT",
                    "details": [
                        {"@type": FCM_ERROR_TYPE_PREFIX, "errorCode": "UNREGISTERED"},
                    ],
                }
            },
        )
        result = handler.handle_error(error)

        assert isinstance(result, FCMResponse)
        assert isinstance(result.exception, UnregisteredError)

    def test_handle_http_status_error_with_quota_exceeded(self):
        handler = FCMResponseHandler()
        error = _make_http_status_error(
            429,
            json_body={
                "error": {
                    "code": 429,
                    "message": "Quota exceeded",
                    "status": "RESOURCE_EXHAUSTED",
                    "details": [
                        {"@type": FCM_ERROR_TYPE_PREFIX, "errorCode": "QUOTA_EXCEEDED"},
                    ],
                }
            },
        )
        result = handler.handle_error(error)

        assert isinstance(result, FCMResponse)
        assert isinstance(result.exception, QuotaExceededError)

    def test_handle_http_status_error_with_sender_id_mismatch(self):
        handler = FCMResponseHandler()
        error = _make_http_status_error(
            403,
            json_body={
                "error": {
                    "code": 403,
                    "message": "Sender ID mismatch",
                    "status": "PERMISSION_DENIED",
                    "details": [
                        {"@type": FCM_ERROR_TYPE_PREFIX, "errorCode": "SENDER_ID_MISMATCH"},
                    ],
                }
            },
        )
        result = handler.handle_error(error)

        assert isinstance(result, FCMResponse)
        assert isinstance(result.exception, SenderIdMismatchError)

    def test_handle_http_status_error_with_third_party_auth_error(self):
        handler = FCMResponseHandler()
        error = _make_http_status_error(
            401,
            json_body={
                "error": {
                    "code": 401,
                    "message": "Third party auth error",
                    "status": "UNAUTHENTICATED",
                    "details": [
                        {"@type": FCM_ERROR_TYPE_PREFIX, "errorCode": "THIRD_PARTY_AUTH_ERROR"},
                    ],
                }
            },
        )
        result = handler.handle_error(error)

        assert isinstance(result, FCMResponse)
        assert isinstance(result.exception, ThirdPartyAuthError)

    def test_handle_http_status_error_with_apns_auth_error(self):
        handler = FCMResponseHandler()
        error = _make_http_status_error(
            401,
            json_body={
                "error": {
                    "code": 401,
                    "message": "APNs auth error",
                    "status": "UNAUTHENTICATED",
                    "details": [
                        {"@type": FCM_ERROR_TYPE_PREFIX, "errorCode": "APNS_AUTH_ERROR"},
                    ],
                }
            },
        )
        result = handler.handle_error(error)

        assert isinstance(result, FCMResponse)
        assert isinstance(result.exception, ThirdPartyAuthError)

    def test_handle_http_status_error_falls_back_to_status_code(self):
        """When no FCM error type is present, fall back to HTTP status code mapping."""
        handler = FCMResponseHandler()
        error = _make_http_status_error(
            500,
            json_body={
                "error": {
                    "code": 500,
                    "message": "Internal server error",
                    "status": "INTERNAL",
                }
            },
        )
        result = handler.handle_error(error)

        assert isinstance(result, FCMResponse)
        assert isinstance(result.exception, InternalError)

    def test_handle_http_status_error_unknown_status_code(self):
        """When HTTP status code is not in the mapping, fall back to UnknownError."""
        handler = FCMResponseHandler()
        error = _make_http_status_error(
            418,
            json_body={
                "error": {
                    "message": "I'm a teapot",
                }
            },
        )
        result = handler.handle_error(error)

        assert isinstance(result, FCMResponse)
        assert isinstance(result.exception, UnknownError)

    def test_handle_http_status_error_non_json_response(self):
        """When the error response is not valid JSON, still produce an error."""
        handler = FCMResponseHandler()
        request = httpx.Request("POST", "https://fcm.googleapis.com/v1/test")
        response = httpx.Response(502, request=request, content=b"Bad Gateway")
        error = httpx.HTTPStatusError(
            message="Server error 502",
            request=request,
            response=response,
        )
        result = handler.handle_error(error)

        assert isinstance(result, FCMResponse)
        assert not result.success
        assert result.exception is not None
        assert "Unexpected HTTP response" in str(result.exception)

    def test_handle_response_success(self):
        handler = FCMResponseHandler()
        request = httpx.Request("POST", "https://fcm.googleapis.com/v1/test")
        response = httpx.Response(
            200,
            request=request,
            json={"name": "projects/test/messages/123"},
        )
        result = handler.handle_response(response)

        assert isinstance(result, FCMResponse)
        assert result.success
        assert result.message_id == "projects/test/messages/123"

    def test_get_fcm_error_type_empty_data(self):
        """_get_fcm_error_type should return None for empty error data."""
        handler = FCMResponseHandler()
        assert handler._get_fcm_error_type({}) is None
        assert handler._get_fcm_error_type(None) is None

    def test_get_fcm_error_type_no_matching_details(self):
        """_get_fcm_error_type should return None when no FCM error type in details."""
        handler = FCMResponseHandler()
        result = handler._get_fcm_error_type({
            "message": "some error",
            "details": [{"@type": "some.other.type", "errorCode": "SOMETHING"}],
        })
        assert result is None

    def test_get_fcm_error_type_no_details_key(self):
        """_get_fcm_error_type should return None when no details key at all."""
        handler = FCMResponseHandler()
        result = handler._get_fcm_error_type({"message": "some error"})
        assert result is None
