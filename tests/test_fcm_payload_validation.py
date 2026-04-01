"""Integration tests that validate push message payloads against the real FCM API using dry_run=True.

These tests require valid Firebase credentials. Set the environment variable
``FIREBASE_SERVICE_ACCOUNT_KEY`` to the path of a service-account JSON file.
When credentials are absent the tests are skipped automatically.

dry_run=True tells FCM to validate the entire message structure (payload format,
field types, enum values) without actually delivering the message. A fake but
syntactically valid device token is sufficient — FCM returns NOT_FOUND /
UNREGISTERED for a nonexistent token, confirming the payload itself is valid.
FCM returns INVALID_ARGUMENT if the payload is malformed.
"""

import os
from datetime import datetime

import pytest
import pytest_asyncio

from async_firebase.client import AsyncFirebaseClient
from async_firebase.errors import InvalidArgumentError
from async_firebase.messages import (
    AndroidConfig,
    AndroidNotificationPriority,
    APNSConfig,
    LightSettings,
    Message,
    Notification,
    NotificationProxy,
    Visibility,
)


FAKE_DEVICE_TOKEN = "cyLa0tdhQEWwV6j_ZFWuHb:APA91bGqTD_gKaAiyaCDyWRwBhGLiMDTj2jXgEeM-ZZ1CclDqBViqKFvEhR46Ii-mmWcVw4tcmHHdycQPM0Spmy9-Z4uQcyTmcgN9JxPQnyVn_4E2LvfQfU"

_service_account_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
    pytest.mark.skipif(
        not _service_account_path or not os.path.isfile(_service_account_path),
        reason="FIREBASE_SERVICE_ACCOUNT_KEY not set or file not found",
    ),
]


@pytest_asyncio.fixture()
async def fcm_client():
    client = AsyncFirebaseClient()
    client.creds_from_service_account_file(_service_account_path)
    async with client:
        yield client


def _assert_payload_accepted(response):
    """Assert that FCM accepted the payload structure.

    NOT_FOUND / UNREGISTERED means the token doesn't exist but the payload
    was valid — that is the expected outcome for a fake token with dry_run.
    INVALID_ARGUMENT about the *token* is also acceptable — it means FCM
    parsed the payload successfully but rejected the fake token.
    INVALID_ARGUMENT about anything else means the payload is malformed.
    """
    if not isinstance(response.exception, InvalidArgumentError):
        return
    message = str(response.exception)
    assert "registration token" in message.lower(), (
        f"FCM rejected the payload as INVALID_ARGUMENT: {message}"
    )


async def test_standard_android_push_payload(fcm_client):
    """Validate a fully-populated Android push payload passes FCM validation."""
    android_config = AndroidConfig.build(
        priority="high",
        ttl=3600,
        collapse_key="test-collapse",
        title="Integration Test",
        body="Payload validation via dry_run",
        tag="test-tag",
        channel_id="test-channel",
        image="https://example.com/icon.png",
        ticker="ticker text",
        sticky=False,
        event_timestamp=datetime(2026, 1, 15, 12, 0, 0),
        local_only=False,
        notification_priority=AndroidNotificationPriority.HIGH,
        vibrate_timings_millis=[100, 200, 100, 200],
        default_vibrate_timings=False,
        default_sound=True,
        light_settings=LightSettings(color="#ff0000", light_on_duration_millis=500, light_off_duration_millis=1000),
        default_light_settings=False,
        notification_count=3,
        visibility=Visibility.PRIVATE,
        proxy=NotificationProxy.ALLOW,
    )
    message = Message(android=android_config, token=FAKE_DEVICE_TOKEN)
    response = await fcm_client.send(message, dry_run=True)
    _assert_payload_accepted(response)


async def test_silent_android_push_payload(fcm_client):
    """Validate a data-only (silent) Android push payload passes FCM validation."""
    android_config = AndroidConfig.build(
        priority="normal",
        ttl=600,
        data={"action": "sync", "resource_id": "42"},
    )
    message = Message(android=android_config, token=FAKE_DEVICE_TOKEN)
    response = await fcm_client.send(message, dry_run=True)
    _assert_payload_accepted(response)


async def test_standard_apns_push_payload(fcm_client):
    """Validate a standard iOS (APNS) push payload passes FCM validation."""
    apns_config = APNSConfig.build(
        priority="high",
        apns_topic="com.example.app",
        collapse_key="test-collapse",
        title="Integration Test",
        alert="Payload validation via dry_run",
        badge=1,
        sound="default",
        category="TEST_CATEGORY",
        mutable_content=True,
    )
    message = Message(apns=apns_config, token=FAKE_DEVICE_TOKEN)
    response = await fcm_client.send(message, dry_run=True)
    _assert_payload_accepted(response)


async def test_silent_apns_push_payload(fcm_client):
    """Validate a silent (content-available) iOS push payload passes FCM validation."""
    apns_config = APNSConfig.build(
        priority="normal",
        apns_topic="com.example.app",
        content_available=True,
        custom_data={"action": "background_refresh"},
    )
    message = Message(apns=apns_config, token=FAKE_DEVICE_TOKEN)
    response = await fcm_client.send(message, dry_run=True)
    _assert_payload_accepted(response)


async def test_cross_platform_push_payload(fcm_client):
    """Validate a message with both Android and APNS configs passes FCM validation."""
    android_config = AndroidConfig.build(
        priority="high",
        ttl=3600,
        title="Cross-platform Test",
        body="Testing both platforms",
        visibility=Visibility.PUBLIC,
    )
    apns_config = APNSConfig.build(
        priority="high",
        apns_topic="com.example.app",
        title="Cross-platform Test",
        alert="Testing both platforms",
        badge=1,
        sound="default",
    )
    message = Message(
        notification=Notification(title="Cross-platform Test", body="Testing both platforms"),
        android=android_config,
        apns=apns_config,
        token=FAKE_DEVICE_TOKEN,
    )
    response = await fcm_client.send(message, dry_run=True)
    _assert_payload_accepted(response)
