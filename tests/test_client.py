import json
import uuid
from datetime import datetime, timedelta

import pytest
from asynctest import patch
from google.oauth2 import service_account
from pytest_httpx import HTTPXMock

from async_firebase.client import AsyncFirebaseClient
from async_firebase.messages import (
    AndroidConfig,
    AndroidNotification,
    APNSConfig,
    APNSPayload,
    Aps,
    ApsAlert,
)


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


def fake_jwt_grant():
    return "fake-jwt-token", datetime.utcnow() + timedelta(days=30), {}


def fake_google_refresh(self, request):
    if self._jwt_credentials is not None:
        self._jwt_credentials.refresh(request)
        self.token = self._jwt_credentials.token
        self.expiry = self._jwt_credentials.expiry
    else:
        access_token, expiry, _ = fake_jwt_grant()
        self.token = access_token
        self.expiry = expiry


async def test__get_access_token(fake_async_fcm_client_w_creds):
    with patch("google.oauth2.service_account.Credentials.refresh", fake_google_refresh):
        access_token = await fake_async_fcm_client_w_creds._get_access_token()
        assert access_token == "fake-jwt-token"


async def test__get_access_token_called_once(fake_async_fcm_client_w_creds):
    with patch("google.oauth2._client.jwt_grant", return_value=fake_jwt_grant()) as mocked_refresh:
        for _ in range(3):
            await fake_async_fcm_client_w_creds._get_access_token()

        # since the token still valid, there should be only one request to fetch token
        assert mocked_refresh.call_count == 1


def test_build_android_config(fake_async_fcm_client_w_creds):
    android_config = fake_async_fcm_client_w_creds.build_android_config(
        priority="high",
        ttl=7200,
        collapse_key="something",
        restricted_package_name="some-package",
        data={"key_1": "value_1", "key_2": 100},
        color="red",
        sound="beep",
        tag="test",
        click_action="TOP_STORY_ACTIVITY"
    )
    assert android_config == AndroidConfig(**{
        "priority": "high",
        "collapse_key": "something",
        "restricted_package_name": "some-package",
        "data": {"key_1": "value_1", "key_2": "100"},
        "ttl": "7200s",
        "notification": AndroidNotification(**{
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
            "title_loc_args": []
        })
    })


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
    assert apns_message == APNSConfig(**{
        "headers": {
            "apns-expiration": str(int(datetime.utcnow().timestamp()) + 7200),
            "apns-priority": "10",
            "apns-topic": "test-topic",
            "apns-collapse-id": "something",
        },
        "payload": APNSPayload(**{
            "aps": Aps(**{
                "alert": ApsAlert(title="some-title", body="alert-message"),
                "badge": 0,
                "sound": "default",
                "content_available": True,
                "category": None,
                "thread_id": None,
                "mutable_content": True,
                "custom_data": {},
            })
        })
    })


async def test__prepare_headers(fake_async_fcm_client_w_creds):
    frozen_uuid = uuid.UUID(hex="6eadf1d38633427cb83dbb9be137f48c")
    with patch(
        "google.oauth2.service_account.Credentials.refresh", fake_google_refresh
    ), patch.object(
        uuid, "uuid4", side_effect=[frozen_uuid]
    ):
        headers = await fake_async_fcm_client_w_creds._prepare_headers()
        assert headers == {
            "Authorization": "Bearer fake-jwt-token",
            "Content-Type": "application/json; UTF-8",
            "X-Request-Id": str(frozen_uuid)
        }


async def test_push(fake_async_fcm_client_w_creds, fake_device_token, httpx_mock: HTTPXMock):
    creds = fake_async_fcm_client_w_creds._credentials
    httpx_mock.add_response(
        status_code=200,
        json={"name": f"projects/{creds.project_id}/messages/0:1612788010922733%7606eb247606eb24"}
    )
    apns_config = fake_async_fcm_client_w_creds.build_apns_config(
        priority="normal",
        apns_topic="test-push",
        collapse_key="push",
        badge=0,
        category="test-category",
        custom_data={"foo": "bar"}
    )
    with patch("google.oauth2.service_account.Credentials.refresh", fake_google_refresh):
        response = await fake_async_fcm_client_w_creds.push(
            device_token=fake_device_token,
            apns=apns_config
        )
    assert response == {"name": "projects/fake-mobile-app/messages/0:1612788010922733%7606eb247606eb24"}


async def test_push_dry_run(fake_async_fcm_client_w_creds, fake_device_token, httpx_mock: HTTPXMock):
    creds = fake_async_fcm_client_w_creds._credentials
    httpx_mock.add_response(
        status_code=200,
        json={"name": f"projects/{creds.project_id}/messages/fake_message_id"}
    )
    apns_config = fake_async_fcm_client_w_creds.build_apns_config(
        priority="normal",
        apns_topic="test-push",
        collapse_key="push",
        badge=0,
        category="test-category",
        custom_data={"foo": "bar"}
    )
    with patch("google.oauth2.service_account.Credentials.refresh", fake_google_refresh):
        response = await fake_async_fcm_client_w_creds.push(
            device_token=fake_device_token,
            apns=apns_config,
            dry_run=True
        )
    assert response == {"name": "projects/fake-mobile-app/messages/fake_message_id"}


async def test_push_unauthenticated(fake_async_fcm_client_w_creds, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        status_code=401,
        json={
            "error": {
                "code": 401,
                "message": "Request had invalid authentication credentials. "
                           "Expected OAuth 2 access token, login cookie or other "
                           "valid authentication credential. See "
                           "https://developers.google.com/identity/sign-in/web/devconsole-project.",
                "status": "UNAUTHENTICATED"
            }
        }
    )
    apns_config = fake_async_fcm_client_w_creds.build_apns_config(
        priority="normal",
        apns_topic="test-push",
        collapse_key="push",
        badge=0,
        category="test-category",
        custom_data={"foo": "bar"}
    )
    with patch("google.oauth2.service_account.Credentials.refresh", fake_google_refresh):
        response = await fake_async_fcm_client_w_creds.push(
            device_token="qwerty:ytrewq",
            apns=apns_config
        )
        assert response["error"]["code"] == 401


async def test_push_data_has_not_provided(fake_async_fcm_client_w_creds):
    with pytest.raises(ValueError):
        await fake_async_fcm_client_w_creds.push(device_token="device_id:device_token")


def test_creds_from_service_account_info(fake_async_fcm_client, fake_service_account):
    fake_async_fcm_client.creds_from_service_account_info(fake_service_account)
    assert isinstance(fake_async_fcm_client._credentials, service_account.Credentials)


def test_creds_from_service_account_file(fake_async_fcm_client, fake_service_account_file):
    fake_async_fcm_client.creds_from_service_account_file(fake_service_account_file)
    assert isinstance(fake_async_fcm_client._credentials, service_account.Credentials)


async def test_push_realistic_payload(fake_async_fcm_client_w_creds, fake_device_token, httpx_mock: HTTPXMock):
    creds = fake_async_fcm_client_w_creds._credentials
    httpx_mock.add_response(
        status_code=200,
        json={"name": f"projects/{creds.project_id}/messages/0:1612788010922733%7606eb247606eb24"}
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
    with patch("google.oauth2.service_account.Credentials.refresh", fake_google_refresh):
        await fake_async_fcm_client_w_creds.push(
            device_token=fake_device_token,
            apns=apns_config
        )
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
                            "mutable-content": True
                        },
                        "bucket_name": "3bc56ff12a",
                        "bucket_link": "/link/to/bucket/3bc56ff12a",
                        "aliases": ["happy_friends", "mobile_groups"],
                        "updated_count": 1,
                    }
                },
                "token": fake_device_token
            },
            "validate_only": False
        }
