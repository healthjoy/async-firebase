import json
import uuid
from datetime import datetime
from unittest import mock

import pkg_resources
import pytest
from google.oauth2 import service_account
from pytest_httpx import HTTPXMock

from async_firebase.client import AsyncFirebaseClient
from async_firebase.errors import InternalError
from async_firebase.messages import (
    AndroidConfig,
    AndroidNotification,
    APNSConfig,
    APNSPayload,
    Aps,
    ApsAlert,
    FCMBatchResponse,
    FCMResponse,
    TopicManagementResponse,
    Message,
    WebpushConfig,
    WebpushNotification,
    WebpushFCMOptions,
    MulticastMessage,
    TopicManagementErrorInfo,
    Visibility,
)
from async_firebase.utils import FcmErrorCode


pytestmark = pytest.mark.asyncio


@pytest.fixture()
def fake_async_fcm_client():
    return AsyncFirebaseClient()


@pytest.fixture()
def fake_async_fcm_client_w_creds(fake_async_fcm_client, fake_service_account):
    client = AsyncFirebaseClient()
    client.creds_from_service_account_info(fake_service_account)
    return client


@pytest.fixture()
def fake_device_token(faker_):
    return faker_.bothify(text=f"{'?' * 12}:{'?' * 256}")


@pytest.fixture()
def fake_multi_device_tokens(faker_, request):
    return [faker_.bothify(text=f"{'?' * 12}:{'?' * 256}") for _ in range(request.param)]


async def fake__get_access_token():
    return "fake-jwt-token"


@pytest.mark.parametrize(
    "visibility_level, exp_visibility_level",
    (
        (Visibility.PRIVATE, Visibility.PRIVATE),
        (Visibility.PUBLIC, Visibility.PUBLIC),
        (Visibility.SECRET, Visibility.SECRET),
    )
)
def test_build_android_config(fake_async_fcm_client_w_creds, visibility_level, exp_visibility_level):
    android_config = fake_async_fcm_client_w_creds.build_android_config(
        priority="high",
        ttl=7200,
        collapse_key="something",
        restricted_package_name="some-package",
        data={"key_1": "value_1", "key_2": 100, "foo": None},
        color="red",
        sound="beep",
        tag="test",
        click_action="TOP_STORY_ACTIVITY",
        channel_id="some_channel_id",
        notification_count=7,
        visibility=visibility_level,
    )
    assert android_config == AndroidConfig(
        **{
            "priority": "high",
            "collapse_key": "something",
            "restricted_package_name": "some-package",
            "data": {"key_1": "value_1", "key_2": "100", "foo": "null"},
            "ttl": "7200s",
            "notification": AndroidNotification(
                **{
                    "color": "red",
                    "sound": "beep",
                    "tag": "test",
                    "click_action": "TOP_STORY_ACTIVITY",
                    "title": None,
                    "body": None,
                    "icon": None,
                    "body_loc_key": None,
                    "body_loc_args": [],
                    "title_loc_key": None,
                    "title_loc_args": [],
                    "channel_id": "some_channel_id",
                    "notification_count": 7,
                    "visibility": exp_visibility_level.value,
                }
            ),
        }
    )


def test_build_apns_config(fake_async_fcm_client_w_creds, freezer):
    apns_message = fake_async_fcm_client_w_creds.build_apns_config(
        priority="high",
        ttl=7200,
        apns_topic="test-topic",
        collapse_key="something",
        alert="alert-message",
        title="some-title",
        badge=0,
    )
    assert apns_message == APNSConfig(
        **{
            "headers": {
                "apns-expiration": str(int(datetime.utcnow().timestamp()) + 7200),
                "apns-priority": "10",
                "apns-topic": "test-topic",
                "apns-collapse-id": "something",
            },
            "payload": APNSPayload(
                **{
                    "aps": Aps(
                        **{
                            "alert": ApsAlert(title="some-title", body="alert-message"),
                            "badge": 0,
                            "sound": "default",
                            "content_available": None,
                            "category": None,
                            "thread_id": None,
                            "mutable_content": True,
                            "custom_data": {},
                        }
                    )
                }
            ),
        }
    )


async def test_prepare_headers(fake_async_fcm_client_w_creds):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    frozen_uuid = uuid.UUID(hex="6eadf1d38633427cb83dbb9be137f48c")
    fake_async_fcm_client_w_creds.get_request_id = lambda: str(frozen_uuid)
    headers = await fake_async_fcm_client_w_creds.prepare_headers()
    assert headers == {
        "Authorization": "Bearer fake-jwt-token",
        "Content-Type": "application/json; UTF-8",
        "X-Request-Id": str(frozen_uuid),
        "X-GOOG-API-FORMAT-VERSION": "2",
        "X-FIREBASE-CLIENT": "async-firebase/{0}".format(pkg_resources.get_distribution("async-firebase").version),
    }


async def test_push_android(fake_async_fcm_client_w_creds, fake_device_token, httpx_mock: HTTPXMock):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    creds = fake_async_fcm_client_w_creds._credentials
    httpx_mock.add_response(
        status_code=200,
        json={"name": f"projects/{creds.project_id}/messages/0:1612788010922733%7606eb247606eb23"},
    )
    android_config = fake_async_fcm_client_w_creds.build_android_config(
        priority="normal",
        ttl=604800,
        collapse_key="SALE",
        title="Sring SALE",
        body="Don't miss spring SALE",
        tag="spring-sale",
        notification_count=1,
        visibility=Visibility.PUBLIC
    )
    message = Message(android=android_config, token=fake_device_token)
    response = await fake_async_fcm_client_w_creds.send(message)
    assert isinstance(response, FCMResponse)
    assert response.success
    assert response.message_id == "projects/fake-mobile-app/messages/0:1612788010922733%7606eb247606eb23"


async def test_push_ios(fake_async_fcm_client_w_creds, fake_device_token, httpx_mock: HTTPXMock):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    creds = fake_async_fcm_client_w_creds._credentials
    httpx_mock.add_response(
        status_code=200,
        json={"name": f"projects/{creds.project_id}/messages/0:1612788010922733%7606eb247606eb24"},
    )
    apns_config = fake_async_fcm_client_w_creds.build_apns_config(
        priority="normal",
        apns_topic="test-push",
        collapse_key="push",
        badge=0,
        category="test-category",
        custom_data={"foo": "bar"},
    )
    message = Message(apns=apns_config, token=fake_device_token)
    response = await fake_async_fcm_client_w_creds.send(message)
    assert isinstance(response, FCMResponse)
    assert response.success
    assert response.message_id == "projects/fake-mobile-app/messages/0:1612788010922733%7606eb247606eb24"


async def test_send_android_dry_run(fake_async_fcm_client_w_creds, fake_device_token, httpx_mock: HTTPXMock):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    creds = fake_async_fcm_client_w_creds._credentials
    httpx_mock.add_response(
        status_code=200,
        json={"name": f"projects/{creds.project_id}/messages/fake_message_id"},
    )
    android_config = fake_async_fcm_client_w_creds.build_android_config(
        priority="high",
        ttl=2419200,
        collapse_key="push",
        data={"discount": "15%", "key_1": "value_1", "timestamp": "2021-02-24T12:00:15"},
        title="Store Changes",
        body="Recent store changes",
        visibility="PUBLIC"
    )
    message = Message(android=android_config, token=fake_device_token)
    response = await fake_async_fcm_client_w_creds.send(message, dry_run=True)
    assert isinstance(response, FCMResponse)
    assert response.success
    assert response.message_id == "projects/fake-mobile-app/messages/fake_message_id"


async def test_send_ios_dry_run(fake_async_fcm_client_w_creds, fake_device_token, httpx_mock: HTTPXMock):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    creds = fake_async_fcm_client_w_creds._credentials
    httpx_mock.add_response(
        status_code=200,
        json={"name": f"projects/{creds.project_id}/messages/fake_message_id"},
    )
    apns_config = fake_async_fcm_client_w_creds.build_apns_config(
        priority="normal",
        apns_topic="test-push",
        collapse_key="push",
        badge=0,
        category="test-category",
        custom_data={"foo": "bar"},
    )
    message = Message(apns=apns_config, token=fake_device_token)
    response = await fake_async_fcm_client_w_creds.send(message, dry_run=True)
    assert isinstance(response, FCMResponse)
    assert response.success
    assert response.message_id == "projects/fake-mobile-app/messages/fake_message_id"


async def test_send_unauthenticated(fake_async_fcm_client_w_creds, httpx_mock: HTTPXMock):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    httpx_mock.add_response(
        status_code=401,
        json={
            "error": {
                "code": 401,
                "message": "Request had invalid authentication credentials. "
                "Expected OAuth 2 access token, login cookie or other "
                "valid authentication credential. See "
                "https://developers.google.com/identity/sign-in/web/devconsole-project.",
                "status": "UNAUTHENTICATED",
            }
        },
    )
    apns_config = fake_async_fcm_client_w_creds.build_apns_config(
        priority="normal",
        apns_topic="test-push",
        collapse_key="push",
        badge=0,
        category="test-category",
        custom_data={"foo": "bar"},
    )
    message = Message(apns=apns_config, token="qwerty:ytrewq")
    fcm_response = await fake_async_fcm_client_w_creds.send(message)

    assert isinstance(fcm_response, FCMResponse)
    assert not fcm_response.success
    assert fcm_response.exception is not None
    assert fcm_response.exception.code == FcmErrorCode.UNAUTHENTICATED.value
    assert fcm_response.exception.cause.response.status_code == 401


async def test_send_data_has_not_been_provided(fake_async_fcm_client_w_creds):
    message = Message(token="device_id:device_token")
    with pytest.raises(ValueError):
        await fake_async_fcm_client_w_creds.send(message)


def test_creds_from_service_account_info(fake_async_fcm_client, fake_service_account):
    fake_async_fcm_client.creds_from_service_account_info(fake_service_account)
    assert isinstance(fake_async_fcm_client._credentials, service_account.Credentials)


def test_creds_from_service_account_file(fake_async_fcm_client, fake_service_account_file):
    fake_async_fcm_client.creds_from_service_account_file(fake_service_account_file)
    assert isinstance(fake_async_fcm_client._credentials, service_account.Credentials)


async def test_send_realistic_payload(fake_async_fcm_client_w_creds, fake_device_token, httpx_mock: HTTPXMock):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    creds = fake_async_fcm_client_w_creds._credentials
    httpx_mock.add_response(
        status_code=200,
        json={"name": f"projects/{creds.project_id}/messages/0:1612788010922733%7606eb247606eb24"},
    )
    apns_config: APNSConfig = fake_async_fcm_client_w_creds.build_apns_config(
        priority="normal",
        apns_topic="Your bucket has been updated",
        collapse_key="BUCKET_UPDATED",
        badge=1,
        category="CATEGORY_BUCKET_UPDATED",
        custom_data={
            "bucket_name": "3bc56ff12a",
            "bucket_link": "/link/to/bucket/3bc56ff12a",
            "aliases": ["happy_friends", "mobile_groups"],
            "updated_count": 1,
        },
        mutable_content=True,
        content_available=True,
    )
    message = Message(apns=apns_config, token=fake_device_token)
    await fake_async_fcm_client_w_creds.send(message)
    request_payload = json.loads(httpx_mock.get_requests()[0].read())
    assert request_payload == {
        "message": {
            "apns": {
                "headers": apns_config.headers,
                "payload": {
                    "aps": {
                        "badge": 1,
                        "category": "CATEGORY_BUCKET_UPDATED",
                        "content-available": True,
                        "mutable-content": True,
                    },
                    "bucket_name": "3bc56ff12a",
                    "bucket_link": "/link/to/bucket/3bc56ff12a",
                    "aliases": ["happy_friends", "mobile_groups"],
                    "updated_count": 1,
                },
            },
            "token": fake_device_token,
        },
        "validate_only": False,
    }


@pytest.mark.parametrize("fake_multi_device_tokens", (3,), indirect=True)
async def test_send_all(fake_async_fcm_client_w_creds, fake_multi_device_tokens: list, httpx_mock: HTTPXMock):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    creds = fake_async_fcm_client_w_creds._credentials
    response_data = (
        "\r\n--batch_llG_9dniIyeFXPERplIRPwpVYtn3RBa4\r\nContent-Type: application/http\r\nContent-ID: "
        "response-4440d691-7909-4346-af9a-b44f17638f6c\r\n\r\nHTTP/1.1 200 OK\r\nContent-Type: "
        "application/json; charset=UTF-8\r\nVary: Origin\r\nVary: X-Origin\r\nVary: Referer\r\n\r\n{\n  "
        f'"name": "projects/{creds.project_id}/messages/0:1612788010922733%7606eb247606eb24"\n}}\n\r\n'
        "--batch_llG_9dniIyeFXPERplIRPwpVYtn3RBa4\r\nContent-Type: application/http\r\nContent-ID: "
        "response-fdbc3fd2-4031-4c00-88d2-22c9523bb941\r\n\r\nHTTP/1.1 200 OK\r\nContent-Type: "
        "application/json; charset=UTF-8\r\nVary: Origin\r\nVary: X-Origin\r\nVary: Referer\r\n\r\n{\n  "
        f'"name": "projects/{creds.project_id}/messages/0:1612788010922733%7606eb247606eb25"\n}}\n\r\n'
        "--batch_llG_9dniIyeFXPERplIRPwpVYtn3RBa4\r\nContent-Type: application/http\r\nContent-ID: "
        "response-222748d1-1388-4c06-a48f-445f7aef19a9\r\n\r\nHTTP/1.1 200 OK\r\nContent-Type: "
        "application/json; charset=UTF-8\r\nVary: Origin\r\nVary: X-Origin\r\nVary: Referer\r\n\r\n{\n  "
        f'"name": "projects/{creds.project_id}/messages/0:1612788010922733%7606eb247606eb26"\n}}\n\r\n'
        "--batch_llG_9dniIyeFXPERplIRPwpVYtn3RBa4--\r\n"
    )

    httpx_mock.add_response(
        status_code=200,
        content=response_data.encode(),
        headers={"content-type": "multipart/mixed; boundary=batch_llG_9dniIyeFXPERplIRPwpVYtn3RBa4"},
    )
    apns_config = fake_async_fcm_client_w_creds.build_apns_config(
        priority="normal",
        apns_topic="test-push",
        collapse_key="push",
        badge=0,
        category="test-category",
        custom_data={"foo": "bar"},
    )
    messages = [
        Message(apns=apns_config, token=fake_device_token) for fake_device_token in fake_multi_device_tokens
    ]
    response = await fake_async_fcm_client_w_creds.send_all(messages)
    assert isinstance(response, FCMBatchResponse)
    assert response.success_count == 3
    assert response.failure_count == 0
    assert response.responses[0].message_id == "projects/fake-mobile-app/messages/0:1612788010922733%7606eb247606eb24"
    assert response.responses[1].message_id == "projects/fake-mobile-app/messages/0:1612788010922733%7606eb247606eb25"
    assert response.responses[2].message_id == "projects/fake-mobile-app/messages/0:1612788010922733%7606eb247606eb26"


@pytest.mark.parametrize("fake_multi_device_tokens", (3,), indirect=True)
async def test_send_each_makes_proper_http_calls(
    fake_async_fcm_client_w_creds, fake_multi_device_tokens: list, httpx_mock: HTTPXMock
):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    creds = fake_async_fcm_client_w_creds._credentials
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    creds = fake_async_fcm_client_w_creds._credentials
    response_message_ids = [
        "0:1612788010922733%7606eb247606eb24",
        "0:1612788010922733%7606eb247606eb35",
        "0:1612788010922733%7606eb247606eb46",
    ]
    for message_id in response_message_ids:
        httpx_mock.add_response(
            status_code=200,
            json={"name": f"projects/{creds.project_id}/messages/{message_id}"},
        )
    apns_config: APNSConfig = fake_async_fcm_client_w_creds.build_apns_config(
        priority="normal",
        apns_topic="Your bucket has been updated",
        collapse_key="BUCKET_UPDATED",
        badge=1,
        category="CATEGORY_BUCKET_UPDATED",
        custom_data={"foo": "bar"},
        mutable_content=True,
        content_available=True,
    )
    messages = [
        Message(apns=apns_config, token=fake_device_token) for fake_device_token in fake_multi_device_tokens
    ]
    await fake_async_fcm_client_w_creds.send_each(messages)
    request_payloads = [json.loads(request.read()) for request in httpx_mock.get_requests()]
    expected_request_payloads = [
        {
            "message": {
                "apns": {
                    "headers": apns_config.headers,
                    "payload": {
                        "aps": {
                            "badge": 1,
                            "category": "CATEGORY_BUCKET_UPDATED",
                            "content-available": True,
                            "mutable-content": True,
                        },
                        "foo": "bar",
                    },
                },
                "token": fake_device_token,
            },
            "validate_only": False,
        } for fake_device_token in fake_multi_device_tokens
    ]
    for payload, expected_payload in zip(request_payloads, expected_request_payloads):
        assert payload == expected_payload


@pytest.mark.parametrize("fake_multi_device_tokens", (3,), indirect=True)
async def test_send_each_returns_correct_data(
    fake_async_fcm_client_w_creds, fake_multi_device_tokens: list, httpx_mock: HTTPXMock
):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    creds = fake_async_fcm_client_w_creds._credentials
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    creds = fake_async_fcm_client_w_creds._credentials
    response_message_ids = [
        "0:1612788010922733%7606eb247606eb24",
        "0:1612788010922733%7606eb247606eb35",
        "0:1612788010922733%7606eb247606eb46",
    ]
    for message_id in (response_message_ids[0], response_message_ids[1]):
        httpx_mock.add_response(
            status_code=200,
            json={"name": f"projects/{creds.project_id}/messages/{message_id}"},
        )
    httpx_mock.add_response(status_code=500)
    apns_config: APNSConfig = fake_async_fcm_client_w_creds.build_apns_config(
        priority="normal",
        apns_topic="Your bucket has been updated",
        collapse_key="BUCKET_UPDATED",
        badge=1,
        category="CATEGORY_BUCKET_UPDATED",
        custom_data={"foo": "bar"},
        mutable_content=True,
        content_available=True,
    )
    messages = [
        Message(apns=apns_config, token=fake_device_token) for fake_device_token in fake_multi_device_tokens
    ]
    fcm_batch_response = await fake_async_fcm_client_w_creds.send_each(messages)

    assert fcm_batch_response.success_count == 2
    assert fcm_batch_response.failure_count == 1
    assert isinstance(fcm_batch_response, FCMBatchResponse)
    for fcm_response in fcm_batch_response.responses:
        assert isinstance(fcm_response, FCMResponse)

    # check successful responses
    for fcm_response, response_message_id in list(zip(fcm_batch_response.responses, response_message_ids))[1:2]:
        assert fcm_response.message_id == f"projects/{creds.project_id}/messages/{response_message_id}"
        assert fcm_response.exception is None

    # check failed response
    failed_fcm_response = fcm_batch_response.responses[2]
    assert failed_fcm_response.message_id is None
    assert isinstance(failed_fcm_response.exception, InternalError)


@pytest.mark.parametrize("fake_multi_device_tokens", (3,), indirect=True)
async def test_send_each_for_multicast(
    fake_async_fcm_client_w_creds, fake_multi_device_tokens: list,
):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    send_each_mock = mock.AsyncMock()
    fake_async_fcm_client_w_creds.send_each = send_each_mock
    apns_config = fake_async_fcm_client_w_creds.build_apns_config(
        priority="normal",
        apns_topic="test-push",
        collapse_key="push",
        badge=0,
        category="test-category",
        custom_data={"foo": "bar"},
    )
    await fake_async_fcm_client_w_creds.send_each_for_multicast(
        MulticastMessage(apns=apns_config, tokens=fake_multi_device_tokens),
    )
    send_each_argument = send_each_mock.call_args[0][0]
    assert isinstance(send_each_argument, list)
    for message in send_each_argument:
        assert isinstance(message, Message)
        assert message.apns == apns_config
        assert message.token is not None


@pytest.mark.parametrize("fake_multi_device_tokens", (3,), indirect=True)
async def test_send_all_dry_run(
    fake_async_fcm_client_w_creds, fake_multi_device_tokens: list, httpx_mock: HTTPXMock
):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    creds = fake_async_fcm_client_w_creds._credentials
    response_data = (
        "\r\n--batch_llG_9dniIyeFXPERplIRPwpVYtn3RBa4\r\nContent-Type: application/http\r\nContent-ID: "
        "response-4440d691-7909-4346-af9a-b44f17638f6c\r\n\r\nHTTP/1.1 200 OK\r\nContent-Type: "
        "application/json; charset=UTF-8\r\nVary: Origin\r\nVary: X-Origin\r\nVary: Referer\r\n\r\n{\n  "
        f'"name": "projects/{creds.project_id}/messages/fake_message_id"\n}}\n\r\n'
        "--batch_llG_9dniIyeFXPERplIRPwpVYtn3RBa4\r\nContent-Type: application/http\r\nContent-ID: "
        "response-fdbc3fd2-4031-4c00-88d2-22c9523bb941\r\n\r\nHTTP/1.1 200 OK\r\nContent-Type: "
        "application/json; charset=UTF-8\r\nVary: Origin\r\nVary: X-Origin\r\nVary: Referer\r\n\r\n{\n  "
        f'"name": "projects/{creds.project_id}/messages/fake_message_id"\n}}\n\r\n'
        "--batch_llG_9dniIyeFXPERplIRPwpVYtn3RBa4\r\nContent-Type: application/http\r\nContent-ID: "
        "response-222748d1-1388-4c06-a48f-445f7aef19a9\r\n\r\nHTTP/1.1 200 OK\r\nContent-Type: "
        "application/json; charset=UTF-8\r\nVary: Origin\r\nVary: X-Origin\r\nVary: Referer\r\n\r\n{\n  "
        f'"name": "projects/{creds.project_id}/messages/fake_message_id"\n}}\n\r\n'
        "--batch_llG_9dniIyeFXPERplIRPwpVYtn3RBa4--\r\n"
    )
    httpx_mock.add_response(
        status_code=200,
        content=response_data.encode(),
        headers={"content-type": "multipart/mixed; boundary=batch_llG_9dniIyeFXPERplIRPwpVYtn3RBa4"},
    )
    apns_config = fake_async_fcm_client_w_creds.build_apns_config(
        priority="normal",
        apns_topic="test-push",
        collapse_key="push",
        badge=0,
        category="test-category",
        custom_data={"foo": "bar"},
    )
    messages = [
        Message(apns=apns_config, token=fake_device_token) for fake_device_token in fake_multi_device_tokens
    ]
    response = await fake_async_fcm_client_w_creds.send_all(messages, dry_run=True)

    assert isinstance(response, FCMBatchResponse)
    assert response.success_count == 3
    assert response.failure_count == 0
    assert response.responses[0].message_id == "projects/fake-mobile-app/messages/fake_message_id"
    assert response.responses[1].message_id == "projects/fake-mobile-app/messages/fake_message_id"
    assert response.responses[2].message_id == "projects/fake-mobile-app/messages/fake_message_id"


@pytest.mark.parametrize("fake_multi_device_tokens", (501, 600, 1000), indirect=True)
async def test_send_multicast_too_many_tokens(
    fake_async_fcm_client_w_creds,
    fake_multi_device_tokens: list,
):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    apns_config = fake_async_fcm_client_w_creds.build_apns_config(
        priority="normal",
        apns_topic="test-push",
        collapse_key="push",
        badge=0,
        category="test-category",
        custom_data={"foo": "bar"},
    )
    with pytest.raises(ValueError):
        await fake_async_fcm_client_w_creds.send_multicast(
            MulticastMessage(apns=apns_config, tokens=fake_multi_device_tokens),
            dry_run=True
        )


async def test_send_all_unknown_registration_token(fake_async_fcm_client_w_creds, httpx_mock: HTTPXMock):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    response_data = (
        "\r\n--batch_HwFDZe-SUCq5qEgCavJPhhi8tA7xJBlB\r\nContent-Type: application/http\r\nContent-ID: "
        "response-363ad2c9-a3d1-45f5-b559-6d69a13a880e\r\n\r\nHTTP/1.1 400 Bad Request\r\nVary: Origin\r\nVary: "
        'X-Origin\r\nVary: Referer\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{\n  "error": {\n    '
        '"code": 400,\n    "message": "The registration token is not a valid FCM registration token",\n    "status": '
        '"INVALID_ARGUMENT",\n    "details": [\n      {\n        "@type": '
        '"type.googleapis.com/google.firebase.fcm.v1.FcmError",\n        "errorCode": "INVALID_ARGUMENT"\n      }\n   '
        " ]\n  }\n}\n\r\n--batch_HwFDZe-SUCq5qEgCavJPhhi8tA7xJBlB--\r\n"
    )
    httpx_mock.add_response(
        status_code=400,
        content=response_data.encode(),
        headers={"content-type": "multipart/mixed; boundary=batch_HwFDZe-SUCq5qEgCavJPhhi8tA7xJBlB"},
    )
    apns_config = fake_async_fcm_client_w_creds.build_apns_config(
        priority="normal",
        apns_topic="test-push",
        collapse_key="push",
        badge=0,
        category="test-category",
        custom_data={"foo": "bar"},
    )
    messages = [Message(apns=apns_config, token="qwerty:ytrewq")]
    response = await fake_async_fcm_client_w_creds.send_all(messages)

    assert isinstance(response, FCMBatchResponse)
    assert response.success_count == 0
    assert response.failure_count == 1
    assert response.responses[0].exception.code == FcmErrorCode.INVALID_ARGUMENT.value
    assert response.responses[0].exception.cause.response.status_code == 400


async def test_send_response_error_invalid_argument(fake_async_fcm_client_w_creds, httpx_mock: HTTPXMock):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    response_data = (
        '\r\n--batch_H3WKviwlw1OiFBuquMNPomHJtcBwS2Oi\r\n'
        'Content-Type: application/http\r\n'
        'Content-ID: response-37b4e119-2d98-4544-852d-082e429c18c2\r\n\r\n'
        'HTTP/1.1 400 Bad Request\r\n'
        'Vary: Origin\r\n'
        'Vary: X-Origin\r\n'
        'Vary: Referer\r\n'
        'Content-Type: application/json; charset=UTF-8\r\n\r\n'
        '{\n "error": {\n "code": 400,\n "message": "Invalid value at \'message.data[1].value\' (TYPE_STRING), 10",\n'
        ' "status": "INVALID_ARGUMENT",\n "details": [\n {\n "@type": "type.googleapis.com/google.rpc.BadRequest",\n'
        ' "fieldViolations": [\n {\n "field": "message.data[1].value",\n'
        ' "description": "Invalid value at \'message.data[1].value\' (TYPE_STRING), 10"\n }\n ]\n }\n ]\n }\n}\n\r\n'
        '--batch_H3WKviwlw1OiFBuquMNPomHJtcBwS2Oi--\r\n'
    )
    httpx_mock.add_response(
        status_code=400,
        content=response_data.encode(),
        headers={"content-type": "multipart/mixed; boundary=batch_HwFDZe-SUCq5qEgCavJPhhi8tA7xJBlB"},
    )
    apns_config = fake_async_fcm_client_w_creds.build_apns_config(
        priority="normal",
        apns_topic="test-push",
        collapse_key="push",
        badge=0,
        category="test-category",
        custom_data={"foo": "bar"},
    )
    messages = [Message(apns=apns_config, token="qwerty:ytrewq")]
    response = await fake_async_fcm_client_w_creds.send_all(messages)

    assert isinstance(response, FCMBatchResponse)
    assert response.success_count == 0
    assert response.failure_count == 1
    assert response.responses[0].exception.code == FcmErrorCode.INVALID_ARGUMENT.value
    assert response.responses[0].exception.cause.response.status_code == 400


async def test_send_all_data_has_not_provided(fake_async_fcm_client_w_creds):
    messages = [Message(token="device_id:device_token")]
    with pytest.raises(ValueError):
        await fake_async_fcm_client_w_creds.send_all(messages)


@pytest.mark.parametrize("fake_multi_device_tokens", (501, 600, 1000), indirect=True)
async def test_send_all_too_many_messages(
    fake_async_fcm_client_w_creds,
    fake_multi_device_tokens: list,
):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    apns_config = fake_async_fcm_client_w_creds.build_apns_config(
        priority="normal",
        apns_topic="test-push",
        collapse_key="push",
        badge=0,
        category="test-category",
        custom_data={"foo": "bar"},
    )
    with pytest.raises(ValueError):
        await fake_async_fcm_client_w_creds.send_all(
            [Message(apns=apns_config, token=device_token) for device_token in fake_multi_device_tokens],
            dry_run=True
        )


@pytest.mark.parametrize(
    "apns_config, message, exp_push_notification",
    (
        (
            None,
            Message(
                token="token-1",
                data={"text": "hello"},
            ),
            {
                "message": {"token": "token-1", "data": {"text": "hello"}},
                "validate_only": True,
            },
        ),
        (
            APNSConfig(),
            Message(
                token="token-1",
                data={"text": "hello"},
            ),
            {
                "message": {"token": "token-1", "data": {"text": "hello"}},
                "validate_only": True,
            },
        ),
        (
            APNSConfig(
                payload=APNSPayload(
                    aps=Aps(
                        alert="push-text",
                        badge=5,
                        sound="default",
                        content_available=True,
                        category="NEW_MESSAGE",
                        mutable_content=False,
                    )
                )
            ),
            Message(token="token-1", apns=APNSConfig(payload=APNSPayload())),
            {
                "message": {
                    "token": "token-1",
                    "apns": {
                        "payload": {
                            "aps": {
                                "alert": "push-text",
                                "badge": 5,
                                "sound": "default",
                                "content-available": True,
                                "category": "NEW_MESSAGE",
                                "mutable-content": False,
                            }
                        }
                    },
                },
                "validate_only": True,
            },
        ),
    ),
)
def test_assemble_push_notification(fake_async_fcm_client_w_creds, apns_config, message, exp_push_notification):
    push_notification = fake_async_fcm_client_w_creds.assemble_push_notification(
        apns_config=apns_config, dry_run=True, message=message
    )
    assert push_notification == exp_push_notification


def test_build_webpush_config(fake_async_fcm_client_w_creds):
    webpush_config = fake_async_fcm_client_w_creds.build_webpush_config(
        data={"attr_1": "value_1", "attr_2": "value_2"},
        title="Test Webpush Title",
        body="Test Webpush Body",
        image="https://cdn.healhtjoy.com/public/test-image.png",
        language="en",
        tag="test",
        custom_data={"attr_3": "value_3", "attr_4": "value_4"},
        link="https://link-to-something.domain.com"
    )
    assert webpush_config == WebpushConfig(
        data={"attr_1": "value_1", "attr_2": "value_2"},
        headers={},
        notification=WebpushNotification(
            title="Test Webpush Title",
            body="Test Webpush Body",
            image="https://cdn.healhtjoy.com/public/test-image.png",
            language="en",
            tag="test",
            silent=False,
            renotify=False,
            actions=[],
            direction="auto",
            custom_data={"attr_3": "value_3", "attr_4": "value_4"},
        ),
        fcm_options=WebpushFCMOptions(link="https://link-to-something.domain.com")
    )


@pytest.mark.parametrize("fake_multi_device_tokens", (3,), indirect=True)
async def test_subscribe_to_topic(fake_async_fcm_client_w_creds, fake_multi_device_tokens, httpx_mock: HTTPXMock):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    httpx_mock.add_response(
        status_code=200,
        json={"results": [{}, {}, {}]},
    )
    response = await fake_async_fcm_client_w_creds.subscribe_devices_to_topic(
        topic_name="test_topic", device_tokens=fake_multi_device_tokens
    )
    assert isinstance(response, TopicManagementResponse)
    assert response.success_count == 3
    assert response.errors == []
    assert response.failure_count == 0


@pytest.mark.parametrize("fake_multi_device_tokens", (3,), indirect=True)
async def test_subscribe_to_topic_with_incorrect(
        fake_async_fcm_client_w_creds, fake_multi_device_tokens, httpx_mock: HTTPXMock
):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token

    device_tokens = [*fake_multi_device_tokens, "incorrect"]
    httpx_mock.add_response(
        status_code=200,
        json={"results": [{}, {}, {}, {"error": "INVALID_ARGUMENT"}]},
    )
    response = await fake_async_fcm_client_w_creds.subscribe_devices_to_topic(
        topic_name='test_topic', device_tokens=device_tokens
    )
    assert isinstance(response, TopicManagementResponse)
    assert response.success_count == 3
    assert response.failure_count == 1
    assert len(response.errors) == 1

    assert isinstance(response.errors[0], TopicManagementErrorInfo)
    assert response.errors[0].index == 3
    assert response.errors[0].reason == "INVALID_ARGUMENT"


@pytest.mark.parametrize("fake_multi_device_tokens", (3,), indirect=True)
async def test_unsubscribe_to_topic(fake_async_fcm_client_w_creds, fake_multi_device_tokens, httpx_mock: HTTPXMock):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    httpx_mock.add_response(
        status_code=200,
        json={"results": [{}, {}, {}]},
    )
    response = await fake_async_fcm_client_w_creds.unsubscribe_devices_from_topic(
        topic_name="test_topic", device_tokens=fake_multi_device_tokens
    )
    assert isinstance(response, TopicManagementResponse)
    assert response.success_count == 3
    assert response.errors == []
    assert response.failure_count == 0


@pytest.mark.parametrize("fake_multi_device_tokens", (3,), indirect=True)
async def test_unsubscribe_to_topic_with_incorrect(
        fake_async_fcm_client_w_creds, fake_multi_device_tokens, httpx_mock: HTTPXMock
):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token

    device_tokens = [*fake_multi_device_tokens, "incorrect"]
    httpx_mock.add_response(
        status_code=200,
        json={"results": [{}, {}, {}, {"error": "INVALID_ARGUMENT"}]},
    )
    response = await fake_async_fcm_client_w_creds.unsubscribe_devices_from_topic(
        topic_name='test_topic', device_tokens=device_tokens
    )
    assert isinstance(response, TopicManagementResponse)
    assert response.success_count == 3
    assert response.failure_count == 1
    assert len(response.errors) == 1

    assert isinstance(response.errors[0], TopicManagementErrorInfo)
    assert response.errors[0].index == 3
    assert response.errors[0].reason == "INVALID_ARGUMENT"


@pytest.mark.parametrize("fake_multi_device_tokens", (3,), indirect=True)
async def test_send_topic_management_unauthenticated(
    fake_async_fcm_client_w_creds, fake_multi_device_tokens, httpx_mock: HTTPXMock
):
    fake_async_fcm_client_w_creds._get_access_token = fake__get_access_token
    httpx_mock.add_response(
        status_code=401,
        json={
            "error": {
                "code": 401,
                "message": "Request had invalid authentication credentials. "
                "Expected OAuth 2 access token, login cookie or other "
                "valid authentication credential. See "
                "https://developers.google.com/identity/sign-in/web/devconsole-project.",
                "status": "UNAUTHENTICATED",
            }
        },
    )
    response = await fake_async_fcm_client_w_creds.unsubscribe_devices_from_topic(
        topic_name="test_topic", device_tokens=fake_multi_device_tokens
    )

    assert isinstance(response, TopicManagementResponse)
    assert not response.success_count
    assert response.exception is not None
    assert response.exception.code == FcmErrorCode.UNAUTHENTICATED.value
    assert response.exception.cause.response.status_code == 401
